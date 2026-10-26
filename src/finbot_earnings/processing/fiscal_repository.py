"""Version-2 state machine shared by the SQLite and DynamoDB adapters.

Large immutable JSON blobs are staged in bounded content-addressed chunks.
Only fenced atomic state commits make them reachable. Unlinked crash remnants
are harmless; no TTL or cleanup can remove referenced historical blobs.
"""
from base64 import b64decode, b64encode
from datetime import datetime, timedelta, timezone
import hashlib
import uuid

from .contracts import json_text, json_value, timestamp, utc_text
from .errors import StaleClaim, TechnicalFailure, WorkBusy, WorkConflict
from .fiscal.config import digest
from .fiscal_contract import FiscalIdentity

CHUNK_BYTES = 128 * 1024
MAX_BLOB_BYTES = 24 * 1024 * 1024
MAX_ATTEMPTS = 3
LEASE_SECONDS = 360
MAX_STAGE_FAILURES = 3
STATUSES = {"processing", "accepted", "review_required", "no_eps_extracted", "processing_failed"}


class FiscalRepository:
    def __init__(self, *, now=None):
        self.now = now or (lambda: datetime.now(timezone.utc))

    def _blob(self, value):
        raw = json_text(value).encode("utf-8")
        if len(raw) > MAX_BLOB_BYTES:
            raise TechnicalFailure("receipt_storage_bound_exceeded", retryable=False)
        key = hashlib.sha256(raw).hexdigest()
        count = (len(raw) + CHUNK_BYTES - 1) // CHUNK_BYTES
        for index in range(count):
            item = dict(pk="EPS2#BLOB#" + key, sk=f"CHUNK#{index:04d}",
                        data=b64encode(raw[index * CHUNK_BYTES:(index + 1) * CHUNK_BYTES]).decode("ascii"))
            self._immutable(item)
        return dict(sha256=key, size_bytes=len(raw), chunks=count)

    @staticmethod
    def _blob_identity(value):
        raw = json_text(value).encode("utf-8")
        return dict(sha256=hashlib.sha256(raw).hexdigest(), size_bytes=len(raw),
                    chunks=(len(raw) + CHUNK_BYTES - 1) // CHUNK_BYTES)

    def _load_blob(self, ref):
        if not 0 < ref["size_bytes"] <= MAX_BLOB_BYTES or ref["chunks"] != (ref["size_bytes"] + CHUNK_BYTES - 1) // CHUNK_BYTES:
            raise TechnicalFailure("invalid_blob_reference", retryable=False)
        parts = []
        for index in range(int(ref["chunks"])):
            item = self._get("EPS2#BLOB#" + ref["sha256"], f"CHUNK#{index:04d}")
            if item is None:
                raise TechnicalFailure("missing_persisted_blob", retryable=False)
            parts.append(b64decode(item["data"], validate=True))
        raw = b"".join(parts)
        if len(raw) != ref["size_bytes"] or hashlib.sha256(raw).hexdigest() != ref["sha256"]:
            raise TechnicalFailure("corrupt_persisted_blob", retryable=False)
        return json_value(raw)

    def _state(self, work_id):
        item = self._get("EPS2#WORK#" + work_id, "STATE")
        return None if item is None else json_value(item["record_json"])

    def get_job(self, work_id):
        # Logical references from events are resolvable by the same inspection API.
        work_id = work_id.replace("earnings-processing:v2:", "earnings-work:v2:", 1)
        if work_id.endswith("/input"):
            job = self.get_job(work_id[:-6])
            return None if job is None else job["input"]
        state = self._state(work_id)
        if state is None:
            return None
        return {**state, "input": self._load_blob(state["input_ref"]),
            "extraction_config": self._load_blob(state["config_ref"]),
            "attempts": [{**a, "receipt": None if a.get("receipt_ref") is None else self._load_blob(a["receipt_ref"])} for a in state["attempts"]],
            "completion": None if state["completion_ref"] is None else self._load_blob(state["completion_ref"])}

    def event(self, event_id):
        item = self._get("EPS2#EVENT#" + event_id, "PAYLOAD")
        return None if item is None else self._load_blob(item["payload_ref"])

    def _owned(self, state, token):
        if state is None or not token or state["claim_token"] != token or state["lease_until"] <= utc_text(self.now()):
            raise StaleClaim("work claim expired or replaced")

    def _save(self, prior, state, *, token=None, extra=()):
        state["version"] = 0 if prior is None else prior["version"] + 1
        state["updated_at"] = utc_text(self.now())
        item = dict(pk="EPS2#WORK#" + state["work_id"], sk="STATE", version=state["version"],
                    claim_token=state["claim_token"], lease_until=state["lease_until"], record_json=json_text(state))
        summary = dict(pk="EPS2#STATUS#" + state["status"], sk=state["work_id"],
                       work_id=state["work_id"], status=state["status"], updated_at=state["updated_at"],
                       event_id=state["event_id"], published_at=state["published_at"], terminal=state["terminal"])
        deletes = [] if prior is None or prior["status"] == state["status"] else [dict(pk="EPS2#STATUS#" + prior["status"], sk=state["work_id"])]
        return self._cas(item, prior, token, utc_text(self.now()), [summary, *extra], deletes)

    def _mutate(self, work_id, token, change):
        for _ in range(5):
            prior = self._state(work_id)
            self._owned(prior, token)
            state = json_value(json_text(prior))
            change(state)
            if self._save(prior, state, token=token):
                return state
        raise TechnicalFailure("checkpoint_contention")

    def claim(self, filing, config, run_id="initial"):
        identity = FiscalIdentity(filing.filing_id, filing.snapshot_id, config["version"], digest(config), run_id)
        input_ref, config_ref = self._blob_identity(filing.to_dict()), self._blob_identity(config)
        for _ in range(5):
            prior = self._state(identity.work_id)
            if prior is None:
                # Register a version globally, including across different filings.
                self._immutable(dict(pk="EPS2#CONFIG#" + config["version"], sk="DIGEST", sha256=digest(config)))
                self._blob(filing.to_dict())
                self._blob(config)
                state = dict(record_schema_version=2, work_id=identity.work_id, processing_record_ref=identity.record_ref,
                    identity=identity.to_dict(), input_ref=input_ref, config_ref=config_ref, created_at=utc_text(self.now()),
                    status="processing", claim_token=None, lease_until=None, attempts=[], completion_ref=None,
                    event_id=None, payload_ref=None, published_at=None, acknowledgment=None, publication_attempts=0,
                    failures={}, terminal=False, last_failure=None,
                    timing=dict(first_claimed_at=utc_text(self.now()),
                        ready_to_first_claim_ms=round((self.now() - timestamp(filing.ready_at)).total_seconds() * 1000)),
                    operational_policy=dict(lease_seconds=LEASE_SECONDS, max_provider_attempts=MAX_ATTEMPTS, max_stage_failures=MAX_STAGE_FAILURES))
            else:
                state = json_value(json_text(prior))
                if state["input_ref"] != input_ref or state["config_ref"] != config_ref or state["identity"] != identity.to_dict():
                    raise WorkConflict("work identity reused with changed input/configuration")
                if state["terminal"] or (state["completion_ref"] is not None and (state["event_id"] is None or state["published_at"] is not None)):
                    return state
                if state["claim_token"] and state["lease_until"] > utc_text(self.now()):
                    raise WorkBusy("work already claimed")
            state.update(claim_token=uuid.uuid4().hex, lease_until=utc_text(self.now() + timedelta(seconds=LEASE_SECONDS)))
            if self._save(prior, state):
                return state
        raise WorkBusy("claim contention")

    def begin_attempt(self, work_id, token):
        def change(state):
            if state["completion_ref"] is not None or len(state["attempts"]) >= MAX_ATTEMPTS:
                raise TechnicalFailure("provider_attempt_budget_exhausted", retryable=False)
            if state["attempts"] and state["attempts"][-1]["receipt_ref"]:
                latest = self._load_blob(state["attempts"][-1]["receipt_ref"])
                if latest["outcome"] != "processing_failed":
                    raise WorkConflict("saved successful/review receipt must be resumed")
            state["attempts"].append(dict(attempt=len(state["attempts"]) + 1, reserved_at=utc_text(self.now()),
                                          receipt_ref=None, usage_unknown=True))
        return self._mutate(work_id, token, change)

    def save_receipt(self, work_id, token, receipt):
        ref = self._blob(receipt)
        def change(state):
            if not state["attempts"] or receipt["attempt"] != len(state["attempts"]):
                raise WorkConflict("receipt attempt does not match reserved attempt")
            current = state["attempts"][-1]
            if current["receipt_ref"] is not None and current["receipt_ref"] != ref:
                raise WorkConflict("saved receipt is immutable")
            if receipt["input"] != self._load_blob(state["input_ref"]) or receipt["extraction_config"] != self._load_blob(state["config_ref"]) or receipt["extraction_config_sha256"] != state["identity"]["extraction_config_sha256"] or receipt["run_id"] != state["identity"]["run_id"]:
                raise WorkConflict("receipt provenance mismatch")
            current.update(receipt_ref=ref, usage_unknown=receipt["usage_unknown"], receipt_saved_at=utc_text(self.now()))
        return self._mutate(work_id, token, change)

    def complete(self, work_id, token, outcome, reasons, event=None):
        completion_ref = self._blob(dict(outcome=outcome, reasons=reasons, completed_at=utc_text(self.now())))
        payload_ref = None if event is None else self._blob(event)
        for _ in range(5):
            prior = self._state(work_id)
            self._owned(prior, token)
            if prior["completion_ref"] is not None:
                return prior
            if outcome not in {"accepted", "review_required", "no_eps_extracted", "processing_failed"} or (outcome == "accepted") != (event is not None):
                raise WorkConflict("outcome and publication intent disagree")
            state = json_value(json_text(prior))
            extra = []
            if event is not None:
                identity = FiscalIdentity(**state["identity"])
                if event["event_id"] != identity.event_id:
                    raise WorkConflict("event identity mismatch")
                state.update(event_id=identity.event_id, payload_ref=payload_ref)
                extra.append(dict(pk="EPS2#EVENT#" + identity.event_id, sk="PAYLOAD", payload_ref=payload_ref))
            state.update(completion_ref=completion_ref, status=outcome, terminal=outcome == "processing_failed")
            state["timing"]["outcome_committed_at"] = utc_text(self.now())
            if outcome == "processing_failed":
                state["last_failure"] = {**reasons[0], "at": utc_text(self.now())}
            if event is None:
                state.update(claim_token=None, lease_until=None)
            if self._save(prior, state, token=token, extra=extra):
                return state
        raise TechnicalFailure("completion_contention")

    def publication_payload(self, state):
        return json_text(self._load_blob(state["payload_ref"]))

    def begin_publication(self, work_id, token):
        def change(state):
            if state["event_id"] is None or state["published_at"] is not None:
                raise WorkConflict("no pending publication")
            state["publication_attempts"] += 1
            state["publication_started_at"] = utc_text(self.now())
        return self._mutate(work_id, token, change)

    def mark_published(self, work_id, token, acknowledgment):
        if not isinstance(acknowledgment, str) or not acknowledgment.strip() or len(acknowledgment) > 200:
            raise TechnicalFailure("missing_publication_acknowledgment")
        def change(state):
            state.update(published_at=utc_text(self.now()), acknowledgment=acknowledgment,
                         status="accepted", terminal=False, claim_token=None, lease_until=None)
            source = self._load_blob(state["input_ref"])
            state["timing"]["ready_to_publication_ack_ms"] = round((self.now() - timestamp(source["ready_at"])).total_seconds() * 1000)
            state["timing"]["last_publication_ms"] = round((self.now() - timestamp(state["publication_started_at"])).total_seconds() * 1000)
        return self._mutate(work_id, token, change)

    def fail(self, work_id, token, stage, code, retryable):
        def change(state):
            state["failures"][stage] = state["failures"].get(stage, 0) + 1
            state.update(status="processing_failed", last_failure=dict(code=code, stage=stage, at=utc_text(self.now())),
                         terminal=not retryable or state["failures"][stage] >= MAX_STAGE_FAILURES,
                         claim_token=None, lease_until=None)
        return self._mutate(work_id, token, change)

    def rearm(self, work_id):
        for _ in range(5):
            prior = self._state(work_id)
            if prior is None:
                raise KeyError(work_id)
            if prior["claim_token"] and prior["lease_until"] > utc_text(self.now()):
                raise WorkBusy("cannot redrive active work")
            if prior["status"] != "processing_failed":
                raise WorkConflict("retry requires failed work; use a fresh run for completed outcomes")
            if prior["completion_ref"] is not None and prior["event_id"] is None or (
                    prior["last_failure"] and prior["last_failure"]["code"] == "invalid_model_response"):
                raise WorkConflict("saved invalid output requires a fresh run")
            state = json_value(json_text(prior))
            if prior["last_failure"] and prior["last_failure"]["code"] == "provider_configuration_failure":
                state["retry_after_attempt"] = len(prior["attempts"])
            state.update(terminal=False, failures={}, claim_token=None, lease_until=None, redriven_at=utc_text(self.now()))
            if self._save(prior, state):
                return state
        raise WorkBusy("redrive contention")

    def list_status(self, status, *, limit=50, cursor=None):
        if status not in STATUSES or type(limit) is not int or not 1 <= limit <= 100:
            raise ValueError("invalid status or page limit")
        return self._query("EPS2#STATUS#" + status, limit, cursor)
