"""One snapshot, durable extraction checkpoint, fiscal acceptance, immediate publication."""
from dataclasses import dataclass

from .contracts import FilingReady, json_text
from .errors import ContractError, StaleClaim, TechnicalFailure, WorkBusy, WorkConflict
from .fiscal.config import load_config
from .fiscal_contract import accept, make_event
from .fiscal_repository import MAX_ATTEMPTS


@dataclass(frozen=True)
class FiscalResult:
    work_id: str | None
    outcome: str
    acknowledge: bool
    reasons: tuple = ()
    event_id: str | None = None
    exhausted: bool = False


class FiscalConsumer:
    def __init__(self, repository, documents, extractor, publisher, *, config=None, expected_topic_arn=None, now=None):
        self.repository, self.documents, self.extractor, self.publisher = repository, documents, extractor, publisher
        self.config = config or load_config()
        self.expected_topic_arn = expected_topic_arn
        self.now = now or repository.now

    def process(self, message, *, run_id="initial"):
        try:
            filing = FilingReady.parse(message, expected_topic_arn=self.expected_topic_arn)
        except ContractError:
            return FiscalResult(None, "processing_failed", False, (dict(code="invalid_filing_ready", stage="input"),), exhausted=True)
        try:
            state = self.repository.claim(filing, self.config, run_id)
        except WorkBusy:
            return FiscalResult(None, "busy", False)
        except WorkConflict:
            return FiscalResult(None, "processing_failed", False, (dict(code="work_identity_conflict", stage="persistence"),), exhausted=True)
        if state["terminal"]:
            return self._result(state)
        if state["completion_ref"] is not None and (state["event_id"] is None or state["published_at"] is not None):
            return self._result(state)
        token, stage = state["claim_token"], "persistence"
        try:
            if state["completion_ref"] is None:
                job = self.repository.get_job(state["work_id"])
                receipt = job["attempts"][-1]["receipt"] if job["attempts"] else None
                if receipt is None or (receipt["outcome"] == "processing_failed" and
                        (receipt["retryable"] or state.get("retry_after_attempt") == receipt["attempt"])):
                    state = self.repository.begin_attempt(state["work_id"], token)
                    stage = "extraction"
                    receipt = self.extractor.extract(filing, self.documents, run_id=run_id, attempt=len(state["attempts"]))
                    stage = "persistence"
                    state = self.repository.save_receipt(state["work_id"], token, receipt)
                if receipt["outcome"] == "processing_failed":
                    reason = receipt["reasons"][0]
                    state = self.repository.fail(state["work_id"], token, reason["stage"], reason["code"],
                        receipt["retryable"] and len(state["attempts"]) < MAX_ATTEMPTS)
                    return self._result(state)
                outcome, reasons = (accept(receipt["extraction"]) if receipt["outcome"] == "extracted"
                                    else (receipt["outcome"], receipt["reasons"]))
                event = None
                if outcome == "accepted":
                    event = make_event(job, receipt, self.now())
                    actual = len(json_text(event).encode("utf-8"))
                    limit = self.config["persistence_limits"]["max_event_bytes"]
                    if actual > limit:
                        outcome, reasons, event = "review_required", [dict(code="event_bound_exceeded", stage="acceptance", actual=actual, limit=limit, bound="max_event_bytes")], None
                state = self.repository.complete(state["work_id"], token, outcome, reasons, event)
            if state["event_id"] is not None and state["published_at"] is None:
                stage = "publication"
                state = self.repository.begin_publication(state["work_id"], token)
                acknowledgment = self.publisher.publish(self.repository.publication_payload(state))
                state = self.repository.mark_published(state["work_id"], token, acknowledgment)
            return self._result(state)
        except StaleClaim:
            return FiscalResult(state["work_id"], "retry", False, (dict(code="claim_expired_or_replaced", stage=stage),))
        except Exception as exc:
            code = exc.code if isinstance(exc, TechnicalFailure) else stage + "_failed"
            retryable = exc.retryable if isinstance(exc, TechnicalFailure) else not isinstance(exc, (ValueError, WorkConflict))
            try:
                state = self.repository.fail(state["work_id"], token, stage, code, retryable)
            except StaleClaim:
                return FiscalResult(state["work_id"], "retry", False, (dict(code="claim_expired_or_replaced", stage=stage),))
            return self._result(state)

    def _result(self, state):
        if state["status"] == "processing_failed":
            reasons = (state["last_failure"],) if state["last_failure"] else ()
            if not reasons and state["completion_ref"]:
                reasons = tuple(self.repository._load_blob(state["completion_ref"])["reasons"])
            return FiscalResult(state["work_id"], "processing_failed" if state["terminal"] else "retry", False,
                reasons, state["event_id"], state["terminal"])
        completion = self.repository._load_blob(state["completion_ref"])
        return FiscalResult(state["work_id"], completion["outcome"], True, tuple(completion["reasons"]), state["event_id"])
