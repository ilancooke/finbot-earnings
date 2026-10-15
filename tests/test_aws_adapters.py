from dataclasses import replace
from io import BytesIO
import json

import boto3
from botocore.response import StreamingBody
from botocore.stub import ANY, Stubber
import jsonschema
import pytest

from finbot_earnings.processing.aws_adapters import NovaLiteModel, NOVA_LITE_MODEL_ID, NOVA_PROMPT_VERSION, EPS_SCHEMA, S3Documents, SNSPublisher
from finbot_earnings.processing.contracts import FilingReady
from finbot_earnings.processing.domain import Document, ExtractionConfig, ModelRequest
from finbot_earnings.processing.errors import InputReview, TechnicalFailure
from tests.processing_helpers import fixture


def request():
    payload, bodies, _ = fixture()
    filing = FilingReady.parse(payload)
    return ModelRequest(filing, tuple(Document(ref, bodies[ref.artifact_id]) for ref in filing.artifacts),
                        ExtractionConfig("bedrock-test-v1", model_id=NOVA_LITE_MODEL_ID, prompt_version=NOVA_PROMPT_VERSION, max_output_tokens=2000))


def provider_response(value=None, stop="tool_use"):
    _, _, response = fixture()
    return dict(output={"message": {"role": "assistant", "content": [{"toolUse": {
        "toolUseId": "extraction-1", "name": "report_earnings", "input": response if value is None else value}}]}},
        stopReason=stop, usage={"inputTokens": 100, "outputTokens": 50, "totalTokens": 150}, metrics={"latencyMs": 20})


def test_s3_decodes_key_once_and_closes_stream():
    client = boto3.client("s3")
    artifact = replace(request().filing.artifacts[0], s3_uri="s3://artifacts/a%20b%2520%23%2B.htm", size_bytes=3)
    stream = BytesIO(b"abc")
    with Stubber(client) as stub:
        stub.add_response("get_object", {"Body": StreamingBody(stream, 3), "ContentLength": 3},
                          {"Bucket": "artifacts", "Key": "a b%20#+.htm"})
        assert S3Documents(client, "artifacts").read(artifact, max_bytes=3) == b"abc"
        stub.assert_no_pending_responses()
    assert stream.closed


def test_s3_bounds_bucket_and_mismatch_fail_safely():
    client = boto3.client("s3")
    artifact = request().filing.artifacts[0]
    with Stubber(client) as stub:
        with pytest.raises(TechnicalFailure, match="unexpected_source_bucket"):
            S3Documents(client, "other").read(artifact, max_bytes=1000)
        with pytest.raises(TechnicalFailure, match="stored_object_exceeds_limit"):
            S3Documents(client, "artifacts").read(artifact, max_bytes=1)
        stream = BytesIO(b"abc")
        stub.add_response("get_object", {"Body": StreamingBody(stream, 3), "ContentLength": 3})
        with pytest.raises(TechnicalFailure, match="stored_object_size_mismatch"):
            S3Documents(client, "artifacts").read(artifact, max_bytes=1000)
    assert stream.closed


def test_sns_publishes_exact_saved_payload_and_requires_ack():
    client = boto3.client("sns")
    topic = "arn:aws:sns:us-east-1:123456789012:earnings"
    payload = '{"schema_version":"1.0","literal":"é"}'
    with Stubber(client) as stub:
        stub.add_response("publish", {"MessageId": "ack"}, {"TopicArn": topic, "Message": payload})
        assert SNSPublisher(client, topic).publish(payload) == "ack"
        stub.add_response("publish", {}, {"TopicArn": topic, "Message": payload})
        with pytest.raises(TechnicalFailure, match="missing_publication_acknowledgment"):
            SNSPublisher(client, topic).publish(payload)
        with pytest.raises(TechnicalFailure, match="publication_exceeds_limit"):
            SNSPublisher(client, topic).publish("é" * (256 * 1024))


def test_nova_forced_tool_and_original_html_text_pdf_in_one_request():
    client, seen = boto3.client("bedrock-runtime"), []
    client.meta.events.register("before-parameter-build.bedrock-runtime.Converse", lambda params, **kwargs: seen.append(params))
    supplied = request()
    html, text, pdf = supplied.documents
    text = replace(text, reference=replace(text.reference, filename="release.txt"), body=b"Apple financial results")
    pdf = replace(pdf, reference=replace(pdf.reference, filename="supplement.pdf"), body=b"%PDF-1.7\n\xff\xfe")
    supplied = replace(supplied, documents=(html, text, pdf))
    with Stubber(client) as stub:
        stub.add_response("converse", provider_response(), dict(modelId=NOVA_LITE_MODEL_ID, system=ANY, messages=ANY,
            inferenceConfig={"maxTokens": 2000}, toolConfig={"tools": [{"toolSpec": {
                "name": "report_earnings", "description": ANY, "inputSchema": {"json": EPS_SCHEMA}}}],
                "toolChoice": {"tool": {"name": "report_earnings"}}}))
        result = NovaLiteModel(client).classify_and_extract(supplied)
        stub.assert_no_pending_responses()
    assert len(seen) == 1
    content = seen[0]["messages"][0]["content"]
    context = json.loads(content[0]["text"])
    assert len(context["documents"]) == 3
    for metadata, block, doc, format in zip(context["documents"], content[1:], supplied.documents, ("html", "txt", "pdf")):
        assert metadata["artifact_id"] == doc.reference.artifact_id
        assert metadata["filename"] == doc.reference.filename
        assert block["document"] == {"format": format, "name": metadata["name"], "source": {"bytes": doc.body}}
    assert result.usage == {"input_tokens": 100, "output_tokens": 50}
    jsonschema.Draft202012Validator.check_schema(EPS_SCHEMA)
    jsonschema.validate(result.response, EPS_SCHEMA)


@pytest.mark.parametrize("stop", ["end_turn", "max_tokens", "guardrail_intervened", "model_context_window_exceeded"])
def test_bedrock_incomplete_output_is_never_accepted(stop):
    client = boto3.client("bedrock-runtime")
    with Stubber(client) as stub:
        stub.add_response("converse", provider_response(stop=stop))
        with pytest.raises(TechnicalFailure, match="bedrock_incomplete_output") as caught:
            NovaLiteModel(client).classify_and_extract(request())
        assert not caught.value.retryable


def test_nova_schema_invalid_tool_input_retained_for_terminal_validation():
    client = boto3.client("bedrock-runtime")
    with Stubber(client) as stub:
        stub.add_response("converse", provider_response(value={"unexpected": "value"}))
        result = NovaLiteModel(client).classify_and_extract(request())
        assert result.response == {"unexpected": "value"}


@pytest.mark.parametrize("kind", ["missing", "wrong_name", "multiple", "not_object"])
def test_nova_rejects_invalid_tool_responses(kind):
    client = boto3.client("bedrock-runtime")
    response = provider_response()
    content = response["output"]["message"]["content"]
    if kind == "missing":
        content[:] = [{"text": "No extraction"}]
    elif kind == "wrong_name":
        content[0]["toolUse"]["name"] = "other_tool"
    elif kind == "multiple":
        content.append(content[0])
    else:
        content[0]["toolUse"]["input"] = []
    with Stubber(client) as stub:
        stub.add_response("converse", response)
        with pytest.raises(TechnicalFailure, match="invalid_bedrock_output"):
            NovaLiteModel(client).classify_and_extract(request())


def test_nova_accepts_commentary_alongside_single_tool_call():
    client = boto3.client("bedrock-runtime")
    response = provider_response()
    response["output"]["message"]["content"].insert(0, {"text": "Extraction follows."})
    with Stubber(client) as stub:
        stub.add_response("converse", response)
        assert NovaLiteModel(client).classify_and_extract(request()).response == fixture()[2]


@pytest.mark.parametrize("kind,code", [("count", "too_many_documents"), ("size", "document_exceeds_provider_limit"),
                                      ("format", "unsupported_document_format")])
def test_nova_provider_input_limits_before_inference(kind, code):
    supplied = request()
    if kind == "count":
        supplied = replace(supplied, documents=supplied.documents * 2)
    elif kind == "size":
        supplied = replace(supplied, documents=(replace(supplied.documents[0], body=b"a" * 4_500_001),))
    else:
        doc = supplied.documents[0]
        supplied = replace(supplied, documents=(replace(doc, reference=replace(doc.reference, filename="input.zip")),))
    with Stubber(boto3.client("bedrock-runtime")) as stub:
        with pytest.raises(InputReview, match=code):
            NovaLiteModel(stub.client).classify_and_extract(supplied)
        stub.assert_no_pending_responses()


@pytest.mark.parametrize("change,code", [({"model_id": "other"}, "unsupported_model"),
                                        ({"prompt_version": "eps-v0"}, "unsupported_prompt_version")])
def test_nova_configuration_is_explicit(change, code):
    supplied = request()
    with Stubber(boto3.client("bedrock-runtime")) as stub:
        with pytest.raises(TechnicalFailure, match=code):
            NovaLiteModel(stub.client).classify_and_extract(replace(supplied, config=replace(supplied.config, **change)))


@pytest.mark.parametrize("error,terminal", [("ValidationException", True), ("AccessDeniedException", True), ("ThrottlingException", False)])
def test_bedrock_retry_policy_distinguishes_configuration_from_throttling(error, terminal):
    client = boto3.client("bedrock-runtime")
    with Stubber(client) as stub:
        stub.add_client_error("converse", service_error_code=error, service_message="provider detail", http_status_code=400)
        if terminal:
            with pytest.raises(TechnicalFailure) as caught:
                NovaLiteModel(client).classify_and_extract(request())
            assert not caught.value.retryable
        else:
            with pytest.raises(client.exceptions.ThrottlingException):
                NovaLiteModel(client).classify_and_extract(request())
