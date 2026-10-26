"""Read-only replay of the saved v6 baseline through the production SDK adapter.

No scoring, credentials, provider calls, sibling imports or operational writes.
Reference fingerprints are exported independently in the evals environment; see
docs/PRODUCTION_PARITY.md. Missing or changed artifacts fail the audit.
"""
from argparse import ArgumentParser
from base64 import b64decode
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import socket

import httpx

from finbot_earnings.processing.contracts import FilingReady
from finbot_earnings.processing.fiscal import OpenAIFiscalExtractor, load_config, make_client
from finbot_earnings.processing.fiscal.config import digest, resource
from finbot_earnings.processing.fiscal_contract import accept


def require(condition, message):
    if not condition:
        raise ValueError(message)


def read_json(path):
    return json.loads(path.read_bytes())


def forbidden(*args, **kwargs):
    raise RuntimeError("Network forbidden during production parity verification")


def canonical_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(
        timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def verify_inventory(root, expected):
    require(sha256((root / "integrity.json").read_bytes()).hexdigest() == expected,
            "Saved run integrity identity changed")
    actual = {}
    for path in sorted(root.rglob("*")):
        require(not path.is_symlink(), "Saved run contains a symlink")
        if path.is_file() and path != root / "integrity.json":
            body = path.read_bytes()
            actual[path.relative_to(root).as_posix()] = dict(
                sha256=sha256(body).hexdigest(), size_bytes=len(body))
    require(read_json(root / "integrity.json") == dict(algorithm="sha256", files=actual),
            "Saved run inventory mismatch")
    return len(actual)


class FrozenDocuments:
    def __init__(self, request, directory):
        self.bodies = {}
        self.reads = []
        for document in request["documents"]:
            path = (directory / document["path"]).resolve()
            require(path.is_relative_to(directory.resolve()), "Document escapes frozen case")
            body = path.read_bytes()
            require(sha256(body).hexdigest() == document["sha256"], "Source hash mismatch")
            self.bodies[document["artifact_id"]] = body

    def read(self, ref, *, max_bytes):
        self.reads.append(ref.artifact_id)
        body = self.bodies[ref.artifact_id]
        require(len(body) <= max_bytes, "Source exceeds production bound")
        return body


def filing_ready(request, source):
    # The experiment did not save a live FilingReady envelope. This synthetic
    # envelope supplies required storage/readiness fields, never added to model
    # input. Only filed_at's equivalent ISO representation changes model context.
    context = {**request["filing"], "filed_at": canonical_time(request["filing"]["filed_at"])}
    artifacts = [dict(artifact_id=d["artifact_id"], filename=d["filename"],
                      s3_uri="s3://offline-parity/" + d["artifact_id"],
                      size_bytes=len(source.bodies[d["artifact_id"]]),
                      **{k: d[k] for k in ("content_type", "document_type") if d.get(k)})
                 for d in request["documents"]]
    canonical = dict(**context, primary_artifact_id=artifacts[0]["artifact_id"],
                     artifacts=sorted(artifacts, key=lambda d: d["artifact_id"]))
    return FilingReady.parse(dict(**canonical, event_type="filing.ready", schema_version="1.0",
                                  ready_at=context["filed_at"], snapshot_id=digest(canonical)))


def verify(root, evidence):
    count = verify_inventory(root, evidence["integrity_sha256"])
    manifest = read_json(root / "run.json")
    require(manifest["run_id"] == evidence["run_id"], "Run identity mismatch")
    require(manifest["implementation"] == evidence["reference_implementation"], "Reference code mismatch")
    require(read_json(root / "results.json")["summary"] == evidence["baseline_summary"], "Baseline changed")
    predictions = read_json(root / "predictions.json")["cases"]
    config = load_config()
    require(config["sdk_versions"] == evidence["dependencies"], "Dependency mismatch")
    require((root / "prompt.txt").read_bytes() == resource("eps-v6.txt"), "Prompt mismatch")
    require(read_json(root / "labels.schema.json") == json.loads(resource("earnings_eps_fiscal_v2.schema.json")),
            "Local schema mismatch")
    paths = {p.parent.name: p for p in (root / "inputs").glob("*/request.json")}
    require(len(paths) == len(evidence["cases"]) == 50, "Expected complete 50-filing baseline")
    require(set(paths) == {c["case_id"] for c in evidence["cases"]}, "Baseline membership mismatch")
    timing = dict(preparation_ms=0, extraction_ms=0, total_ms=0)
    maxima = dict(image_count=0, prepared_text_bytes=0, encoded_request_bytes=0, input_token_estimate=0)
    documents = observations = timestamp_changes = 0
    for case in evidence["cases"]:
        name = case["case_id"]
        path = paths[name]
        request = read_json(path)
        source = FrozenDocuments(request, path.parent)
        filing = filing_ready(request, source)
        require(request["filing"]["filed_at"] == case["filed_at_before"], "Reference timestamp changed")
        require(filing.filed_at == case["filed_at_after"], "Unexpected timestamp normalization")
        timestamp_changes += case["filed_at_before"] != case["filed_at_after"]
        body = (root / "responses" / (name + ".provider.json")).read_bytes()
        calls = []

        def handler(outbound):
            require(str(outbound.url) == "https://api.openai.com/v1/responses" and outbound.method == "POST",
                    "Endpoint mismatch")
            require(outbound.extensions["timeout"] == dict(connect=120, read=120, write=120, pool=120),
                    "Timeout mismatch")
            calls.append(json.loads(outbound.content))
            return httpx.Response(200, content=body, headers={"content-type": "application/json"})

        with httpx.Client(transport=httpx.MockTransport(handler)) as http:
            with make_client("synthetic-offline-key", http_client=http) as client:
                receipt = OpenAIFiscalExtractor(client).extract(filing, source)
        require(len(calls) == 1, "Expected one mocked request")
        require(digest(calls[0]) == case["canonical_timestamp_request_sha256"],
                "Request parity mismatch: " + name)
        # Reverse only the documented timestamp spelling to prove exact reference
        # equality too; no normalization of attachment text, images or settings.
        context = json.loads(calls[0]["input"][0]["content"][0]["text"].removeprefix("Filing context: "))
        context["filed_at"] = case["filed_at_before"]
        calls[0]["input"][0]["content"][0]["text"] = "Filing context: " + json.dumps(context, ensure_ascii=False)
        require(digest(calls[0]) == case["reference_request_sha256"], "Unexpected request difference")
        require(receipt["outcome"] == "extracted" and not receipt["usage_unknown"], "Replay failed: " + name)
        require(b64decode(receipt["response_body_base64"]) == body, "Native bytes changed")
        require(receipt["response"] == json.loads(body), "Native response changed")
        require(digest(receipt["extraction"]) == case["extraction_sha256"], "Extraction changed")
        require(digest(receipt["usage"]) == case["usage_sha256"], "Usage changed")
        require(receipt["extraction"] == predictions[name]["labels"], "Saved prediction changed")
        require(receipt["usage"] == predictions[name]["usage"], "Saved prediction usage changed")
        require(accept(receipt["extraction"]) == ("accepted", []), "Acceptance mismatch")
        require(source.reads == [r.artifact_id for r in filing.artifacts], "Selected member omission/reordering")
        require(receipt["documents"] == [dict(artifact_id=r.artifact_id, filename=r.filename,
                    size_bytes=r.size_bytes, sha256=sha256(source.bodies[r.artifact_id]).hexdigest())
                    for r in filing.artifacts], "Source inventory mismatch")
        documents += len(source.reads)
        observations += sum(map(len, receipt["extraction"].values()))
        for key in timing:
            timing[key] += receipt["timing"][key]
        for key in maxima:
            maxima[key] = max(maxima[key], receipt["request"][key])
    return dict(run_id=evidence["run_id"], configuration_sha256=digest(config),
                integrity_files=count, cases=len(paths), documents=documents, observations=observations,
                timestamp_spelling_changes=timestamp_changes, request_maxima=maxima,
                mocked_replay_timing=timing, live_provider_calls=0, new_api_cost_usd="0")


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--evidence", type=Path, default=Path(__file__).resolve().parents[1]
                        / "docs/parity/v6-reference.json")
    args = parser.parse_args()
    socket.socket.connect = socket.create_connection = forbidden
    print(json.dumps(verify(args.run.resolve(), read_json(args.evidence)), indent=2))


if __name__ == "__main__":
    main()
