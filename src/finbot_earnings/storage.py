from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .clock import isoformat, parse_datetime, utc_now
from .identity import artifact_id, artifact_identity, sha256_bytes
from .models import (
    ArtifactRecord, ArtifactType, DiscoveredArtifact, DownloadedArtifact, EarningsExtraction,
    ParsedArtifact, ProcessingState, SourceProvider, jsonable,
)


class ArtifactStore:
    """SQLite registry with immutable raw payloads on the local filesystem."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.artifacts_root = self.root / "artifacts"
        self.events_root = self.root / "events"
        self.root.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.root / "registry.sqlite3")
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA foreign_keys=ON")
        self._initialize()

    def close(self) -> None:
        self._db.close()

    def __enter__(self) -> "ArtifactStore":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def _initialize(self) -> None:
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS events (
              event_id TEXT PRIMARY KEY, ticker TEXT NOT NULL, anchor_date TEXT NOT NULL,
              fiscal_period_raw TEXT, created_at TEXT NOT NULL,
              UNIQUE(ticker, anchor_date)
            );
            CREATE TABLE IF NOT EXISTS artifacts (
              artifact_id TEXT PRIMARY KEY, identity_key TEXT NOT NULL UNIQUE,
              ticker TEXT NOT NULL, event_id TEXT NOT NULL REFERENCES events(event_id),
              provider TEXT NOT NULL, artifact_type TEXT NOT NULL, source_url TEXT NOT NULL,
              content_hash TEXT NOT NULL, raw_path TEXT NOT NULL, state TEXT NOT NULL,
              published_at TEXT, detected_at TEXT NOT NULL, download_started_at TEXT NOT NULL,
              downloaded_at TEXT NOT NULL, parse_started_at TEXT, parsed_at TEXT, extraction_started_at TEXT,
              extraction_completed_at TEXT, structured_data_ready_at TEXT,
              accession_number TEXT, filename TEXT, retry_count INTEGER NOT NULL DEFAULT 0,
              error_stage TEXT, error_message TEXT, last_attempt_at TEXT, metadata_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS extractions (
              extraction_id TEXT PRIMARY KEY, artifact_id TEXT NOT NULL REFERENCES artifacts(artifact_id),
              provider TEXT NOT NULL, model TEXT NOT NULL, prompt_version TEXT NOT NULL,
              schema_version TEXT NOT NULL, parser_version TEXT NOT NULL,
              started_at TEXT NOT NULL, completed_at TEXT NOT NULL, data_path TEXT NOT NULL,
              data_json TEXT NOT NULL, usage_json TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS artifacts_ticker_idx ON artifacts(ticker, detected_at);
            CREATE INDEX IF NOT EXISTS artifacts_event_idx ON artifacts(event_id, detected_at);
            CREATE TABLE IF NOT EXISTS source_state (
              source_name TEXT NOT NULL, ticker TEXT NOT NULL, initialized_at TEXT NOT NULL,
              PRIMARY KEY(source_name, ticker)
            );
            CREATE TABLE IF NOT EXISTS source_seen (
              source_name TEXT NOT NULL, ticker TEXT NOT NULL, discovery_key TEXT NOT NULL,
              first_seen_at TEXT NOT NULL,
              PRIMARY KEY(source_name, ticker, discovery_key)
            );
            """
        )
        columns = {row["name"] for row in self._db.execute("PRAGMA table_info(artifacts)").fetchall()}
        if "parse_started_at" not in columns:
            self._db.execute("ALTER TABLE artifacts ADD COLUMN parse_started_at TEXT")
        self._db.commit()

    @staticmethod
    def discovery_key(discovery: DiscoveredArtifact) -> str:
        if discovery.provider == SourceProvider.SEC and discovery.accession_number:
            return f"{discovery.accession_number}:{(discovery.filename or discovery.url).lower()}"
        return discovery.external_id or discovery.url

    def source_initialized(self, source_name: str, ticker: str) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM source_state WHERE source_name=? AND ticker=?",
            (source_name, ticker.upper()),
        ).fetchone()
        return row is not None

    def baseline_source(self, source_name: str, ticker: str, discoveries: list[DiscoveredArtifact]) -> None:
        now = isoformat(utc_now())
        for discovery in discoveries:
            self._db.execute(
                "INSERT OR IGNORE INTO source_seen(source_name,ticker,discovery_key,first_seen_at) VALUES(?,?,?,?)",
                (source_name, ticker.upper(), self.discovery_key(discovery), now),
            )
        self._db.execute(
            "INSERT OR IGNORE INTO source_state(source_name,ticker,initialized_at) VALUES(?,?,?)",
            (source_name, ticker.upper(), now),
        )
        self._db.commit()

    def claim_discovery(self, source_name: str, discovery: DiscoveredArtifact) -> bool:
        cursor = self._db.execute(
            "INSERT OR IGNORE INTO source_seen(source_name,ticker,discovery_key,first_seen_at) VALUES(?,?,?,?)",
            (source_name, discovery.ticker, self.discovery_key(discovery), isoformat(discovery.detected_at)),
        )
        self._db.commit()
        return cursor.rowcount == 1

    def discovery_seen(self, source_name: str, discovery: DiscoveredArtifact) -> bool:
        row = self._db.execute(
            "SELECT 1 FROM source_seen WHERE source_name=? AND ticker=? AND discovery_key=?",
            (source_name, discovery.ticker, self.discovery_key(discovery)),
        ).fetchone()
        return row is not None

    def _event_for(self, ticker: str, moment: datetime) -> str:
        anchor = moment.date()
        rows = self._db.execute(
            "SELECT event_id, anchor_date FROM events WHERE ticker=? ORDER BY anchor_date DESC", (ticker,)
        ).fetchall()
        for row in rows:
            existing = date.fromisoformat(row["anchor_date"])
            if abs((existing - anchor).days) <= 3:
                return str(row["event_id"])
        event_id = f"{ticker}-{anchor.isoformat()}"
        self._db.execute(
            "INSERT OR IGNORE INTO events(event_id,ticker,anchor_date,created_at) VALUES(?,?,?,?)",
            (event_id, ticker, anchor.isoformat(), isoformat(utc_now())),
        )
        self._write_event(event_id)
        return event_id

    def register(self, downloaded: DownloadedArtifact) -> tuple[ArtifactRecord, bool]:
        discovery = downloaded.discovery
        digest = sha256_bytes(downloaded.body)
        identity = artifact_identity(discovery, digest)
        identifier = artifact_id(identity)
        existing = self._db.execute("SELECT * FROM artifacts WHERE identity_key=?", (identity,)).fetchone()
        if existing:
            return self._row_to_record(existing), False

        event_moment = discovery.published_at or discovery.detected_at
        event_id = self._event_for(discovery.ticker, event_moment)
        artifact_dir = self.artifacts_root / discovery.ticker / identifier
        artifact_dir.mkdir(parents=True, exist_ok=True)
        suffix = self._raw_suffix(discovery.filename, downloaded.headers)
        raw_path = artifact_dir / f"raw{suffix}"
        self._write_immutable(raw_path, downloaded.body)
        metadata = {
            **discovery.metadata,
            "title": discovery.title,
            "external_id": discovery.external_id,
            "http": {
                "status_code": downloaded.status_code,
                "headers": downloaded.headers,
                "final_url": downloaded.final_url,
            },
        }
        values = (
            identifier, identity, discovery.ticker, event_id, discovery.provider.value,
            discovery.artifact_type.value, discovery.url, digest, str(raw_path),
            ProcessingState.PERSISTED.value, isoformat(discovery.published_at),
            isoformat(discovery.detected_at), isoformat(downloaded.download_started_at),
            isoformat(downloaded.downloaded_at), discovery.accession_number,
            discovery.filename, json.dumps(metadata, sort_keys=True),
        )
        try:
            self._db.execute(
                """INSERT INTO artifacts(
                artifact_id,identity_key,ticker,event_id,provider,artifact_type,source_url,
                content_hash,raw_path,state,published_at,detected_at,download_started_at,
                downloaded_at,accession_number,filename,metadata_json)
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", values,
            )
            self._db.commit()
        except sqlite3.IntegrityError:
            row = self._db.execute("SELECT * FROM artifacts WHERE identity_key=?", (identity,)).fetchone()
            if not row:
                raise
            return self._row_to_record(row), False
        record = self.get_artifact(identifier)
        self._write_artifact_metadata(record)
        self.refresh_timeline(event_id)
        return record, True

    @staticmethod
    def _raw_suffix(filename: str | None, headers: dict[str, str]) -> str:
        if filename:
            suffix = Path(filename).suffix.lower()
            if suffix in {".html", ".htm", ".xml", ".json", ".txt", ".pdf"}:
                return suffix
        content_type = next((v for k, v in headers.items() if k.lower() == "content-type"), "")
        if "html" in content_type:
            return ".html"
        if "json" in content_type:
            return ".json"
        if "xml" in content_type:
            return ".xml"
        return ".bin"

    @staticmethod
    def _write_immutable(path: Path, body: bytes) -> None:
        try:
            with path.open("xb") as handle:
                handle.write(body)
        except FileExistsError:
            if sha256_bytes(path.read_bytes()) != sha256_bytes(body):
                raise RuntimeError(f"immutable artifact collision at {path}")

    @staticmethod
    def _atomic_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(jsonable(value), handle, indent=2, sort_keys=True)
                handle.write("\n")
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def save_parsed(self, parsed: ParsedArtifact, parse_started_at: datetime) -> Path:
        record = self.get_artifact(parsed.artifact_id)
        path = Path(record.raw_path).parent / f"parsed-{parsed.parser_version}.json"
        payload = {**jsonable(parsed), "parse_started_at": isoformat(parse_started_at)}
        if not path.exists():
            self._atomic_json(path, payload)
        if record.state != ProcessingState.EXTRACTED:
            self.update_state(
                parsed.artifact_id, ProcessingState.PARSED,
                parse_started_at=parse_started_at, parsed_at=parsed.parsed_at,
            )
        return path

    def save_extraction(
        self, extraction: EarningsExtraction, started_at: datetime, completed_at: datetime,
    ) -> Path:
        record = self.get_artifact(extraction.source_artifact_id)
        stamp = completed_at.strftime("%Y%m%dT%H%M%S.%fZ")
        safe_model = extraction.model.replace("/", "_")
        extraction_id = f"{record.artifact_id}-{stamp}"
        path = Path(record.raw_path).parent / f"extraction-{extraction.prompt_version}-{safe_model}-{stamp}.json"
        payload = jsonable(extraction)
        self._atomic_json(path, payload)
        self._db.execute(
            """INSERT INTO extractions(extraction_id,artifact_id,provider,model,prompt_version,
            schema_version,parser_version,started_at,completed_at,data_path,data_json,usage_json)
            VALUES(?,?,?,?,?,?,?,?,?,?,?,?)""",
            (extraction_id, record.artifact_id, extraction.provider, extraction.model,
             extraction.prompt_version, extraction.schema_version, extraction.parser_version,
             isoformat(started_at), isoformat(completed_at), str(path), json.dumps(payload),
             json.dumps(extraction.usage)),
        )
        self._db.commit()
        ready_at = utc_now()
        self.update_state(
            record.artifact_id, ProcessingState.EXTRACTED,
            extraction_completed_at=completed_at, structured_data_ready_at=ready_at,
        )
        return path

    def update_state(self, artifact_id_value: str, state: ProcessingState, **timestamps: datetime) -> None:
        allowed_columns = {
            "parse_started_at", "parsed_at", "extraction_started_at",
            "extraction_completed_at", "structured_data_ready_at"
        }
        unknown = set(timestamps) - allowed_columns
        if unknown:
            raise ValueError(f"unsupported timestamp columns: {sorted(unknown)}")
        current = self.get_artifact(artifact_id_value).state
        allowed = {
            ProcessingState.PERSISTED: {ProcessingState.PARSED, ProcessingState.FAILED},
            ProcessingState.PARSED: {ProcessingState.PARSED, ProcessingState.EXTRACTION_PENDING, ProcessingState.FAILED},
            ProcessingState.EXTRACTION_PENDING: {ProcessingState.EXTRACTING, ProcessingState.FAILED},
            ProcessingState.EXTRACTING: {ProcessingState.EXTRACTING, ProcessingState.EXTRACTED, ProcessingState.FAILED},
            ProcessingState.EXTRACTED: {ProcessingState.EXTRACTED, ProcessingState.EXTRACTION_PENDING},
            ProcessingState.FAILED: {ProcessingState.PARSED, ProcessingState.EXTRACTION_PENDING, ProcessingState.EXTRACTING, ProcessingState.FAILED},
        }
        if state not in allowed.get(current, set()):
            raise ValueError(f"invalid processing-state transition: {current.value} -> {state.value}")
        assignments = ["state=?", "error_stage=NULL", "error_message=NULL"]
        values: list[Any] = [state.value]
        for name, value in timestamps.items():
            assignments.append(f"{name}=?")
            values.append(isoformat(value))
        values.append(artifact_id_value)
        self._db.execute(f"UPDATE artifacts SET {','.join(assignments)} WHERE artifact_id=?", values)
        self._db.commit()
        record = self.get_artifact(artifact_id_value)
        self._write_artifact_metadata(record)
        self.refresh_timeline(record.event_id)

    def record_failure(self, artifact_id_value: str, stage: str, error: Exception, *, permanent: bool) -> None:
        state = ProcessingState.FAILED.value if permanent else ProcessingState.EXTRACTING.value
        self._db.execute(
            """UPDATE artifacts SET state=?, retry_count=retry_count+1, error_stage=?,
            error_message=?, last_attempt_at=? WHERE artifact_id=?""",
            (state, stage, str(error)[:2000], isoformat(utc_now()), artifact_id_value),
        )
        self._db.commit()
        record = self.get_artifact(artifact_id_value)
        self._write_artifact_metadata(record)
        self.refresh_timeline(record.event_id)

    def get_artifact(self, artifact_id_value: str) -> ArtifactRecord:
        row = self._db.execute("SELECT * FROM artifacts WHERE artifact_id=?", (artifact_id_value,)).fetchone()
        if row is None:
            raise KeyError(f"artifact not found: {artifact_id_value}")
        return self._row_to_record(row)

    def list_artifacts(self, ticker: str | None = None) -> list[ArtifactRecord]:
        if ticker:
            rows = self._db.execute(
                "SELECT * FROM artifacts WHERE ticker=? ORDER BY detected_at", (ticker.upper(),)
            ).fetchall()
        else:
            rows = self._db.execute("SELECT * FROM artifacts ORDER BY detected_at").fetchall()
        return [self._row_to_record(row) for row in rows]

    def load_parsed(self, artifact_id_value: str, parser_version: str) -> ParsedArtifact | None:
        record = self.get_artifact(artifact_id_value)
        path = Path(record.raw_path).parent / f"parsed-{parser_version}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return ParsedArtifact(
            artifact_id=data["artifact_id"], ticker=data["ticker"],
            artifact_type=ArtifactType(data["artifact_type"]), source_url=data["source_url"],
            title=data.get("title"), text=data["text"], tables=data.get("tables", []),
            parser_version=data["parser_version"], parsed_at=parse_datetime(data["parsed_at"]),
        )

    def latest_event_id(self, ticker: str) -> str | None:
        row = self._db.execute(
            "SELECT event_id FROM events WHERE ticker=? ORDER BY anchor_date DESC LIMIT 1", (ticker.upper(),)
        ).fetchone()
        return str(row["event_id"]) if row else None

    def refresh_timeline(self, event_id: str) -> Path:
        event = self._db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
        if event is None:
            raise KeyError(event_id)
        records = [self._row_to_record(row) for row in self._db.execute(
            "SELECT * FROM artifacts WHERE event_id=? ORDER BY detected_at", (event_id,)
        ).fetchall()]
        event_dir = self.events_root / event["ticker"] / event_id
        self._atomic_json(event_dir / "event.json", dict(event))
        timeline = {"event_id": event_id, "ticker": event["ticker"], "artifacts": []}
        for record in records:
            base = record.published_at or record.detected_at
            timeline["artifacts"].append({
                "artifact_id": record.artifact_id, "provider": record.provider.value,
                "artifact_type": record.artifact_type.value, "state": record.state.value,
                "published_at": isoformat(record.published_at), "detected_at": isoformat(record.detected_at),
                "download_started_at": isoformat(record.download_started_at), "downloaded_at": isoformat(record.downloaded_at),
                "parse_started_at": isoformat(record.parse_started_at), "parsed_at": isoformat(record.parsed_at),
                "extraction_started_at": isoformat(record.extraction_started_at),
                "extraction_completed_at": isoformat(record.extraction_completed_at),
                "structured_data_ready_at": isoformat(record.structured_data_ready_at),
                "detection_latency_seconds": self._elapsed(record.detected_at, record.published_at),
                "download_latency_seconds": self._elapsed(record.downloaded_at, base),
                "ready_latency_seconds": self._elapsed(record.structured_data_ready_at, base),
                "retry_count": record.retry_count, "error_stage": record.error_stage,
            })
        path = event_dir / "timeline.json"
        self._atomic_json(path, timeline)
        return path

    def timeline(self, ticker: str) -> dict[str, Any] | None:
        event_id = self.latest_event_id(ticker)
        if not event_id:
            return None
        path = self.refresh_timeline(event_id)
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _elapsed(end: datetime | None, start: datetime | None) -> float | None:
        return round((end - start).total_seconds(), 6) if end and start else None

    def _write_event(self, event_id: str) -> None:
        row = self._db.execute("SELECT * FROM events WHERE event_id=?", (event_id,)).fetchone()
        if row:
            self._atomic_json(self.events_root / row["ticker"] / event_id / "event.json", dict(row))

    def _write_artifact_metadata(self, record: ArtifactRecord) -> None:
        self._atomic_json(Path(record.raw_path).parent / "metadata.json", record)

    @staticmethod
    def _row_to_record(row: sqlite3.Row) -> ArtifactRecord:
        return ArtifactRecord(
            artifact_id=row["artifact_id"], identity_key=row["identity_key"], ticker=row["ticker"],
            event_id=row["event_id"], provider=SourceProvider(row["provider"]),
            artifact_type=ArtifactType(row["artifact_type"]), source_url=row["source_url"],
            content_hash=row["content_hash"], raw_path=row["raw_path"], state=ProcessingState(row["state"]),
            published_at=parse_datetime(row["published_at"]), detected_at=parse_datetime(row["detected_at"]),
            download_started_at=parse_datetime(row["download_started_at"]), downloaded_at=parse_datetime(row["downloaded_at"]),
            parse_started_at=parse_datetime(row["parse_started_at"]), parsed_at=parse_datetime(row["parsed_at"]),
            extraction_started_at=parse_datetime(row["extraction_started_at"]),
            extraction_completed_at=parse_datetime(row["extraction_completed_at"]),
            structured_data_ready_at=parse_datetime(row["structured_data_ready_at"]),
            accession_number=row["accession_number"], filename=row["filename"], retry_count=row["retry_count"],
            error_stage=row["error_stage"], error_message=row["error_message"], metadata=json.loads(row["metadata_json"]),
        )
