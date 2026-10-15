"""Standalone synthetic filing demo; no environment loading, network or model API."""

from __future__ import annotations

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

from .contracts import json_text
from .domain import ExtractionConfig, ModelResult
from .pipeline import FilingPipeline
from .sqlite_store import SQLiteProcessingRepository


def run(output_dir: Path):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    accession = "0000320193-26-000001"
    label = "Three months ended September 30, 2026"
    gaap = f"For the {label.lower()}, GAAP diluted earnings per share were US$1.23."
    adjusted = f"For the {label.lower()}, adjusted diluted earnings per share were US$1.45."
    heading = f"<h1>Apple financial results — {label}</h1>"
    bodies = {
        "primary.htm": b"<h1>Apple current report</h1><p>See attached earnings documents.</p>",
        "release.htm": (heading + f"<p>{gaap}</p>").encode(),
        "supplement.htm": (heading + f"<p>{adjusted}</p>").encode(),
    }
    manifest = [dict(artifact_id=accession + "/" + name, filename=name,
        s3_uri="s3://synthetic-artifacts/" + accession + "/" + name,
        size_bytes=len(body), content_type="text/html") for name, body in bodies.items()]
    snapshot = dict(filing_id=accession, cik="0000320193", ticker="AAPL", company_name="Apple",
        form_type="8-K", filed_at="2026-10-14T00:00:00.000000Z",
        primary_artifact_id=accession + "/primary.htm", artifacts=manifest)
    payload = dict(**snapshot, snapshot_id=hashlib.sha256(json_text(snapshot).encode()).hexdigest(),
        event_type="filing.ready", schema_version="1.0", ready_at="2026-10-14T00:00:01.000000Z")
    (output_dir / "filing-ready.json").write_text(json_text(payload) + "\n", encoding="utf-8")
    documents_dir = output_dir / "synthetic-documents"
    documents_dir.mkdir()
    for name, body in bodies.items():
        (documents_dir / name).write_bytes(body)

    class LocalDocuments:
        def read(self, artifact, *, max_bytes):
            with (documents_dir / artifact.filename).open("rb") as stream:
                return stream.read(max_bytes + 1)

    class FixtureModel:
        calls = 0
        document_counts = []

        def classify_and_extract(self, request):
            self.calls += 1
            self.document_counts.append(len(request.documents))
            facts = [dict(metric=metric, value=value, currency="USD",
                period=dict(kind="quarter", end_date="2026-09-30", label=label),
                source_artifact_id=accession + "/" + filename, evidence=quote)
                for metric, value, filename, quote in (
                    ("gaap_diluted_eps", "1.23", "release.htm", gaap),
                    ("adjusted_diluted_eps", "1.45", "supplement.htm", adjusted))]
            return ModelResult(dict(classification="reports_earnings", facts=facts), "fixture", {})

    class FilePublisher:
        calls = 0

        def publish(self, message):
            self.calls += 1
            with (output_dir / "published-events.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(message + "\n")
            return f"local-ack-{self.calls}"

    model, publisher = FixtureModel(), FilePublisher()
    with SQLiteProcessingRepository(output_dir / "processing.sqlite3") as repository:
        worker = FilingPipeline(repository, LocalDocuments(), model, publisher, ExtractionConfig("offline-demo-v1"))
        result = worker.process(payload)
        duplicate = worker.process(payload)
        (output_dir / "processing-record.json").write_text(
            json.dumps(repository.get_job(result.work_id), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = dict(result=asdict(result), model_calls=model.calls, documents_per_call=model.document_counts,
        published_events=publisher.calls, duplicate_acknowledged=duplicate.acknowledge)
    if result.outcome != "validated" or not result.acknowledge:
        raise RuntimeError("Synthetic filing did not validate; inspect processing-record.json")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path, help="New directory for synthetic demo results")
    args = parser.parse_args()
    try:
        summary = run(args.output_dir)
    except FileExistsError:
        parser.error("output directory already exists; choose a new directory")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
