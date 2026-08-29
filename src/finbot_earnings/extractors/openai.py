from __future__ import annotations

import json
import os
from typing import Any

from ..models import EarningsExtraction, ParsedArtifact
from .base import EarningsExtractor, PermanentExtractionError, TransientExtractionError

PROMPT_VERSION = "earnings-flash-v1"
SCHEMA_VERSION = "earnings-extraction-v1"

SYSTEM_PROMPT = """Extract only explicitly reported earnings information from the supplied official artifact.
Prioritize revenue, net income, GAAP/non-GAAP diluted EPS, gross margin, operating income,
prominent business/segment revenue, and explicit next-quarter or other major guidance.
Do not infer missing numbers. Preserve each source representation in value_raw. value_numeric
must use the base unit (for example, 46.7 billion USD becomes 46700000000) or null if ambiguous.
Use a compact deterministic source locator such as a heading/table/nearby label, not a long quotation.
Represent company segments generically using canonical_name such as segment_revenue:data_center."""

_NULLABLE_NUMBER = {"type": ["number", "null"]}
_NULLABLE_STRING = {"type": ["string", "null"]}

FACT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "canonical_name": {"type": "string"}, "reported_label": {"type": "string"},
        "value_raw": {"type": "string"}, "value_numeric": _NULLABLE_NUMBER,
        "unit": _NULLABLE_STRING, "period_raw": _NULLABLE_STRING,
        "gaap_status": _NULLABLE_STRING, "source_locator": _NULLABLE_STRING,
    },
    "required": ["canonical_name", "reported_label", "value_raw", "value_numeric", "unit", "period_raw", "gaap_status", "source_locator"],
}

GUIDANCE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "canonical_name": {"type": "string"}, "value_raw": {"type": "string"},
        "value_numeric": _NULLABLE_NUMBER, "unit": _NULLABLE_STRING,
        "period_raw": _NULLABLE_STRING, "range_low": _NULLABLE_NUMBER,
        "range_high": _NULLABLE_NUMBER, "gaap_status": _NULLABLE_STRING,
        "source_locator": _NULLABLE_STRING,
    },
    "required": ["canonical_name", "value_raw", "value_numeric", "unit", "period_raw", "range_low", "range_high", "gaap_status", "source_locator"],
}

EXTRACTION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "ticker": {"type": "string"},
        "fiscal_period_raw": _NULLABLE_STRING,
        "facts": {"type": "array", "items": FACT_SCHEMA},
        "guidance": {"type": "array", "items": GUIDANCE_SCHEMA},
        "highlights": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["ticker", "fiscal_period_raw", "facts", "guidance", "highlights"],
}


class OpenAIEarningsExtractor(EarningsExtractor):
    provider = "openai"
    display_name = "OpenAI"

    def __init__(self, model: str, client: Any | None = None):
        self.model = model
        if client is None:
            if not os.environ.get("OPENAI_API_KEY"):
                raise ValueError("OPENAI_API_KEY is required for OpenAI extraction")
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise RuntimeError("install the project dependencies to use OpenAI extraction") from exc
            client = OpenAI()
        self.client = client

    def extract(self, artifact: ParsedArtifact) -> EarningsExtraction:
        input_text = (
            f"Ticker: {artifact.ticker}\nArtifact type: {artifact.artifact_type.value}\n"
            f"Source URL: {artifact.source_url}\nTitle: {artifact.title or ''}\n\n{artifact.text}"
        )
        try:
            response = self.client.responses.create(
                model=self.model,
                instructions=SYSTEM_PROMPT,
                input=input_text,
                text={"format": {
                    "type": "json_schema", "name": "earnings_extraction",
                    "strict": True, "schema": EXTRACTION_SCHEMA,
                }},
                store=False,
            )
            output_text = response.output_text
            if not output_text:
                raise PermanentExtractionError("OpenAI response contained no output text")
            data = json.loads(output_text)
            usage = self._usage(response)
            return EarningsExtraction.from_provider_dict(
                data, artifact=artifact, prompt_version=PROMPT_VERSION,
                schema_version=SCHEMA_VERSION, model=self.model, provider=self.provider,
                usage=usage,
            )
        except PermanentExtractionError:
            raise
        except (json.JSONDecodeError, TypeError, ValueError, KeyError) as exc:
            raise PermanentExtractionError(f"invalid structured extraction: {exc}") from exc
        except Exception as exc:
            status_code = getattr(exc, "status_code", None)
            if status_code is not None and 400 <= int(status_code) < 500 and int(status_code) != 429:
                raise PermanentExtractionError(str(exc)) from exc
            raise TransientExtractionError(str(exc)) from exc

    @staticmethod
    def _usage(response: Any) -> dict[str, Any]:
        usage = getattr(response, "usage", None)
        if usage is None:
            return {}
        if hasattr(usage, "model_dump"):
            return usage.model_dump(mode="json")
        if isinstance(usage, dict):
            return usage
        return {
            key: getattr(usage, key) for key in ("input_tokens", "output_tokens", "total_tokens")
            if getattr(usage, key, None) is not None
        }
