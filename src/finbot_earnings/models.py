from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from .clock import ensure_utc, isoformat


class SourceProvider(StrEnum):
    NVIDIA_IR = "nvidia_ir"
    SEC = "sec"
    SEC_COMPANY_FACTS = "sec_company_facts"


class ArtifactType(StrEnum):
    IR_EARNINGS_RELEASE = "ir_earnings_release"
    SEC_8K = "sec_8k"
    EXHIBIT_99_1 = "exhibit_99_1"
    CFO_COMMENTARY = "cfo_commentary"
    SEC_10Q = "sec_10q"
    SEC_10K = "sec_10k"
    COMPANY_FACTS = "company_facts"
    UNKNOWN = "unknown"


class ProcessingState(StrEnum):
    DISCOVERED = "discovered"
    DOWNLOADED = "downloaded"
    PERSISTED = "persisted"
    PARSED = "parsed"
    EXTRACTION_PENDING = "extraction_pending"
    EXTRACTING = "extracting"
    EXTRACTED = "extracted"
    FAILED = "failed"


@dataclass(frozen=True)
class DiscoveredArtifact:
    ticker: str
    provider: SourceProvider
    artifact_type: ArtifactType
    url: str
    detected_at: datetime
    published_at: datetime | None = None
    title: str | None = None
    cik: str | None = None
    accession_number: str | None = None
    filename: str | None = None
    external_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        object.__setattr__(self, "ticker", self.ticker.upper())
        ensure_utc(self.detected_at)
        ensure_utc(self.published_at)


@dataclass(frozen=True)
class DownloadedArtifact:
    discovery: DiscoveredArtifact
    body: bytes
    download_started_at: datetime
    downloaded_at: datetime
    status_code: int
    headers: dict[str, str]
    final_url: str


@dataclass
class ArtifactRecord:
    artifact_id: str
    identity_key: str
    ticker: str
    event_id: str
    provider: SourceProvider
    artifact_type: ArtifactType
    source_url: str
    content_hash: str
    raw_path: str
    state: ProcessingState
    published_at: datetime | None
    detected_at: datetime
    download_started_at: datetime
    downloaded_at: datetime
    parse_started_at: datetime | None = None
    parsed_at: datetime | None = None
    extraction_started_at: datetime | None = None
    extraction_completed_at: datetime | None = None
    structured_data_ready_at: datetime | None = None
    accession_number: str | None = None
    filename: str | None = None
    retry_count: int = 0
    error_stage: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ParsedArtifact:
    artifact_id: str
    ticker: str
    artifact_type: ArtifactType
    source_url: str
    title: str | None
    text: str
    tables: list[list[list[str]]]
    parser_version: str
    parsed_at: datetime


@dataclass(frozen=True)
class EarningsFact:
    canonical_name: str
    reported_label: str
    value_raw: str
    value_numeric: int | float | None
    unit: str | None
    period_raw: str | None
    gaap_status: str | None
    source_artifact_id: str
    source_locator: str | None = None


@dataclass(frozen=True)
class GuidanceItem:
    canonical_name: str
    value_raw: str
    value_numeric: int | float | None
    unit: str | None
    period_raw: str | None
    range_low: int | float | None = None
    range_high: int | float | None = None
    gaap_status: str | None = None
    source_artifact_id: str = ""
    source_locator: str | None = None


@dataclass(frozen=True)
class EarningsExtraction:
    ticker: str
    fiscal_period_raw: str | None
    facts: list[EarningsFact]
    guidance: list[GuidanceItem]
    highlights: list[str]
    source_artifact_id: str
    prompt_version: str
    schema_version: str
    model: str
    provider: str
    parser_version: str
    usage: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_provider_dict(
        cls, data: dict[str, Any], *, artifact: ParsedArtifact, prompt_version: str,
        schema_version: str, model: str, provider: str, usage: dict[str, Any] | None = None,
    ) -> "EarningsExtraction":
        if not isinstance(data, dict) or not isinstance(data.get("facts"), list) or not isinstance(data.get("guidance"), list):
            raise ValueError("provider output does not match extraction schema")
        fact_fields = set(EarningsFact.__dataclass_fields__) - {"source_artifact_id"}
        guidance_fields = set(GuidanceItem.__dataclass_fields__) - {"source_artifact_id"}
        facts = []
        for item in data["facts"]:
            cls._validate_item(item, fact_fields, {"canonical_name", "reported_label", "value_raw"})
            facts.append(EarningsFact(**{k: item[k] for k in fact_fields}, source_artifact_id=artifact.artifact_id))
        guidance = []
        for item in data["guidance"]:
            cls._validate_item(item, guidance_fields, {"canonical_name", "value_raw"})
            guidance.append(GuidanceItem(**{k: item[k] for k in guidance_fields}, source_artifact_id=artifact.artifact_id))
        highlights = data.get("highlights", [])
        if not all(isinstance(item, str) for item in highlights):
            raise ValueError("highlights must be strings")
        return cls(
            ticker=str(data.get("ticker") or artifact.ticker).upper(),
            fiscal_period_raw=data.get("fiscal_period_raw"), facts=facts, guidance=guidance,
            highlights=highlights, source_artifact_id=artifact.artifact_id,
            prompt_version=prompt_version, schema_version=schema_version, model=model,
            provider=provider, parser_version=artifact.parser_version, usage=usage or {},
        )

    @staticmethod
    def _validate_item(item: Any, fields: set[str], string_fields: set[str]) -> None:
        if not isinstance(item, dict) or set(item) != fields:
            raise ValueError(f"extraction item requires exactly: {sorted(fields)}")
        if any(not isinstance(item[name], str) or not item[name] for name in string_fields):
            raise ValueError(f"required extraction strings must be non-empty: {sorted(string_fields)}")
        for name in {"value_numeric", "range_low", "range_high"} & fields:
            value = item[name]
            if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))):
                raise ValueError(f"{name} must be numeric or null")


def jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return isoformat(value)
    if isinstance(value, StrEnum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return {key: jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(item) for item in value]
    return value
