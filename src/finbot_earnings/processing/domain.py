"""Bounded v0 results, processing configuration and work identity."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from decimal import Decimal
import hashlib
import re
from typing import Protocol

from .contracts import ArtifactReference, FilingReady, fields, json_text, nonempty
from .errors import ContractError, TechnicalFailure

METRICS = {"gaap_diluted_eps", "adjusted_diluted_eps"}
PERIOD_KINDS = {"quarter", "half_year", "annual"}


@dataclass(frozen=True)
class ExtractionConfig:
    version: str
    model_id: str = "fixture"
    prompt_version: str = "eps-v0"
    schema_version: str = "eps-v0"
    validation_policy: str = "explicit-prose-v1"
    max_documents: int = 16
    max_input_bytes: int = 4 * 1024 * 1024
    max_response_bytes: int = 64 * 1024
    max_facts: int = 32
    max_stage_failures: int = 3
    lease_seconds: int = 300
    max_output_tokens: int = 4096

    def __post_init__(self):
        for name in ("version", "model_id", "prompt_version", "schema_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,200}", value):
                raise ValueError(f"invalid {name}")
        if self.validation_policy != "explicit-prose-v1" or self.schema_version != "eps-v0":
            raise ValueError("unsupported validation policy or schema")
        bounds = {"max_documents": 100, "max_input_bytes": 64 * 1024 * 1024,
                  "max_response_bytes": 256 * 1024, "max_facts": 100,
                  "max_stage_failures": 10, "lease_seconds": 3600, "max_output_tokens": 16384}
        for name, maximum in bounds.items():
            if type(getattr(self, name)) is not int or not 1 <= getattr(self, name) <= maximum:
                raise ValueError(f"invalid {name}")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class WorkIdentity:
    filing_id: str
    snapshot_id: str
    extraction_config_version: str
    run_mode: str = "production"
    run_id: str = "initial"

    def __post_init__(self):
        if self.run_mode not in {"production", "evaluation"}:
            raise ValueError("run_mode must be production or evaluation")
        if not isinstance(self.run_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", self.run_id):
            raise ValueError("invalid run_id")

    @property
    def work_id(self):
        return hashlib.sha256(json_text(asdict(self)).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Document:
    reference: ArtifactReference
    body: bytes


@dataclass(frozen=True)
class ModelRequest:
    filing: FilingReady
    documents: tuple[Document, ...]
    config: ExtractionConfig


@dataclass(frozen=True)
class ModelResult:
    response: dict
    model_id: str
    usage: dict


class DocumentSource(Protocol):
    def read(self, artifact: ArtifactReference, *, max_bytes: int) -> bytes:
        """Return immutable stored bytes with bounded I/O; raise TechnicalFailure on failure."""
        ...


class FilingModel(Protocol):
    def classify_and_extract(self, request: ModelRequest) -> ModelResult: ...


class EventPublisher(Protocol):
    def publish(self, payload: str) -> str:
        """Return an acknowledgment ID or raise TechnicalFailure; retries reuse payload."""
        ...


@dataclass(frozen=True)
class Fact:
    metric: str
    value: str
    currency: str
    period_kind: str
    period_end: str
    period_label: str
    source_artifact_id: str
    evidence: str

    @classmethod
    def parse(cls, value):
        fields(value, ("metric", "value", "currency", "period", "source_artifact_id", "evidence"))
        fields(value["period"], ("kind", "end_date", "label"))
        if value["metric"] not in METRICS or value["period"]["kind"] not in PERIOD_KINDS:
            raise ContractError("unknown metric or reporting period kind")
        if not isinstance(value["value"], str) or not re.fullmatch(r"[+-]?(?:0|[1-9]\d*)(?:\.\d+)?", value["value"]):
            raise ContractError("value must be a signed decimal string")
        if len(value["value"]) > 40:
            raise ContractError("EPS value exceeds bound")
        if not isinstance(value["currency"], str) or not re.fullmatch(r"[A-Z]{3}", value["currency"]):
            raise ContractError("currency must be a code")
        end = value["period"]["end_date"]
        if not isinstance(end, str) or date.fromisoformat(end).isoformat() != end:
            raise ContractError("invalid period end")
        for name, item, bound in (("period label", value["period"]["label"], 200),
                                   ("source_artifact_id", value["source_artifact_id"], 1000),
                                   ("evidence", value["evidence"], 2000)):
            nonempty(item, name)
            if len(item) > bound:
                raise ContractError(f"{name} exceeds bound")
        return cls(metric=value["metric"], value=value["value"], currency=value["currency"],
                   period_kind=value["period"]["kind"], period_end=end,
                   period_label=value["period"]["label"], source_artifact_id=value["source_artifact_id"],
                   evidence=value["evidence"])

    @property
    def period_key(self):
        return self.period_kind + ":" + self.period_end

    def to_dict(self):
        return dict(metric=self.metric, value=self.value, currency=self.currency,
                    period=dict(kind=self.period_kind, end_date=self.period_end, label=self.period_label),
                    source_artifact_id=self.source_artifact_id, evidence=self.evidence)


def economic_value(fact):
    return Decimal(fact["value"]), fact["currency"]


def response_facts(response, config):
    try:
        fields(response, ("classification", "facts"))
        if response["classification"] not in {"reports_earnings", "does_not_report_earnings", "uncertain"}:
            raise ContractError("unknown classification")
        if not isinstance(response["facts"], list) or len(response["facts"]) > config.max_facts:
            raise ContractError("facts must be a bounded array")
        return tuple(Fact.parse(value) for value in response["facts"])
    except (ValueError, TypeError, KeyError, OverflowError) as exc:
        raise TechnicalFailure("invalid_model_response", retryable=False) from exc


@dataclass(frozen=True)
class ProcessResult:
    work_id: str | None
    outcome: str
    acknowledge: bool
    findings: tuple[dict, ...] = ()
    publications: tuple[tuple[str, int], ...] = ()
    exhausted: bool = False
