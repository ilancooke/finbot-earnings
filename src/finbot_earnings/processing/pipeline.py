"""One filing request, durable response/outcome, then recoverable publication."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import logging
import time

from .contracts import FilingReady, json_text, json_value, utc_text
from .domain import (
    Document, DocumentSource, EventPublisher, ExtractionConfig, FilingModel,
    ModelRequest, ModelResult, ProcessResult, WorkIdentity,
)
from .errors import ContractError, InputReview, StaleClaim, TechnicalFailure, WorkBusy, WorkConflict
from .repository import ProcessingRepository
from .validation import ValidationResult, document_blocks, validate
from .images import image_format, valid_image, MAX_IMAGES, MAX_IMAGE_BYTES, MAX_IMAGE_TOTAL_BYTES

LOGGER = logging.getLogger(__name__)


class FilingPipeline:
    def __init__(self, repository: ProcessingRepository, documents: DocumentSource,
                 model: FilingModel, publisher: EventPublisher,
                 config: ExtractionConfig, *, now=None, expected_topic_arn=None):
        self.repository, self.documents, self.model, self.publisher = repository, documents, model, publisher
        self.config = config
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.expected_topic_arn = expected_topic_arn

    def process(self, message, *, run_mode="production", run_id="initial") -> ProcessResult:
        started = time.monotonic()
        try:
            filing = FilingReady.parse(message, expected_topic_arn=self.expected_topic_arn)
        except ContractError:
            return ProcessResult(None, "processing_failed", False, ({"code": "invalid_notification"},), exhausted=True)
        identity = WorkIdentity(filing.filing_id, filing.snapshot_id, self.config.version, run_mode, run_id)
        try:
            job = self.repository.claim(filing, self.config, identity, self.now())
        except WorkBusy:
            return ProcessResult(identity.work_id, "busy", False)
        except WorkConflict:
            return ProcessResult(identity.work_id, "processing_failed", False, ({"code": "work_identity_conflict"},), exhausted=True)
        if job["terminal"] is not None:
            return self._failed(job)
        if job["completion"] is not None and not self.repository.pending_publications(job["work_id"]):
            return self._completed(job)
        token, stage = job["claim_token"], "input"
        try:
            if job["completion"] is None:
                reason = self._input_bound(filing)
                documents = ()
                if reason is None:
                    documents = self._load(filing)
                    try:
                        if any(not document.body or (not image_format(document.reference.filename)
                                and not document.reference.filename.lower().endswith(".pdf")
                                and not document_blocks(document)) for document in documents):
                            reason = "empty_document"
                    except UnicodeError:
                        reason = "unsupported_document_encoding"
                    if reason is None and any(document.reference.filename.lower().endswith(".pdf")
                            and not document.body.startswith(b"%PDF-") for document in documents):
                        reason = "invalid_pdf_document"
                    if reason is None and any(image_format(doc.reference.filename)
                            and not valid_image(doc.body, image_format(doc.reference.filename)) for doc in documents):
                        reason = "invalid_or_oversized_supporting_image"
                if reason is not None:
                    validation = ValidationResult("review_required", ({"code": reason},))
                else:
                    try:
                        if job["response"] is None:
                            stage = "inference"
                            model_started = utc_text(self.now())
                            result = self.model.classify_and_extract(ModelRequest(filing, documents, self.config))
                            if not isinstance(result, ModelResult):
                                raise TechnicalFailure("invalid_model_result", retryable=False)
                            try:
                                saved = json_value(json_text({**asdict(result), "started_at": model_started,
                                                             "completed_at": utc_text(self.now())}))
                            except (TypeError, ValueError, OverflowError) as exc:
                                raise TechnicalFailure("invalid_model_result", retryable=False) from exc
                            if len(json_text(saved).encode("utf-8")) > self.config.max_response_bytes:
                                raise TechnicalFailure("model_response_exceeds_limit", retryable=False)
                            stage = "checkpoint"
                            job = self.repository.save_response(job["work_id"], token, saved, self.now())
                        stage = "validation"
                        saved = job["response"]
                        if saved["model_id"] != self.config.model_id or not isinstance(saved["usage"], dict):
                            raise TechnicalFailure("model_metadata_mismatch", retryable=False)
                        for name in ("input_tokens", "output_tokens"):
                            if name in saved["usage"] and (type(saved["usage"][name]) is not int or saved["usage"][name] < 0):
                                raise TechnicalFailure("invalid_model_usage", retryable=False)
                        validation = validate(filing, documents, saved["response"], self.config)
                    except InputReview as exc:
                        validation = ValidationResult("review_required", ({"code": exc.code},))
                stage = "checkpoint"
                job = self.repository.complete(job["work_id"], token, validation, self.now())
            stage = "publication"
            for publication in self.repository.pending_publications(job["work_id"]):
                acknowledgment = self.publisher.publish(publication["payload_json"])
                self.repository.mark_published(job["work_id"], token, publication["event_id"],
                    publication["revision"], acknowledgment, self.now())
            self.repository.release(job["work_id"], token, self.now())
            LOGGER.info("Filing processing completed", extra={"work_id": job["work_id"], "run_mode": run_mode,
                "outcome": job["completion"]["outcome"], "duration_seconds": time.monotonic() - started})
            return self._completed(job)
        except StaleClaim:
            return ProcessResult(job["work_id"], "retry", False, ({"code": "claim_expired_or_replaced"},))
        except Exception as exc:
            retryable = exc.retryable if isinstance(exc, TechnicalFailure) else not isinstance(exc, WorkConflict)
            code = exc.code if isinstance(exc, TechnicalFailure) else stage + "_failed"
            LOGGER.warning("Filing processing failed", extra={"work_id": job["work_id"], "run_mode": run_mode,
                "stage": stage, "error_type": type(exc).__name__, "error_code": code})
            # A failed persistence service is allowed to propagate: claiming a
            # durable retry/terminal checkpoint in that case would invent success.
            try:
                job = self.repository.fail(job["work_id"], token, stage, code, retryable, self.now())
            except StaleClaim:
                return ProcessResult(job["work_id"], "retry", False, ({"code": "claim_expired_or_replaced"},))
            return self._failed(job)

    def _input_bound(self, filing):
        images = [artifact for artifact in filing.artifacts if image_format(artifact.filename)]
        documents = [artifact for artifact in filing.artifacts if not image_format(artifact.filename)]
        if len(documents) > self.config.max_documents:
            return "too_many_documents"
        if len(images) > MAX_IMAGES:
            return "too_many_supporting_images"
        if (sum(image.size_bytes for image in images) > MAX_IMAGE_TOTAL_BYTES
                or any(image.size_bytes > MAX_IMAGE_BYTES for image in images)):
            return "supporting_images_exceed_limit"
        if sum(artifact.size_bytes for artifact in documents) > self.config.max_input_bytes:
            return "filing_input_exceeds_limit"
        for artifact in filing.artifacts:
            format = image_format(artifact.filename)
            if format:
                if artifact.content_type is not None and artifact.content_type.split(";", 1)[0].strip().lower() != "image/" + format:
                    return "unsupported_document_format"
                continue
            if not artifact.filename.lower().endswith((".txt", ".htm", ".html", ".pdf")):
                return "unsupported_document_format"
            if artifact.content_type is not None:
                mime = artifact.content_type.split(";", 1)[0].strip().lower()
                allowed = {"application/pdf"} if artifact.filename.lower().endswith(".pdf") else {
                    "text/plain", "text/html", "application/xhtml+xml"}
                if mime not in allowed:
                    return "unsupported_document_format"
        return None

    def _load(self, filing):
        documents, total, image_total = [], 0, 0
        for artifact in filing.artifacts:
            image = bool(image_format(artifact.filename))
            bound = min(MAX_IMAGE_BYTES, MAX_IMAGE_TOTAL_BYTES - image_total) if image else self.config.max_input_bytes - total
            body = self.documents.read(artifact, max_bytes=bound)
            if not isinstance(body, bytes) or len(body) != artifact.size_bytes:
                raise TechnicalFailure("stored_object_size_mismatch")
            if image:
                image_total += len(body)
            else:
                total += len(body)
            if total > self.config.max_input_bytes:
                raise TechnicalFailure("stored_object_exceeds_limit")
            documents.append(Document(artifact, body))
        return tuple(documents)

    @staticmethod
    def _completed(job):
        result = job["completion"]
        return ProcessResult(job["work_id"], result["outcome"], True, tuple(result["findings"]),
                             tuple(tuple(value) for value in result["publications"]))

    @staticmethod
    def _failed(job):
        failure = job["terminal"] or job.get("last_failure", {})
        exhausted = job["terminal"] is not None
        return ProcessResult(job["work_id"], "processing_failed" if exhausted else "retry", False,
                             ({"code": failure.get("code", "processing_failed"), "stage": failure.get("stage", "unknown")},),
                             exhausted=exhausted)
