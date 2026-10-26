"""Real Responses SDK over offline HTTP, separate from the legacy consumer."""

from base64 import b64decode
from hashlib import sha256
from io import BytesIO
import json
from pathlib import Path

import httpx
from PIL import Image
import pytest

from finbot_earnings.processing.contracts import FilingReady
from finbot_earnings.processing.errors import TechnicalFailure
from finbot_earnings.processing.fiscal import OpenAIFiscalExtractor, load_config, make_client
from finbot_earnings.processing.fiscal.config import digest, local_schema, resource, transport_schema
from finbot_earnings.processing.fiscal.errors import ExtractionProblem
from finbot_earnings.processing.fiscal.html_text import plain_text_preview
from finbot_earnings.processing.fiscal.output import normalized_usage
from finbot_earnings.processing.fiscal.prepare import check_request, preflight, prepare
from finbot_earnings.processing.fiscal import config as fiscal_config
from tests.processing_helpers import Documents, fixture, rehash


def labels():
    return dict(reported_diluted_eps=[dict(value="-1.230", currency="USD", period_type="quarterly",
                                         fiscal_year=2026, fiscal_quarter=3)], adjusted_diluted_eps=[])


def native(value=None):
    return dict(id="resp_synthetic", object="response", status="completed", model="gpt-6-luna",
                error=None, incomplete_details=None,
                output=[dict(type="reasoning", summary=[]), dict(type="message", role="assistant", status="completed",
                        content=[dict(type="output_text", text=json.dumps(labels() if value is None else value))])],
                usage=dict(input_tokens=1000, output_tokens=100,
                           input_tokens_details=dict(cached_tokens=100, cache_write_tokens=200),
                           output_tokens_details=dict(reasoning_tokens=50)))


def image_bytes(kind="PNG", size=(16, 16)):
    stream = BytesIO()
    Image.new("RGB", size, "white").save(stream, format=kind)
    return stream.getvalue()


def snapshot(extra=(), images=0):
    payload, bodies, _ = fixture()
    accession = payload["filing_id"]
    for name, raw, mime in [*extra, *[(f"page-{i:03}.png", image_bytes(), "image/png") for i in range(images)]]:
        artifact_id = accession + "/" + name
        bodies[artifact_id] = raw
        payload["artifacts"].append(dict(artifact_id=artifact_id, filename=name,
            s3_uri="s3://artifacts/" + artifact_id, size_bytes=len(raw), content_type=mime))
    return FilingReady.parse(rehash(payload)), Documents(bodies)


def adapter(handler):
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = make_client("synthetic-offline-key", http_client=http)
    return OpenAIFiscalExtractor(client), client


def test_real_sdk_exact_settings_complete_order_images_and_receipt():
    filing, source = snapshot(extra=[("table.htm", b'<table><tr><th>FY2026 Q3</th><td>-1.230</td></tr></table><script>DROP</script>', "text/html")], images=34)
    seen = []
    result_body = json.dumps(native()).encode()
    def handler(request):
        assert str(request.url) == "https://api.openai.com/v1/responses"
        assert request.method == "POST"
        assert request.extensions["timeout"] == dict(connect=120, read=120, write=120, pool=120)
        value = json.loads(request.content)
        seen.append(request.content)
        assert set(value) == {"model", "instructions", "input", "text", "max_output_tokens", "reasoning",
                              "store", "truncation", "service_tier", "prompt_cache_options"}
        assert value["model"] == "gpt-6-luna" and value["max_output_tokens"] == 4096
        assert value["reasoning"] == {"effort": "medium"}
        assert value["store"] is False and value["truncation"] == "disabled"
        assert value["service_tier"] == "default"
        assert value["prompt_cache_options"] == {"mode": "implicit", "ttl": "30m"}
        assert value["instructions"] == resource("eps-v6.txt").decode() + "\n\nRequired JSON schema:\n" + json.dumps(local_schema())
        assert value["text"]["format"] == dict(type="json_schema", name="earnings_eps", strict=True, schema=transport_schema())
        content = value["input"][0]["content"]
        context = json.loads(content[0]["text"].removeprefix("Filing context: "))
        assert context == {key: getattr(filing, key) for key in ("filing_id", "ticker", "company_name", "form_type", "filed_at", "cik")}
        assert len(content) == 1 + 2 * len(filing.artifacts)
        for index, ref in enumerate(filing.artifacts):
            assert content[index * 2 + 1] == dict(type="input_text", text="Source attachment: " + ref.filename)
            block = content[index * 2 + 2]
            if ref.filename.endswith(".png"):
                assert block["detail"] == "high"
                assert b64decode(block["image_url"].split(",", 1)[1]) == source.bodies[ref.artifact_id]
            else:
                assert block["text"] == plain_text_preview(source.bodies[ref.artifact_id])
        assert "DROP" not in " ".join(b.get("text", "") for b in content)
        assert "FY2026 Q3 | -1.230 |" in content[-1]["text"]
        return httpx.Response(200, content=result_body, headers={"content-type": "application/json"})
    extractor, client = adapter(handler)
    try:
        receipt = extractor.extract(filing, source, run_id="fresh-001", attempt=2)
    finally:
        client.close()
    assert len(seen) == 1 and source.reads == [r.artifact_id for r in filing.artifacts]
    assert receipt["outcome"] == "extracted" and receipt["extraction"] == labels()
    assert receipt["input"] == filing.to_dict() and receipt["run_id"] == "fresh-001" and receipt["attempt"] == 2
    assert receipt["request"]["encoded_request_bytes"] == len(seen[0])
    assert receipt["request"]["sha256"] == digest(json.loads(seen[0]))
    assert receipt["request"]["image_count"] == 34
    assert receipt["response"] == native() and b64decode(receipt["response_body_base64"]) == result_body
    assert receipt["usage"]["inputTokens"] == 700 and receipt["usage"]["totalTokens"] == 1100
    assert receipt["usage"]["providerUsage"]["output_tokens_details"] == {"reasoning_tokens": 50}
    assert not receipt["usage_unknown"] and not receipt["retryable"]
    assert receipt["extraction_config_sha256"] == digest(load_config())
    assert receipt["timing"]["extraction_started_at"] <= receipt["timing"]["extraction_completed_at"]
    assert len(receipt["documents"]) == len(filing.artifacts)
    assert all(d["sha256"] == sha256(source.bodies[d["artifact_id"]]).hexdigest() for d in receipt["documents"])
    assert "synthetic-offline-key" not in json.dumps(receipt)


@pytest.mark.parametrize("kind", ["JPEG", "PNG", "GIF"])
def test_original_supported_image_formats(kind):
    extension = kind.lower()
    raw = image_bytes(kind)
    filing, source = snapshot(extra=[("page." + extension, raw, "image/" + extension)])
    blocks, _, _, count = prepare(filing, source, load_config())
    assert count == 1
    block = next(b for b in blocks if b["type"] == "input_image")
    assert block["image_url"] == f"data:image/{extension};base64," + __import__("base64").b64encode(raw).decode()


@pytest.mark.parametrize("name,mime", [("supplement.pdf", "application/pdf"), ("notes.txt", "text/plain"),
    ("extra.webp", "image/webp"), ("misleading.html", "application/pdf"), ("lie.pdf", "text/html")])
def test_unsupported_member_reviews_whole_snapshot_before_io_or_provider(name, mime):
    filing, source = snapshot(extra=[(name, b"unsupported", mime), ("second.txt", b"also unsupported", "text/plain")])
    extractor, client = adapter(lambda r: pytest.fail("provider called"))
    try:
        result = extractor.extract(filing, source)
    finally:
        client.close()
    assert result["outcome"] == "review_required" and not result["provider_called"] and not source.reads
    assert len(result["reasons"]) == 2
    assert all(r["code"] == "unsupported_selected_format" and r["artifact_id"] for r in result["reasons"])


@pytest.mark.parametrize("kind", ["corrupt", "wrong_format", "animated"])
def test_invalid_images_reject_complete_request(kind):
    raw = b"invalid" if kind == "corrupt" else image_bytes("JPEG")
    if kind == "animated":
        stream = BytesIO()
        Image.new("RGB", (2, 2), "red").save(stream, format="GIF", save_all=True,
                                              append_images=[Image.new("RGB", (2, 2), "blue")])
        raw = stream.getvalue()
    name, mime = ("page.gif", "image/gif") if kind == "animated" else ("page.png", "image/png")
    filing, source = snapshot(extra=[(name, raw, mime)])
    extractor, client = adapter(lambda r: pytest.fail("provider called"))
    try:
        result = extractor.extract(filing, source)
    finally:
        client.close()
    assert result["outcome"] == "review_required" and result["reasons"][0]["code"] == "invalid_selected_image"


@pytest.mark.parametrize("bound", ["max_documents", "max_images", "max_document_bytes", "max_image_bytes",
                                  "max_source_bytes", "max_image_total_bytes"])
def test_manifest_bounds_identify_actual_limit_and_members(bound):
    filing, _ = snapshot(images=34)
    limits = load_config()["input_limits"]
    limits[bound] = 0
    with pytest.raises(ExtractionProblem) as caught:
        preflight(filing, limits)
    reason = next(r for r in caught.value.reasons if r["bound"] == bound)
    assert caught.value.outcome == "review_required" and reason["actual"] > reason["limit"] == 0
    assert reason.get("artifact_id") or reason.get("artifact_ids")


@pytest.mark.parametrize("bound", ["max_text_bytes", "max_image_pixels", "max_image_dimension"])
def test_prepared_bounds_reject_without_truncation(bound):
    filing, source = snapshot(images=1)
    config = load_config()
    config["input_limits"][bound] = 1
    with pytest.raises(ExtractionProblem) as caught:
        prepare(filing, source, config)
    assert caught.value.reasons[0]["bound"] == bound


@pytest.mark.parametrize("bound", ["max_encoded_request_bytes", "max_input_token_estimate"])
def test_request_bounds_prevent_oversized_complete_dispatch(bound):
    filing, _ = snapshot()
    config = load_config()
    config["input_limits"][bound] = 1
    with pytest.raises(ExtractionProblem) as caught:
        check_request(dict(instructions="long text", text={}, input=[dict(content=[])]), filing, config, 34)
    assert caught.value.reasons[0]["bound"] == bound


def test_source_mismatch_cannot_enter_inference():
    filing, source = snapshot()
    source.bodies[filing.artifacts[0].artifact_id] += b"changed"
    extractor, client = adapter(lambda r: pytest.fail("provider called"))
    try:
        result = extractor.extract(filing, source)
    finally:
        client.close()
    assert result["reasons"][0]["code"] == "source_size_mismatch" and result["retryable"]


@pytest.mark.parametrize("failure,code,retryable", [(FileNotFoundError("sensitive"), "source_object_missing", True),
    (TechnicalFailure("unexpected_source_bucket", retryable=False), "source_read_failed", False)])
def test_source_failures_keep_safe_retry_classification(failure, code, retryable):
    class FailedSource:
        def read(self, ref, *, max_bytes):
            raise failure
    filing, _ = snapshot()
    extractor, client = adapter(lambda r: pytest.fail("provider called"))
    try:
        result = extractor.extract(filing, FailedSource())
    finally:
        client.close()
    assert not result["provider_called"] and result["retryable"] is retryable
    assert result["reasons"][0]["code"] == code and "sensitive" not in json.dumps(result)


def test_invalid_html_encoding_is_reviewed_without_silent_replacement():
    filing, source = snapshot(extra=[("invalid.html", b'<meta charset="utf-8"><p>EPS \xff</p>', "text/html")])
    extractor, client = adapter(lambda r: pytest.fail("provider called"))
    try:
        result = extractor.extract(filing, source)
    finally:
        client.close()
    assert result["outcome"] == "review_required"
    assert result["reasons"][0]["code"] == "unsupported_document_encoding"


@pytest.mark.parametrize("value", [{}, {"classification": "earnings"}, [],
    {"reported_diluted_eps": [], "adjusted_diluted_eps": [], "extra": True},
    {"reported_diluted_eps": [{**labels()["reported_diluted_eps"][0], "value": 1.23}], "adjusted_diluted_eps": []},
    {"reported_diluted_eps": [{**labels()["reported_diluted_eps"][0], "fiscal_quarter": True}], "adjusted_diluted_eps": []},
    {"reported_diluted_eps": [{**labels()["reported_diluted_eps"][0], "fiscal_year": 2026.0}], "adjusted_diluted_eps": []},
    {"reported_diluted_eps": [{**labels()["reported_diluted_eps"][0], "period_type": "annual"}], "adjusted_diluted_eps": []}])
def test_schema_invalid_output_retains_full_response_without_retry(value):
    extractor, client = adapter(lambda r: httpx.Response(200, json=native(value)))
    try:
        result = extractor.extract(*snapshot())
    finally:
        client.close()
    assert result["outcome"] == "processing_failed" and not result["retryable"]
    assert result["reasons"][0]["code"] == "invalid_model_response"
    assert result["response"] == native(value) and result["response_body_base64"]


@pytest.mark.parametrize("text", ['not json', '{"reported_diluted_eps":[],"reported_diluted_eps":[],"adjusted_diluted_eps":[]}',
                                '{"reported_diluted_eps":[],"adjusted_diluted_eps":NaN}'])
def test_malformed_json_is_terminal(text):
    response = native()
    response["output"][1]["content"][0]["text"] = text
    extractor, client = adapter(lambda r: httpx.Response(200, json=response))
    try:
        result = extractor.extract(*snapshot())
    finally:
        client.close()
    assert result["reasons"][0]["code"] == "invalid_model_response" and not result["retryable"]


@pytest.mark.parametrize("case,code,outcome", [("incomplete", "incomplete_model_output", "review_required"),
    ("refusal", "provider_refusal", "review_required"), ("tool", "invalid_model_response", "processing_failed"),
    ("multiple", "invalid_model_response", "processing_failed")])
def test_unacceptable_provider_envelopes(case, code, outcome):
    response = native()
    if case == "incomplete":
        response["status"] = "incomplete"
    elif case == "refusal":
        response["output"][1]["content"] = [dict(type="refusal", refusal="test")]
    elif case == "tool":
        response["output"].append(dict(type="function_call"))
    else:
        response["output"].append(response["output"][1])
    extractor, client = adapter(lambda r: httpx.Response(200, json=response))
    try:
        result = extractor.extract(*snapshot())
    finally:
        client.close()
    assert result["outcome"] == outcome and result["reasons"][0]["code"] == code
    assert result["response"] == response and not result["retryable"]


@pytest.mark.parametrize("value", [dict(reported_diluted_eps=[], adjusted_diluted_eps=[]),
    dict(reported_diluted_eps=[dict(value="4.500", currency="TWD", period_type="annual", fiscal_year=2027, fiscal_quarter=None)], adjusted_diluted_eps=[])])
def test_valid_empty_annual_and_precision_are_returned_without_legacy_fields(value):
    extractor, client = adapter(lambda r: httpx.Response(200, json=native(value)))
    try:
        result = extractor.extract(*snapshot())
    finally:
        client.close()
    assert result["outcome"] == "extracted" and result["extraction"] == value


@pytest.mark.parametrize("status,code,retryable", [(429, "rate_limit_exceeded", True), (500, "server_error", True),
    (408, "timeout", True), (400, "invalid_request_error", False), (401, "invalid_api_key", False),
    (429, "insufficient_quota", False)])
def test_provider_failures_are_safe_single_attempts(status, code, retryable):
    calls = []
    def handler(request):
        calls.append(1)
        return httpx.Response(status, json={"error": {"code": code, "message": "SENSITIVE_DO_NOT_SAVE"}},
                              headers={"x-request-id": "req_synthetic123"})
    extractor, client = adapter(handler)
    try:
        result = extractor.extract(*snapshot())
        exhausted = extractor.extract(*snapshot(), attempt=3)
    finally:
        client.close()
    assert len(calls) == 2  # exactly one HTTP attempt per extraction invocation
    assert result["retryable"] is retryable and exhausted["retryable"] is False
    assert result["usage_unknown"] is True
    assert result["reasons"][0]["code"] == ("provider_transient_failure" if retryable else "provider_configuration_failure")
    assert "SENSITIVE_DO_NOT_SAVE" not in json.dumps(result)
    assert result["reasons"][0]["provider_request_id"] == "req_synthetic123"


def test_connection_failure_does_not_retry_or_claim_zero_usage():
    calls = []
    def handler(request):
        calls.append(1)
        raise httpx.ConnectTimeout("SENSITIVE_DO_NOT_SAVE", request=request)
    extractor, client = adapter(handler)
    try:
        result = extractor.extract(*snapshot())
        with pytest.raises(ValueError, match="attempt"):
            extractor.extract(*snapshot(), attempt=4)
    finally:
        client.close()
    assert len(calls) == 1 and result["usage_unknown"] and result["retryable"]
    assert "SENSITIVE_DO_NOT_SAVE" not in json.dumps(result)


def test_native_response_body_is_bounded_before_parsing():
    limit = load_config()["persistence_limits"]["max_response_bytes"]
    extractor, client = adapter(lambda r: httpx.Response(200, content=b" " * (limit + 1)))
    try:
        result = extractor.extract(*snapshot())
    finally:
        client.close()
    assert result["outcome"] == "processing_failed" and result["reasons"][0]["bound"] == "max_response_bytes"
    assert result["response"] is None and result["response_body_base64"] is None
    assert result["usage_unknown"] and not result["retryable"]


@pytest.mark.parametrize("body", [b'\xff', b'{"bad":1e999}', b'{"bad":"\\ud800"}', b'[]',
                                  b'{"status":"completed","status":"completed"}'])
def test_invalid_native_json_remains_inspectable(body):
    extractor, client = adapter(lambda r: httpx.Response(200, content=body))
    try:
        result = extractor.extract(*snapshot())
    finally:
        client.close()
    assert result["outcome"] == "processing_failed" and result["reasons"][0]["code"] == "invalid_model_response"
    assert b64decode(result["response_body_base64"]) == body


def test_default_image_count_bound_rejects_before_source_reads():
    filing, source = snapshot(images=65)
    extractor, client = adapter(lambda r: pytest.fail("provider called"))
    try:
        result = extractor.extract(filing, source)
    finally:
        client.close()
    assert not source.reads and not result["provider_called"]
    reason = result["reasons"][0]
    assert reason["bound"] == "max_images" and reason["actual"] == 65 and reason["limit"] == 64


def test_code_and_dependency_drift_fail_closed(monkeypatch):
    monkeypatch.setattr(fiscal_config.metadata, "version", lambda _: "unexpected")
    with pytest.raises(ValueError, match="dependency version mismatch"):
        load_config()


@pytest.mark.parametrize("usage", [None, {}, {"input_tokens": True, "output_tokens": 100},
    {"input_tokens": 1, "output_tokens": -1}, {"input_tokens": 1, "output_tokens": 1, "input_tokens_details": {"cached_tokens": 2}}])
def test_missing_usage_is_unknown(usage):
    assert "inputTokens" not in normalized_usage(dict(usage=usage))


def test_frozen_port_resources_and_schema_identity():
    config = load_config()
    assert config["prompt_sha256"] == "54158e06ec22a876acb0272bc1674bdd5dbf0f5a489eb7d9c8c3e65fdaf40237"
    assert config["response_schema_sha256"] == "658af83969c4712a81c7a523fb79c0f56a2e9255a71b3ced3ed9441f3f312d94"
    assert local_schema() == json.loads(Path("docs/contracts/earnings_eps_fiscal_v2.schema.json").read_text())
    assert config["transport_schema_sha256"] == digest(transport_schema())
    schema = transport_schema()
    assert "$schema" not in schema and "allOf" not in schema["$defs"]["observation"]
    quarterly, annual = schema["$defs"]["observation"]["anyOf"]
    assert quarterly["properties"]["fiscal_quarter"] == {"type": "integer", "enum": [1, 2, 3, 4]}
    assert annual["properties"]["fiscal_quarter"] == {"type": "null"}


def test_frozen_html_parity_fixtures():
    cases = json.loads(Path("tests/fixtures/fiscal_html_parity.json").read_text())
    for case in cases["cases"]:
        assert plain_text_preview(b64decode(case["source_base64"])) == case["expected_text"], case["name"]
