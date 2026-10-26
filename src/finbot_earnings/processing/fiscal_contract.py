"""Fiscal acceptance and filing-specific identity; no independent fact verification."""
from dataclasses import dataclass
import re

from jsonschema import Draft202012Validator

from .contracts import timestamp, utc_text
from .fiscal.config import digest, local_schema


@dataclass(frozen=True)
class FiscalIdentity:
    filing_id: str
    snapshot_id: str
    extraction_config_version: str
    extraction_config_sha256: str
    run_id: str = "initial"
    namespace: str = "earnings.extracted/1.0"

    def __post_init__(self):
        if not isinstance(self.run_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", self.run_id):
            raise ValueError("invalid run_id")

    def to_dict(self):
        return vars(self).copy()

    @property
    def suffix(self):
        return digest(self.to_dict())

    @property
    def work_id(self):
        return "earnings-work:v2:" + self.suffix

    @property
    def record_ref(self):
        return "earnings-processing:v2:" + self.suffix

    @property
    def event_id(self):
        return "earnings.extracted:1.0:" + self.suffix


def accept(extraction):
    error = next(Draft202012Validator(local_schema()).iter_errors(extraction), None)
    if error:
        return "processing_failed", [dict(code="invalid_model_response", stage="response", path=list(error.absolute_path))]
    periods, reasons = set(), []
    for metric, rows in extraction.items():
        seen = set()
        for index, row in enumerate(rows):
            path = [metric, index]
            if type(row["fiscal_year"]) is not int or (row["fiscal_quarter"] is not None and type(row["fiscal_quarter"]) is not int):
                return "processing_failed", [dict(code="invalid_model_response", stage="response", path=path)]
            period = (row["period_type"], row["fiscal_year"], row["fiscal_quarter"])
            periods.add(period)
            key = (row["currency"], period)
            if key in seen:
                reasons.append(dict(code="duplicate_observation", stage="acceptance", path=path))
            seen.add(key)
    if len(periods) > 1:
        reasons.append(dict(code="multiple_fiscal_periods", stage="acceptance"))
    if reasons:
        return "review_required", reasons
    return ("accepted" if periods else "no_eps_extracted"), []


def make_event(job, receipt, now):
    identity = FiscalIdentity(**job["identity"])
    config, source = job["extraction_config"], job["input"]
    timing = receipt["timing"]
    start, end = timing["extraction_started_at"], timing["extraction_completed_at"]
    if not timestamp(start) <= timestamp(end) <= now:
        raise ValueError("invalid extraction timestamp ordering")
    return dict(event_type="earnings.extracted", schema_version="1.0", event_id=identity.event_id,
        issuer={k: source[k] for k in ("cik", "ticker", "company_name")},
        source={**{k: source[k] for k in ("filing_id", "snapshot_id", "form_type", "filed_at", "ready_at", "primary_artifact_id")},
                "manifest_ref": identity.record_ref + "/input"}, extraction=receipt["extraction"],
        processing=dict(work_id=identity.work_id, processing_record_ref=identity.record_ref, run_id=identity.run_id,
            extraction_config_version=config["version"], extraction_config_sha256=identity.extraction_config_sha256,
            **{k: config[k] for k in ("provider", "model", "prompt_version", "response_schema_version", "preparation_version", "acceptance_policy")}),
        extraction_started_at=start, extraction_completed_at=end, created_at=utc_text(now))
