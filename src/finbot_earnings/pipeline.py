from __future__ import annotations

import logging
import time
from pathlib import Path

from .clock import isoformat, utc_now
from .eligibility import ArtifactEligibilityPolicy
from .extractors.base import EarningsExtractor, PermanentExtractionError, TransientExtractionError
from .models import DownloadedArtifact, ParsedArtifact, ProcessingState
from .parsing import HTMLArtifactParser
from .sources.base import ArtifactSource, HTTPFetcher
from .storage import ArtifactStore

logger = logging.getLogger("finbot_earnings")


class EarningsPipeline:
    def __init__(
        self, store: ArtifactStore, fetcher: HTTPFetcher, extractor: EarningsExtractor | None,
        *, parser: HTMLArtifactParser | None = None,
        eligibility: ArtifactEligibilityPolicy | None = None,
        max_extraction_attempts: int = 3, retry_delay_seconds: float = 1.0,
    ):
        self.store = store
        self.fetcher = fetcher
        self.extractor = extractor
        self.parser = parser or HTMLArtifactParser()
        self.eligibility = eligibility or ArtifactEligibilityPolicy()
        self.max_extraction_attempts = max_extraction_attempts
        self.retry_delay_seconds = retry_delay_seconds

    def poll_source(self, source: ArtifactSource, ticker: str, *, baseline_if_new: bool = True) -> int:
        discoveries = source.poll()
        if baseline_if_new and not self.store.source_initialized(source.name, ticker):
            self.store.baseline_source(source.name, ticker, discoveries)
            logger.info("%s %s baseline recorded artifacts=%d", ticker, source.name, len(discoveries))
            return 0
        processed = 0
        for discovery in discoveries:
            if self.store.discovery_seen(source.name, discovery):
                continue
            logger.info("%s %s artifact discovered type=%s", ticker, source.name, discovery.artifact_type.value)
            downloaded = self.fetcher.download(discovery)
            was_new = self.process_downloaded(downloaded)
            self.store.claim_discovery(source.name, discovery)
            if was_new:
                processed += 1
        return processed

    def process_downloaded(self, downloaded: DownloadedArtifact, *, extract: bool = True) -> bool:
        record, is_new = self.store.register(downloaded)
        if not is_new and record.state in {ProcessingState.EXTRACTED, ProcessingState.FAILED}:
            logger.debug("artifact already seen id=%s", record.artifact_id)
            return False
        if not is_new and record.state == ProcessingState.EXTRACTING:
            self.store.record_failure(
                record.artifact_id, "extraction",
                RuntimeError("interrupted extraction requires explicit replay"), permanent=True,
            )
            logger.error("interrupted extraction marked failed id=%s", record.artifact_id)
            return False
        if is_new:
            logger.info("artifact persisted id=%s sha256=%s", record.artifact_id, record.content_hash)
        parsed = self.store.load_parsed(record.artifact_id, self.parser.version)
        if parsed is None:
            parse_started_at = utc_now()
            try:
                parsed = self.parser.parse(record)
                self.store.save_parsed(parsed, parse_started_at)
            except Exception as exc:
                self.store.record_failure(record.artifact_id, "parse", exc, permanent=True)
                logger.exception("artifact parse failed id=%s", record.artifact_id)
                return is_new
        record = self.store.get_artifact(record.artifact_id)
        decision = self.eligibility.decide(record)
        if not decision.analyze or not extract or self.extractor is None:
            logger.info("artifact parsed id=%s extraction=%s", record.artifact_id, decision.reason if not extract else "disabled")
            return is_new
        if record.state == ProcessingState.PARSED:
            self.store.update_state(record.artifact_id, ProcessingState.EXTRACTION_PENDING)
        self._extract(record.artifact_id, parsed)
        return is_new

    def replay(self, artifact_id: str, *, extract: bool = False) -> ParsedArtifact:
        record = self.store.get_artifact(artifact_id)
        parse_started_at = utc_now()
        parsed = self.parser.parse(record)
        self.store.save_parsed(parsed, parse_started_at)
        if extract:
            if self.extractor is None:
                raise RuntimeError("no extractor configured")
            self.store.update_state(artifact_id, ProcessingState.EXTRACTION_PENDING)
            self._extract(artifact_id, parsed)
        return parsed

    def _extract(self, artifact_id: str, parsed: ParsedArtifact) -> None:
        started_at = utc_now()
        self.store.update_state(artifact_id, ProcessingState.EXTRACTING, extraction_started_at=started_at)
        logger.info("%s extraction started id=%s", self.extractor.display_name, artifact_id)  # type: ignore[union-attr]
        for attempt in range(1, self.max_extraction_attempts + 1):
            try:
                extraction = self.extractor.extract(parsed)  # type: ignore[union-attr]
                completed_at = utc_now()
                path = self.store.save_extraction(extraction, started_at, completed_at)
                ready_at = self.store.get_artifact(artifact_id).structured_data_ready_at or completed_at
                logger.info(
                    "earnings flash ready id=%s elapsed=%.3fs path=%s",
                    artifact_id, (ready_at - started_at).total_seconds(), path,
                )
                return
            except PermanentExtractionError as exc:
                self.store.record_failure(artifact_id, "extraction", exc, permanent=True)
                logger.error("permanent extraction failure id=%s error=%s", artifact_id, exc)
                return
            except TransientExtractionError as exc:
                final = attempt == self.max_extraction_attempts
                self.store.record_failure(artifact_id, "extraction", exc, permanent=final)
                logger.warning("transient extraction failure id=%s attempt=%d/%d", artifact_id, attempt, self.max_extraction_attempts)
                if final:
                    return
                if self.retry_delay_seconds:
                    time.sleep(self.retry_delay_seconds)


class Watcher:
    def __init__(self, ticker: str, pipeline: EarningsPipeline, sources: list[ArtifactSource], interval_seconds: float):
        self.ticker = ticker.upper()
        self.pipeline = pipeline
        self.sources = sources
        self.interval_seconds = interval_seconds

    def run(self) -> None:
        logger.info("watching %s sources=%s interval=%.1fs", self.ticker, ",".join(s.name for s in self.sources), self.interval_seconds)
        try:
            while True:
                loop_started = time.monotonic()
                for source in self.sources:
                    try:
                        self.pipeline.poll_source(source, self.ticker)
                    except Exception:
                        logger.exception("source poll failed ticker=%s source=%s", self.ticker, source.name)
                remaining = self.interval_seconds - (time.monotonic() - loop_started)
                if remaining > 0:
                    time.sleep(remaining)
        except KeyboardInterrupt:
            logger.info("watcher stopped cleanly")
