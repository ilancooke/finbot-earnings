import json
from types import SimpleNamespace

import pytest

from finbot_earnings.processing import lambda_handler
from finbot_earnings.processing.fiscal_consumer import FiscalResult
from tests.processing_helpers import fixture

QUEUE = "arn:aws:sqs:us-east-1:123456789012:earnings"
TOPIC = "arn:aws:sns:us-east-1:123456789012:filing-ready"
CONTEXT = SimpleNamespace(get_remaining_time_in_millis=lambda: 300_000)


@pytest.fixture
def runtime(monkeypatch):
    class Worker:
        calls = []
        result = FiscalResult("work", "accepted", True)
        def process(self, message, **kwargs):
            self.calls.append((message, kwargs))
            return self.result
    worker = Worker()
    monkeypatch.setenv("EARNINGS_QUEUE_ARN", QUEUE)
    monkeypatch.setenv("FILING_READY_TOPIC_ARN", TOPIC)
    monkeypatch.setattr(lambda_handler, "runtime", lambda: worker)
    return worker


def record(identifier="message", **changes):
    payload, _ = fixture()
    return dict(messageId=identifier, eventSource="aws:sqs", eventSourceARN=QUEUE,
        body=json.dumps(dict(Type="Notification", TopicArn=TOPIC, Message=json.dumps(payload))), **changes)


def test_success_and_semantic_reviews_acknowledge(runtime):
    for outcome in ("accepted", "review_required", "no_eps_extracted"):
        runtime.result = FiscalResult("work", outcome, True)
        assert lambda_handler.handler({"Records": [record()]}, CONTEXT) == {"batchItemFailures": []}
    assert all(not kwargs for _, kwargs in runtime.calls)


def test_retry_busy_and_terminal_return_partial_batch_failure(runtime):
    for outcome in ("retry", "busy", "processing_failed"):
        runtime.result = FiscalResult("work", outcome, False)
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


@pytest.mark.parametrize("event", [
    dict(operation="evaluate", filing=fixture()[0], run_id="model-comparison-1"),
    fixture()[0],
    dict(Records=[]),
])
def test_only_sqs_batches_are_supported(runtime, event):
    with pytest.raises(ValueError, match="Expected nonempty SQS records"):
        lambda_handler.handler(event, CONTEXT)
    assert not runtime.calls


def test_remaining_time_budget_defers_without_starting_model(runtime):
    result = lambda_handler.handler({"Records": [record()]}, SimpleNamespace(get_remaining_time_in_millis=lambda: 20_000))
    assert result["batchItemFailures"] and not runtime.calls


def test_missing_message_id_rejects_whole_batch(runtime):
    item = record()
    del item["messageId"]
    with pytest.raises(ValueError):
        lambda_handler.handler({"Records": [item]}, CONTEXT)
