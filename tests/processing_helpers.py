"""Synthetic filing and recording boundaries; never access provider services."""

import hashlib
import json

PERIOD = "Three months ended September 30, 2026"
GAAP = f"For the {PERIOD.lower()}, GAAP diluted earnings per share were US$1.23."
ADJUSTED = f"For the {PERIOD.lower()}, adjusted diluted earnings per share were US$1.45."


def rehash(payload):
    canonical = {key: payload[key] for key in (
        "filing_id", "cik", "ticker", "company_name", "form_type", "filed_at", "primary_artifact_id")}
    canonical["artifacts"] = sorted(payload["artifacts"], key=lambda item: item["artifact_id"])
    raw = json.dumps(canonical, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    payload["snapshot_id"] = hashlib.sha256(raw.encode()).hexdigest()
    return payload


def fixture(sequence=1, *, gaap=GAAP, adjusted=ADJUSTED, heading_period=PERIOD):
    accession = f"0000320193-26-{sequence:06}"
    heading = f"<h1>Apple financial results — {heading_period}</h1>"
    bodies = {
        "Primary.htm": b"<h1>Apple current report</h1><p>See attached release and supplement.</p>",
        "release.htm": (heading + f"<p>{gaap}</p>").encode(),
        "supplement.htm": (heading + f"<p>{adjusted}</p>").encode(),
    }
    payload = dict(event_type="filing.ready", schema_version="1.0", filing_id=accession,
        cik="0000320193", ticker="AAPL", company_name="Apple", form_type="8-K",
        filed_at="2026-10-14T00:00:00.000000Z", ready_at="2026-10-14T00:00:01.000000Z",
        primary_artifact_id=accession + "/Primary.htm", artifacts=[
            dict(artifact_id=accession + "/" + name, filename=name,
                 s3_uri="s3://artifacts/" + accession + "/" + name, size_bytes=len(body),
                 content_type="text/html") for name, body in bodies.items()])
    rehash(payload)
    return payload, {accession + "/" + name: body for name, body in bodies.items()}



class Documents:
    def __init__(self, bodies):
        self.bodies, self.reads = bodies, []

    def read(self, artifact, *, max_bytes):
        self.reads.append(artifact.artifact_id)
        return self.bodies[artifact.artifact_id]


class Publisher:
    def __init__(self, failures=0):
        self.payloads, self.failures = [], failures

    def publish(self, payload):
        self.payloads.append(payload)
        if self.failures:
            self.failures -= 1
            raise TimeoutError("sensitive provider diagnostic")
        return "ack-" + str(len(self.payloads))
