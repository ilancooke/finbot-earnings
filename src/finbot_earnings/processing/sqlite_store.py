"""Durable offline reference adapter, separate from the legacy artifact registry.

One transaction commits accepted event revisions, publication intents and the
processing outcome. Leases fence every checkpoint; expired workers cannot commit.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import timedelta
from pathlib import Path
import sqlite3
import uuid

from .contracts import json_text, json_value, utc_text
from .reconciliation import plan_completion
from .errors import StaleClaim, TechnicalFailure, WorkBusy, WorkConflict


class SQLiteProcessingRepository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, timeout=5, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS processing_jobs (work_id TEXT PRIMARY KEY, record_json TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS canonical_events (event_id TEXT PRIMARY KEY, revision INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS event_revisions (
                event_id TEXT NOT NULL, revision INTEGER NOT NULL, payload_json TEXT NOT NULL,
                PRIMARY KEY(event_id, revision));
            CREATE TABLE IF NOT EXISTS publication_outbox (
                event_id TEXT NOT NULL, revision INTEGER NOT NULL, payload_json TEXT NOT NULL,
                published_at TEXT, acknowledgment TEXT, PRIMARY KEY(event_id, revision),
                FOREIGN KEY(event_id, revision) REFERENCES event_revisions(event_id, revision));
            CREATE TABLE IF NOT EXISTS job_publications (
                work_id TEXT NOT NULL REFERENCES processing_jobs(work_id), event_id TEXT NOT NULL,
                revision INTEGER NOT NULL, PRIMARY KEY(work_id, event_id, revision),
                FOREIGN KEY(event_id, revision) REFERENCES publication_outbox(event_id, revision));
        """)

    def close(self):
        self.db.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    @contextmanager
    def transaction(self):
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise

    def get_job(self, work_id):
        row = self.db.execute("SELECT record_json FROM processing_jobs WHERE work_id=?", (work_id,)).fetchone()
        return None if row is None else json_value(row["record_json"])

    def _save(self, job):
        self.db.execute("UPDATE processing_jobs SET record_json=? WHERE work_id=?", (json_text(job), job["work_id"]))

    def _owned(self, work_id, token, now):
        job = self.get_job(work_id)
        if (job is None or not token or job["claim_token"] != token or job["lease_until"] <= utc_text(now)):
            raise StaleClaim("work claim expired or replaced")
        return job

    def claim(self, filing, config, identity, now):
        from dataclasses import asdict
        with self.transaction():
            job = self.get_job(identity.work_id)
            if job is None:
                job = dict(work_id=identity.work_id, identity=asdict(identity), input=filing.to_dict(),
                           config=config.to_dict(), created_at=utc_text(now), attempt_count=0,
                           claim_token=None, lease_until=None, response=None, completion=None,
                           failures={}, terminal=None)
                self.db.execute("INSERT INTO processing_jobs VALUES (?,?)", (identity.work_id, json_text(job)))
            elif (job["input"] != filing.to_dict() or job["config"] != config.to_dict() or job["identity"] != asdict(identity)):
                raise WorkConflict("work identity reused with changed input/configuration")
            if job["terminal"] is not None or (job["completion"] is not None and not self.pending_publications(job["work_id"])):
                return job
            if job["claim_token"] is not None and job["lease_until"] > utc_text(now):
                raise WorkBusy("work already claimed")
            job.update(claim_token=uuid.uuid4().hex, lease_until=utc_text(now + timedelta(seconds=config.lease_seconds)),
                       attempt_count=job["attempt_count"] + 1)
            self._save(job)
            return job

    def save_response(self, work_id, token, response, now):
        with self.transaction():
            job = self._owned(work_id, token, now)
            if job["response"] is not None:
                if job["response"] != response:
                    raise WorkConflict("saved model response is immutable")
                return job
            job["response"] = response
            self._save(job)
            return job

    def complete(self, work_id, token, validation, now):
        with self.transaction():
            job = self._owned(work_id, token, now)
            if job["completion"] is not None:
                return job
            completion, changes = plan_completion(job, validation, self.event, now)
            for event_id, prior_revision, payload in changes:
                if payload is None:
                    continue
                revision, message = payload["revision"], json_text(payload)
                self.db.execute("INSERT INTO event_revisions VALUES (?,?,?)", (event_id, revision, message))
                self.db.execute("INSERT INTO publication_outbox(event_id,revision,payload_json) VALUES (?,?,?)",
                                (event_id, revision, message))
                if prior_revision is None:
                    self.db.execute("INSERT INTO canonical_events VALUES (?,?)", (event_id, revision))
                else:
                    self.db.execute("UPDATE canonical_events SET revision=? WHERE event_id=?", (revision, event_id))
            for event_id, revision in completion["publications"]:
                self.db.execute("INSERT INTO job_publications VALUES (?,?,?)", (work_id, event_id, revision))
            job["completion"] = completion
            self._save(job)
            return job

    def event(self, event_id, revision=None):
        if revision is None:
            row = self.db.execute("SELECT revision FROM canonical_events WHERE event_id=?", (event_id,)).fetchone()
            if row is None:
                return None
            revision = row["revision"]
        row = self.db.execute("SELECT payload_json FROM event_revisions WHERE event_id=? AND revision=?", (event_id, revision)).fetchone()
        return None if row is None else json_value(row["payload_json"])

    def pending_publications(self, work_id):
        rows = self.db.execute("""SELECT p.* FROM publication_outbox p JOIN job_publications j
            ON p.event_id=j.event_id AND p.revision=j.revision
            WHERE j.work_id=? AND p.published_at IS NULL ORDER BY p.event_id,p.revision""", (work_id,)).fetchall()
        return [dict(row) for row in rows]

    def mark_published(self, work_id, token, event_id, revision, acknowledgment, now):
        if not isinstance(acknowledgment, str) or not acknowledgment.strip() or len(acknowledgment) > 200:
            raise TechnicalFailure("missing_publication_acknowledgment")
        with self.transaction():
            self._owned(work_id, token, now)
            linked = self.db.execute("SELECT 1 FROM job_publications WHERE work_id=? AND event_id=? AND revision=?",
                                     (work_id, event_id, revision)).fetchone()
            if linked is None:
                raise WorkConflict("publication does not belong to processing record")
            self.db.execute("""UPDATE publication_outbox SET published_at=?, acknowledgment=?
                WHERE event_id=? AND revision=? AND published_at IS NULL""", (utc_text(now), acknowledgment, event_id, revision))

    def release(self, work_id, token, now):
        with self.transaction():
            job = self._owned(work_id, token, now)
            job.update(claim_token=None, lease_until=None)
            self._save(job)

    def fail(self, work_id, token, stage, code, retryable, now):
        with self.transaction():
            job = self._owned(work_id, token, now)
            count = job["failures"].get(stage, 0) + 1
            job["failures"][stage] = count
            job["last_failure"] = dict(stage=stage, code=code, at=utc_text(now))
            if not retryable or count >= job["config"]["max_stage_failures"]:
                job["terminal"] = dict(job["last_failure"])
            job.update(claim_token=None, lease_until=None)
            self._save(job)
            return job

    def rearm(self, work_id, now):
        """Explicit operator redrive: retain saved response, revisions and outbox."""
        with self.transaction():
            job = self.get_job(work_id)
            if job is None:
                raise KeyError(work_id)
            if job["claim_token"] is not None and job["lease_until"] > utc_text(now):
                raise WorkBusy("cannot redrive active work")
            job.update(terminal=None, failures={}, claim_token=None, lease_until=None, redriven_at=utc_text(now))
            self._save(job)
