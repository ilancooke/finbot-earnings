import json
from types import SimpleNamespace

import pytest

from finbot_earnings.processing import lambda_handler
from finbot_earnings.processing.domain import ProcessResult
from tests.processing_helpers import fixture

QUEUE = "arn:aws:sqs:us-east-1:123456789012:earnings"
TOPIC = "arn:aws:sns:us-east-1:123456789012:filing-ready"
CONTEXT = SimpleNamespace(get_remaining_time_in_millis=lambda: 300_000)


@pytest.fixture
def runtime(monkeypatch):
    class Worker:
        calls = []
        result = ProcessResult("work", "validated", True)
        def process(self, message, **kwargs):
            self.calls.append((message, kwargs))
            return self.result
    worker = Worker()
    monkeypatch.setenv("EARNINGS_QUEUE_ARN", QUEUE)
    monkeypatch.setenv("FILING_READY_TOPIC_ARN", TOPIC)
    monkeypatch.setattr(lambda_handler, "runtime", lambda: worker)
    return worker


def record(identifier="message", **changes):
    payload, _, _ = fixture()
    return dict(messageId=identifier, eventSource="aws:sqs", eventSourceARN=QUEUE,
        body=json.dumps(dict(Type="Notification", TopicArn=TOPIC, Message=json.dumps(payload))), **changes)


def test_success_and_semantic_reviews_acknowledge(runtime):
    for outcome in ("validated", "review_required", "no_relevant_earnings"):
        runtime.result = ProcessResult("work", outcome, True)
        assert lambda_handler.handler({"Records": [record()]}, CONTEXT) == {"batchItemFailures": []}
    assert all(not kwargs for _, kwargs in runtime.calls)


def test_retry_busy_and_terminal_return_partial_batch_failure(runtime):
    for outcome in ("retry", "busy", "processing_failed"):
        runtime.result = ProcessResult("work", outcome, False)
        assert lambda_handler.handler({"Records": [record()]}, CONTEXT) == {
            "batchItemFailures": [{"itemIdentifier": "message"}]}


def test_bad_origin_and_malformed_record_do_not_reach_pipeline(runtime):
    for field, value in (("eventSourceARN", "other-queue"), ("body", "bad json"), ("body", "{}")):
        item = record()
        item[field] = value
        assert lambda_handler.handler({"Records": [item]}, CONTEXT)["batchItemFailures"]
    assert not runtime.calls


def test_unexpected_failure_retries_only_affected_records(runtime):
    def process(message, **kwargs):
        if len(runtime.calls) == 0:
            runtime.calls.append(message)
            raise OSError("secret provider detail")
        return runtime.result
    runtime.process = process
    result = lambda_handler.handler({"Records": [record("first"), record("second")]}, CONTEXT)
    assert result == {"batchItemFailures": [{"itemIdentifier": "first"}]}


def test_evaluation_is_explicit_and_always_isolated(runtime):
    payload, _, _ = fixture()
    result = lambda_handler.handler(dict(operation="evaluate", filing=payload, run_id="model-comparison-1"), CONTEXT)
    assert result["acknowledge"]
    assert runtime.calls[0][1] == {"run_mode": "evaluation", "run_id": "model-comparison-1"}
    with pytest.raises(ValueError):
        lambda_handler.handler(payload, CONTEXT)


def test_remaining_time_budget_defers_without_starting_model(runtime):
    result = lambda_handler.handler({"Records": [record()]}, SimpleNamespace(get_remaining_time_in_millis=lambda: 20_000))
    assert result["batchItemFailures"] and not runtime.calls


def test_missing_message_id_rejects_whole_batch(runtime):
    item = record()
    del item["messageId"]
    with pytest.raises(ValueError):
        lambda_handler.handler({"Records": [item]}, CONTEXT)


def test_runtime_builds_reusable_clients_with_bounded_sdk_timeouts(monkeypatch):
    from finbot_earnings.processing.domain import ExtractionConfig
    from finbot_earnings.processing.contracts import json_text
    monkeypatch.setenv("EARNINGS_EXTRACTION_CONFIG", json_text(ExtractionConfig("aws-test", model_id="amazon.nova-lite-v1:0", prompt_version="eps-nova-tool-v1").to_dict()))
    for key, value in {"EARNINGS_TABLE_NAME": "earnings", "EARNINGS_SOURCE_BUCKET": "artifacts",
        "EARNINGS_TOPIC_ARN": TOPIC, "FILING_READY_TOPIC_ARN": TOPIC, "EARNINGS_QUEUE_ARN": QUEUE}.items():
        monkeypatch.setenv(key, value)
    lambda_handler.runtime.cache_clear()
    try:
        first = lambda_handler.runtime()
        assert lambda_handler.runtime() is first
        assert first.model.client.meta.service_model.service_name == "bedrock-runtime"
        assert first.model.client.meta.config.retries["total_max_attempts"] == 1
        assert first.model.client.meta.config.read_timeout == 180
        assert first.documents.client.meta.config.read_timeout == 10
    finally:
        lambda_handler.runtime.cache_clear()
