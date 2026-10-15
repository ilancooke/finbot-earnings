"""Validate a frozen, locally stored corpus before any inference is possible."""

from dataclasses import dataclass
import hashlib
from pathlib import Path
import re

from finbot_earnings.processing.contracts import FilingReady, fields, json_text, json_value, nonempty
from finbot_earnings.processing.domain import ExtractionConfig, response_facts


def file_hash(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def local_path(root, name):
    if not isinstance(name, str) or not name or Path(name).is_absolute():
        raise ValueError("Corpus paths must be relative")
    path = (root / name).resolve()
    if not path.is_relative_to(root):
        raise ValueError("Corpus path escapes its root")
    if not path.is_file():
        raise ValueError(f"Missing corpus file: {name}")
    return path


def read_json(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(1024 * 1024 + 1)
    if len(raw) > 1024 * 1024:
        raise ValueError("Corpus JSON exceeds 1 MiB")
    return json_value(raw)


@dataclass(frozen=True)
class Case:
    case_id: str
    tags: tuple[str, ...]
    filing: FilingReady
    documents: dict
    expected: dict
    fixture: dict | None
    snapshot: dict


@dataclass(frozen=True)
class Corpus:
    corpus_id: str
    label_source: str
    cases: tuple[Case, ...]
    snapshot: dict
    sha256: str


def load_corpus(path, config: ExtractionConfig, *, offline=False):
    path = Path(path).resolve()
    root, value = path.parent, read_json(path)
    fields(value, ("schema_version", "corpus_id", "label_source", "label_notes", "cases"))
    if value["schema_version"] != "1.0" or value["label_source"] not in {"synthetic", "agent_draft", "human_reviewed"}:
        raise ValueError("Unsupported corpus schema or label source")
    nonempty(value["corpus_id"], "corpus_id")
    nonempty(value["label_notes"], "label_notes")
    if not isinstance(value["cases"], list) or not value["cases"]:
        raise ValueError("Corpus requires cases")
    cases, ids, snapshots = [], set(), set()
    for name in value["cases"]:
        source = local_path(root, name)
        case = read_json(source)
        fields(case, ("case_id", "tags", "filing", "documents", "expected"), ("fixture_response",))
        case_id = case["case_id"]
        if not isinstance(case_id, str) or not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_-]{0,79}", case_id) or case_id in ids:
            raise ValueError("Case IDs must be unique filename-safe tokens")
        ids.add(case_id)
        if not isinstance(case["tags"], list) or any(not isinstance(tag, str) or not tag.strip() for tag in case["tags"]):
            raise ValueError("Tags must be a list of strings")
        filing = FilingReady.parse(case["filing"])
        identity = (filing.filing_id, filing.snapshot_id)
        if identity in snapshots:
            raise ValueError("Repeated filing snapshot in corpus")
        snapshots.add(identity)
        expected = case["expected"]
        facts = response_facts(expected, config)
        if expected["classification"] != "reports_earnings" and facts:
            raise ValueError("Non-earnings/uncertain labels must have no facts")
        artifact_ids = {artifact.artifact_id for artifact in filing.artifacts}
        fact_keys = [(fact.metric, fact.period_key) for fact in facts]
        if len(set(fact_keys)) != len(fact_keys) or any(fact.source_artifact_id not in artifact_ids for fact in facts):
            raise ValueError("Expected facts need unique metric/period keys and manifest sources")
        documents = case["documents"]
        if not isinstance(documents, dict) or set(documents) != artifact_ids:
            raise ValueError("Local document mapping must cover the entire filing manifest")
        paths = {}
        for artifact in filing.artifacts:
            item = documents[artifact.artifact_id]
            fields(item, ("path", "sha256"))
            if not isinstance(item["sha256"], str) or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"]):
                raise ValueError("Document SHA-256 required")
            document = local_path(root, item["path"])
            if document.stat().st_size != artifact.size_bytes or file_hash(document) != item["sha256"]:
                raise ValueError(f"Frozen document size/hash mismatch in {case_id}")
            paths[artifact.artifact_id] = document
        fixture = None
        if offline:
            fixture = read_json(local_path(root, case.get("fixture_response")))
            fields(fixture, ("response", "usage"))
            if not isinstance(fixture["usage"], dict):
                raise ValueError("Fixture usage must be an object")
        # Store the parsed labels and input manifest, not just their filenames.
        snapshot = {**case, "case_file": name}
        if offline:
            snapshot["fixture"] = fixture
        cases.append(Case(case_id, tuple(case["tags"]), filing, paths, expected, fixture, snapshot))
    snapshot = {**value, "cases": [case.snapshot for case in cases]}
    # Responses are run inputs for fixture playback, not ground truth or source
    # identity. The same corpus keeps its identity in offline and Bedrock modes.
    identity = {**snapshot, "cases": [{key: item for key, item in case.snapshot.items() if key != "fixture"}
                                    for case in cases]}
    digest = hashlib.sha256(json_text(identity).encode()).hexdigest()
    return Corpus(value["corpus_id"], value["label_source"], tuple(cases), snapshot, digest)


class LocalDocuments:
    def __init__(self, case):
        self.case = case

    def read(self, artifact, *, max_bytes):
        with self.case.documents[artifact.artifact_id].open("rb") as stream:
            body = stream.read(min(artifact.size_bytes, max_bytes) + 1)
        expected = self.case.snapshot["documents"][artifact.artifact_id]["sha256"]
        if len(body) != artifact.size_bytes or hashlib.sha256(body).hexdigest() != expected:
            raise ValueError("Frozen document changed after preflight")
        return body
