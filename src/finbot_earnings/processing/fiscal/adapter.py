"""One OpenAI request per complete snapshot attempt, no SDK/adapter retry loop.

Receipts are returned to a caller for durable storage, not written to legacy
stores. A persisted application claim must budget each attempt before calling.
"""

from base64 import b64encode
from datetime import datetime, timezone
import json
import re
import time

import httpx
import openai

from ..contracts import FilingReady, utc_text
from .config import digest, load_config, local_schema, resource, transport_schema
from .errors import ExtractionProblem, problem
from .output import normalized_usage, parse_output, strict_json
from .prepare import check_request, prepare

MAX_PROVIDER_ATTEMPTS = 3


def make_client(api_key, *, http_client=None):
    """Explicit credential injection; never load .env or choose another endpoint."""
    if not isinstance(api_key, str) or not api_key.strip():
        raise ValueError("OpenAI project credential is required")
    return openai.OpenAI(api_key=api_key, base_url="https://api.openai.com/v1",
                         timeout=120, max_retries=0, http_client=http_client)


def provider_problem(error):
    # Error messages, headers and bodies can contain secrets or source text.
    # Inspect only the narrow machine code to prevent blind billing retries.
    body = getattr(error, "body", None)
    item = body.get("error", body) if isinstance(body, dict) else {}
    code = item.get("code") if isinstance(item, dict) else None
    status = getattr(error, "status_code", None)
    transient = (isinstance(error, (openai.APIConnectionError, openai.APITimeoutError))
                 or status in {408, 409, 429} or type(status) is int and status >= 500)
    if code in {"insufficient_quota", "billing_hard_limit_reached", "billing_not_active", "invalid_api_key"}:
        transient = False
    details = {"http_status": status} if type(status) is int else {}
    request_id = getattr(error, "request_id", None)
    if isinstance(request_id, str) and re.fullmatch(r"req_[A-Za-z0-9]{8,80}", request_id):
        details["provider_request_id"] = request_id
    return problem("provider_transient_failure" if transient else "provider_configuration_failure",
                   "extraction", retryable=transient, **details)


class OpenAIFiscalExtractor:
    """Transition API; returns schema-valid EPS, never a legacy ModelResult.

    extract(filing, source, run_id='initial', attempt=1) returns a JSON-compatible
    receipt. `extracted` means structural validity only; M3 owns business-rule
    acceptance, empty completion, immutable events and all durable checkpoints.
    """

    def __init__(self, client):
        self._config = load_config()
        if str(client.base_url).rstrip("/") != self._config["endpoint"]:
            raise ValueError("unsupported OpenAI endpoint")
        # Enforce even on injected SDK clients. No environment/constructor default
        # retries may multiply the persisted application's three-attempt budget.
        self.client = client.with_options(max_retries=0, timeout=120)

    @property
    def config(self):
        return json.loads(json.dumps(self._config))

    def extract(self, filing, source, *, run_id="initial", attempt=1):
        if not isinstance(run_id, str) or not re.fullmatch(r"[A-Za-z0-9._-]{1,100}", run_id):
            raise ValueError("invalid run_id")
        if type(attempt) is not int or not 1 <= attempt <= MAX_PROVIDER_ATTEMPTS:
            raise ValueError("provider attempt must be persisted and between 1 and 3")
        # Accept only the validated upstream boundary, never ad hoc document lists.
        if not isinstance(filing, FilingReady):
            raise ValueError("validated FilingReady required")
        filing = FilingReady.parse(filing.to_dict())
        config = self.config
        receipt = dict(receipt_schema_version=1, input=filing.to_dict(), extraction_config=config,
                       extraction_config_sha256=digest(config), run_id=run_id, attempt=attempt,
                       outcome="processing_failed", reasons=[], retryable=False, provider_called=False,
                       retry_policy=dict(max_provider_attempts=MAX_PROVIDER_ATTEMPTS, sdk_max_retries=0),
                       response=None, response_body_base64=None, extraction=None, usage={}, usage_unknown=False,
                       documents=[], request={}, timing={})
        started = time.monotonic()
        extraction_started = None
        try:
            content, inventory, text_bytes, images = prepare(filing, source, config)
            receipt["documents"] = inventory
            settings = config["request_settings"]
            parameters = dict(
                model=config["model"],
                instructions=resource("eps-v6.txt").decode("utf-8") + "\n\nRequired JSON schema:\n" + json.dumps(local_schema()),
                input=[dict(role="user", content=content)],
                text=dict(format=dict(type="json_schema", name="earnings_eps", strict=True, schema=transport_schema())),
                max_output_tokens=settings["max_output_tokens"], reasoning=dict(effort=settings["reasoning_effort"]),
                store=settings["store"], truncation=settings["truncation"], service_tier=settings["service_tier"],
                prompt_cache_options=settings["prompt_cache_options"],
            )
            receipt["request"] = {**check_request(parameters, filing, config, images),
                                  "sha256": digest(parameters),
                                  "prepared_text_bytes": text_bytes, "image_count": images}
            receipt["timing"]["preparation_ms"] = round((time.monotonic() - started) * 1000)
            receipt["timing"]["extraction_started_at"] = utc_text(datetime.now(timezone.utc))
            extraction_started = time.monotonic()
            receipt["provider_called"] = True
            receipt["usage_unknown"] = True
            # Stream and bound the native body before JSON parsing or persistence.
            # Overflow is terminal and explicit; no prefix is treated as a result.
            body = bytearray()
            limit = config["persistence_limits"]["max_response_bytes"]
            with self.client.responses.with_streaming_response.create(**parameters) as result:
                for chunk in result.iter_bytes(chunk_size=8192):
                    if len(body) + len(chunk) > limit:
                        raise problem("invalid_model_response", "response", bound="max_response_bytes",
                                      actual=len(body) + len(chunk), limit=limit)
                    body.extend(chunk)
            receipt["response_body_base64"] = b64encode(body).decode("ascii")
            try:
                native = strict_json(bytes(body))
            except (ValueError, UnicodeError, RecursionError):
                raise problem("invalid_model_response", "response") from None
            receipt["response"] = native
            if not isinstance(native, dict):
                raise problem("invalid_model_response", "response")
            receipt["usage"] = normalized_usage(native)
            receipt["usage_unknown"] = "inputTokens" not in receipt["usage"]
            receipt["extraction"] = parse_output(native, config)
            receipt["outcome"] = "extracted"
        except openai.APIError as error:
            failure = provider_problem(error)
            receipt.update(outcome=failure.outcome, reasons=failure.reasons,
                           retryable=failure.retryable and attempt < MAX_PROVIDER_ATTEMPTS)
        except (httpx.TimeoutException, httpx.NetworkError, httpx.RemoteProtocolError):
            receipt.update(outcome="processing_failed", reasons=[dict(code="provider_transient_failure", stage="extraction")],
                           retryable=attempt < MAX_PROVIDER_ATTEMPTS)
        except ExtractionProblem as failure:
            receipt.update(outcome=failure.outcome, reasons=failure.reasons,
                           retryable=failure.retryable and attempt < MAX_PROVIDER_ATTEMPTS)
        finally:
            if extraction_started is not None:
                receipt["timing"]["extraction_completed_at"] = utc_text(datetime.now(timezone.utc))
                receipt["timing"]["extraction_ms"] = round((time.monotonic() - extraction_started) * 1000)
            receipt["timing"]["total_ms"] = round((time.monotonic() - started) * 1000)
        return receipt
