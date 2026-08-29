from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from ..clock import utc_now
from ..models import ArtifactType, DiscoveredArtifact, SourceProvider
from .base import ArtifactSource, HTTPFetcher

SEC_DATA_ROOT = "https://data.sec.gov"
SEC_ARCHIVES_ROOT = "https://www.sec.gov/Archives/edgar/data"
SEC_ACCEPTANCE_TIMEZONE = ZoneInfo("America/New_York")


@dataclass(frozen=True)
class Filing:
    accession_number: str
    form: str
    primary_document: str
    filing_date: str
    acceptance_datetime: str | None
    items: str
    primary_doc_description: str


def classify_form(form: str) -> ArtifactType | None:
    normalized = form.upper().strip()
    return {
        "8-K": ArtifactType.SEC_8K,
        "10-Q": ArtifactType.SEC_10Q,
        "10-K": ArtifactType.SEC_10K,
    }.get(normalized)


def recent_filings(payload: dict[str, Any]) -> list[Filing]:
    recent = payload.get("filings", {}).get("recent", {})
    required = ("accessionNumber", "form", "primaryDocument", "filingDate")
    if not all(isinstance(recent.get(key), list) for key in required):
        return []
    count = min(len(recent[key]) for key in required)
    result: list[Filing] = []
    for index in range(count):
        form = str(recent["form"][index])
        if classify_form(form) is None:
            continue
        def optional(key: str) -> str:
            values = recent.get(key, [])
            return str(values[index]) if index < len(values) and values[index] is not None else ""
        result.append(Filing(
            accession_number=str(recent["accessionNumber"][index]), form=form,
            primary_document=str(recent["primaryDocument"][index]),
            filing_date=str(recent["filingDate"][index]),
            acceptance_datetime=optional("acceptanceDateTime") or None,
            items=optional("items"), primary_doc_description=optional("primaryDocDescription"),
        ))
    return result


def exhibit_type(filename: str) -> ArtifactType | None:
    compact = filename.lower().replace("_", "-")
    if "cfo" in compact and "commentary" in compact:
        return ArtifactType.CFO_COMMENTARY
    if re.search(r"(?:ex|exhibit)[-_.]?99[-_.]?1", compact):
        return ArtifactType.EXHIBIT_99_1
    if re.search(r"(?:ex|exhibit)[-_.]?99[-_.]?2", compact):
        return ArtifactType.CFO_COMMENTARY
    # NVIDIA's real filing directory uses names such as q1fy27pr.htm rather
    # than encoding EX-99.1 in the filename. This is only applied after an
    # Item 2.02 filing has already been identified.
    if "pressrelease" in compact or re.search(r"q\d+fy\d+pr\.(?:htm|html)$", compact):
        return ArtifactType.EXHIBIT_99_1
    return None


class SECSource(ArtifactSource):
    name = "sec"

    def __init__(self, ticker: str, cik: str, fetcher: HTTPFetcher, *, max_filings: int = 40):
        if not fetcher.user_agent.strip() or "@" not in fetcher.user_agent:
            raise ValueError("SEC_USER_AGENT must identify the application and include a contact email")
        self.ticker = ticker.upper()
        self.cik = cik.zfill(10)
        self.fetcher = fetcher
        self.max_filings = max_filings
        self._exhibit_cache: dict[str, list[tuple[str, ArtifactType, dict[str, Any]]]] = {}

    @property
    def submissions_url(self) -> str:
        return f"{SEC_DATA_ROOT}/submissions/CIK{self.cik}.json"

    def poll(self) -> list[DiscoveredArtifact]:
        response = self.fetcher.get(self.submissions_url, {"Accept": "application/json"})
        payload = json.loads(response.body)
        detected_at = utc_now()
        discoveries: list[DiscoveredArtifact] = []
        for filing in recent_filings(payload)[: self.max_filings]:
            kind = classify_form(filing.form)
            if kind is None:
                continue
            accession_compact = filing.accession_number.replace("-", "")
            cik_number = str(int(self.cik))
            base_url = f"{SEC_ARCHIVES_ROOT}/{cik_number}/{accession_compact}"
            published_at = self._acceptance_time(filing.acceptance_datetime)
            metadata = {
                "form": filing.form, "items": filing.items, "filing_date": filing.filing_date,
                "primary_doc_description": filing.primary_doc_description,
            }
            discoveries.append(DiscoveredArtifact(
                ticker=self.ticker, provider=SourceProvider.SEC, artifact_type=kind,
                url=f"{base_url}/{filing.primary_document}", detected_at=detected_at,
                published_at=published_at, title=filing.primary_doc_description or filing.form,
                cik=self.cik, accession_number=filing.accession_number,
                filename=filing.primary_document, metadata=metadata,
            ))
            if kind == ArtifactType.SEC_8K and "2.02" in filing.items:
                discoveries.extend(self._exhibits(base_url, filing, detected_at, published_at, metadata))
        return discoveries

    def _exhibits(
        self, base_url: str, filing: Filing, detected_at: Any, published_at: Any,
        filing_metadata: dict[str, str],
    ) -> list[DiscoveredArtifact]:
        cached = self._exhibit_cache.get(filing.accession_number)
        if cached is None:
            response = self.fetcher.get(f"{base_url}/index.json", {"Accept": "application/json"})
            payload = json.loads(response.body)
            cached = []
            for item in payload.get("directory", {}).get("item", []):
                filename = str(item.get("name", ""))
                kind = exhibit_type(filename)
                if kind is not None:
                    cached.append((filename, kind, item))
            self._exhibit_cache[filing.accession_number] = cached
        discoveries: list[DiscoveredArtifact] = []
        for filename, kind, item in cached:
            discoveries.append(DiscoveredArtifact(
                ticker=self.ticker, provider=SourceProvider.SEC, artifact_type=kind,
                url=f"{base_url}/{filename}", detected_at=detected_at, published_at=published_at,
                title="SEC earnings exhibit" if kind == ArtifactType.EXHIBIT_99_1 else "SEC CFO commentary exhibit",
                cik=self.cik, accession_number=filing.accession_number, filename=filename,
                metadata={**filing_metadata, "directory_item": item},
            ))
        return discoveries

    @staticmethod
    def _acceptance_time(value: str | None):
        """Convert the SEC acceptance clock reading to UTC.

        The submissions feed marks acceptanceDateTime with ``Z``, but the
        observed value is an Eastern-time wall-clock reading.  Treating that
        suffix as UTC understates the acceptance time by four or five hours.
        ``ZoneInfo`` handles the EDT/EST transition for us.
        """
        if not value:
            return None
        try:
            if len(value) == 14 and value.isdigit():
                wall_time = datetime.strptime(value, "%Y%m%d%H%M%S")
            else:
                # Deliberately discard the feed's timezone marker: the clock
                # components themselves are in America/New_York.
                wall_time = datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            return wall_time.replace(tzinfo=SEC_ACCEPTANCE_TIMEZONE).astimezone(timezone.utc)
        except ValueError:
            return None
