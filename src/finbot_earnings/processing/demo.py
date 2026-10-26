"""Synthetic fiscal consumer demo using the real OpenAI SDK over mocked HTTP."""
import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import httpx

from .contracts import json_text
from .fiscal import OpenAIFiscalExtractor, make_client
from .fiscal_consumer import FiscalConsumer
from .fiscal_stores import SQLiteFiscalRepository


def run(output_dir):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    accession = "0000320193-26-000001"
    bodies = {"primary.htm": b"<h1>Synthetic company current report</h1>",
        "release.htm": b"<h1>FY2026 Q3 results</h1><table><tr><td>Diluted EPS</td><td>USD 1.230</td></tr></table>",
        "supplement.htm": b"<p>Adjusted diluted EPS: USD 1.45, FY2026 Q3</p>"}
    snapshot = dict(filing_id=accession, cik="0000320193", ticker="AAPL", company_name="Synthetic company",
        form_type="8-K", filed_at="2026-10-14T00:00:00.000000Z", primary_artifact_id=accession + "/primary.htm",
        artifacts=[dict(artifact_id=accession + "/" + name, filename=name,
            s3_uri="s3://synthetic-artifacts/" + accession + "/" + name, size_bytes=len(raw), content_type="text/html")
            for name, raw in bodies.items()])
    payload = dict(**snapshot, snapshot_id=hashlib.sha256(json_text(snapshot).encode()).hexdigest(),
        event_type="filing.ready", schema_version="1.0", ready_at="2026-10-14T00:00:01.000000Z")
    (output_dir / "filing-ready.json").write_text(json_text(payload) + "\n")
    documents_dir = output_dir / "synthetic-documents"
    documents_dir.mkdir()
    for name, raw in bodies.items():
        (documents_dir / name).write_bytes(raw)

    class LocalDocuments:
        def read(self, artifact, *, max_bytes):
            with (documents_dir / artifact.filename).open("rb") as stream:
                return stream.read(max_bytes + 1)

    calls, document_counts = [], []
    row = dict(currency="USD", period_type="quarterly", fiscal_year=2026, fiscal_quarter=3)
    full = dict(reported_diluted_eps=[dict(**row, value="1.230")], adjusted_diluted_eps=[dict(**row, value="1.45")])
    empty = dict(reported_diluted_eps=[], adjusted_diluted_eps=[])

    def transport(request):
        content = json.loads(request.content)["input"][0]["content"]
        document_counts.append(sum(b.get("text", "").startswith("Source attachment: ") for b in content))
        calls.append(request.url.path)
        value = full if len(calls) == 1 else empty
        native = dict(status="completed", output=[dict(type="message", role="assistant", status="completed",
            content=[dict(type="output_text", text=json_text(value))])], usage=dict(input_tokens=100, output_tokens=50))
        return httpx.Response(200, json=native)

    class FilePublisher:
        calls = 0
        def publish(self, message):
            self.calls += 1
            with (output_dir / "published-events.jsonl").open("a") as stream:
                stream.write(message + "\n")
            return f"local-ack-{self.calls}"

    publisher = FilePublisher()
    repository = SQLiteFiscalRepository(output_dir / "processing.sqlite3")
    try:
        with make_client("synthetic-offline-key", http_client=httpx.Client(transport=httpx.MockTransport(transport))) as client:
            worker = FiscalConsumer(repository, LocalDocuments(), OpenAIFiscalExtractor(client), publisher)
            result = worker.process(payload)
            duplicate = worker.process(payload)
            empty_result = worker.process(payload, run_id="empty-demo")
            mixed = json.loads(json_text(payload))
            mixed["artifacts"].append(dict(artifact_id=accession + "/selected.pdf", filename="selected.pdf",
                s3_uri="s3://synthetic-artifacts/selected.pdf", size_bytes=100, content_type="application/pdf"))
            mixed["artifacts"].sort(key=lambda ref: ref["artifact_id"])
            mixed["snapshot_id"] = hashlib.sha256(json_text({k: mixed[k] for k in snapshot}).encode()).hexdigest()
            review = worker.process(mixed)
        for name, outcome in (("processing-record", result), ("empty-record", empty_result), ("review-record", review)):
            (output_dir / (name + ".json")).write_text(json.dumps(repository.get_job(outcome.work_id), indent=2) + "\n")
    finally:
        repository.close()
    summary = dict(result=asdict(result), model_calls=len(calls), documents_per_call=document_counts,
        published_events=publisher.calls, duplicate_acknowledged=duplicate.acknowledge,
        empty_outcome=empty_result.outcome, review_outcome=review.outcome)
    if (result.outcome, empty_result.outcome, review.outcome, publisher.calls, len(calls)) != ("accepted", "no_eps_extracted", "review_required", 1, 2) or duplicate != result:
        raise RuntimeError("Synthetic fiscal demo failed; inspect processing records")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    try:
        summary = run(args.output_dir)
    except FileExistsError:
        parser.error("output directory already exists; choose a new directory")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
