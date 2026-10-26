"""AWS clients are injected/stubbed. No secret/provider/network access."""
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
import json

import boto3
from botocore.stub import Stubber
import httpx
import pytest

from finbot_earnings.processing import fiscal_runtime, lambda_handler
from finbot_earnings.processing.contracts import FilingReady, json_text
from finbot_earnings.processing.errors import TechnicalFailure
from finbot_earnings.processing.fiscal import make_client
from finbot_earnings.processing.fiscal.config import digest, load_config
from finbot_earnings.processing.fiscal_stores import SQLiteFiscalRepository
from finbot_earnings.processing.operator import execute, main, parser
from tests.processing_helpers import fixture, Documents
from tests.test_fiscal_extractor import native

SECRET = "arn:aws:secretsmanager:us-east-1:123456789012:secret:earnings-openai-abcdef"
TOPIC = "arn:aws:sns:us-east-1:123456789012:output"
UPSTREAM = "arn:aws:sns:us-east-1:123456789012:filing-ready"


def environment(monkeypatch):
    for key, value in dict(EARNINGS_TABLE_NAME="earnings", EARNINGS_SOURCE_BUCKET="artifacts",
        EARNINGS_TOPIC_ARN=TOPIC, FILING_READY_TOPIC_ARN=UPSTREAM, EARNINGS_QUEUE_ARN="arn:aws:sqs:us-east-1:123456789012:input",
        EARNINGS_OPENAI_SECRET_ARN=SECRET, EARNINGS_FISCAL_CONFIG_SHA256=digest(load_config())).items():
        monkeypatch.setenv(key, value)


def test_lazy_runtime_frozen_configuration_bounded_clients_and_no_secret_on_import(monkeypatch):
    environment(monkeypatch)
    lambda_handler.runtime.cache_clear()
    try:
        runtime = lambda_handler.runtime()
        assert lambda_handler.runtime() is runtime
        assert isinstance(runtime.extractor, fiscal_runtime.SecretFiscalExtractor)
        assert runtime.extractor.secrets.meta.config.read_timeout == 10
        assert runtime.documents.client.meta.config.retries["total_max_attempts"] == 2
        assert runtime.repository.table_name == "earnings"
        assert runtime.config == load_config()
        monkeypatch.setenv("EARNINGS_FISCAL_CONFIG_SHA256", "wrong")
        with pytest.raises(ValueError, match="digest"): fiscal_runtime.build_consumer()
    finally:
        lambda_handler.runtime.cache_clear()


def test_secret_sdk_access_and_actual_adapter_over_mocked_http(monkeypatch, tmp_path):
    environment(monkeypatch)
    session = boto3.Session(region_name="us-east-1")
    secrets = session.client("secretsmanager")
    with Stubber(secrets) as stub:
        stub.add_response("get_secret_value", dict(SecretString="offline-project-credential"), dict(SecretId=SECRET, VersionStage="AWSCURRENT"))
        extractor = fiscal_runtime.SecretFiscalExtractor(secrets, SECRET)
        calls = []
        def client(key):
            assert key == "offline-project-credential"
            return make_client(key, http_client=httpx.Client(transport=httpx.MockTransport(
                lambda request: (calls.append(request), httpx.Response(200, json=native()))[1])))
        import finbot_earnings.processing.fiscal as boundary
        monkeypatch.setattr(boundary, "make_client", client)
        payload, bodies, _ = fixture()
        receipt = extractor.extract(FilingReady.parse(payload), Documents(bodies), attempt=1)
        assert receipt["outcome"] == "extracted" and len(calls) == 1
        assert "offline-project-credential" not in json_text(receipt)
        stub.assert_no_pending_responses()


def test_secret_failure_budget_and_cli_errors_do_not_expose_credentials(monkeypatch, tmp_path, capsys):
    environment(monkeypatch)
    repo = SQLiteFiscalRepository(tmp_path / "jobs.sqlite3")
    try:
        consumer = fiscal_runtime.build_consumer(repo)
        consumer.extractor.secrets = Mock()
        consumer.extractor.secrets.get_secret_value.side_effect = RuntimeError("sensitive-private-key")
        payload, _, _ = fixture()
        result = consumer.process(payload)
        assert not result.acknowledge
        job = repo.get_job(result.work_id)
        assert len(job["attempts"]) == 1 and job["attempts"][0]["usage_unknown"]
        assert "sensitive-private-key" not in json_text(job)
        assert main(["--sqlite", str(tmp_path / "jobs.sqlite3"), "inspect", result.work_id]) == 0
        assert json.loads(capsys.readouterr().out)["work_id"] == result.work_id
        assert main(["--sqlite", str(tmp_path / "jobs.sqlite3"), "inspect", "missing"]) == 1
        assert json.loads(capsys.readouterr().err)["code"] == "operator_command_failed"
    finally:
        repo.close()


@pytest.mark.parametrize("error,expected,retryable", [("NoSuchKey", "source_object_missing", True), ("AccessDenied", "source_read_failed", False), ("SlowDown", "source_read_failed", True)])
def test_s3_client_errors_are_normalized_for_extractor(error, expected, retryable):
    source = boto3.client("s3", region_name="us-east-1")
    filing = FilingReady.parse(fixture()[0])
    ref = filing.artifacts[0]
    with Stubber(source) as stub:
        stub.add_client_error("get_object", service_error_code=error, service_message="private diagnostic",
            expected_params=dict(Bucket="artifacts", Key=ref.s3_uri.split("s3://artifacts/", 1)[1]))
        with pytest.raises(TechnicalFailure) as caught:
            fiscal_runtime.FiscalS3Documents(source, "artifacts").read(ref, max_bytes=10000)
        assert caught.value.code == expected and caught.value.retryable == retryable
        assert "private diagnostic" not in str(caught.value)


def test_output_cli_uses_receive_without_delete_and_keeps_transport_times():
    client = boto3.client("sqs", region_name="us-east-1")
    url = "https://sqs.us-east-1.amazonaws.com/123456789012/inspection"
    body = dict(Type="Notification", TopicArn=TOPIC, Message=json.dumps({"event_type": "earnings.extracted"}))
    with Stubber(client) as stub:
        stub.add_response("receive_message", dict(Messages=[dict(MessageId="delivery-001", Body=json.dumps(body),
            Attributes=dict(SentTimestamp="1790000000000", ApproximateReceiveCount="1"))]),
            dict(QueueUrl=url, MaxNumberOfMessages=2, VisibilityTimeout=0, WaitTimeSeconds=0,
                 MessageSystemAttributeNames=["SentTimestamp", "ApproximateReceiveCount"]))
        result = execute(parser().parse_args(["output", "--queue-url", url, "--limit", "2"]), None, sqs=client)
        assert result[0]["body"] == body and result[0]["attributes"]["SentTimestamp"] == "1790000000000"
        stub.assert_no_pending_responses()


def test_handler_runs_new_consumer_through_persisted_publication_and_duplicate(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from tests.test_fiscal_consumer import worker
    environment(monkeypatch)
    repo = SQLiteFiscalRepository(tmp_path / "jobs.sqlite3")
    try:
        consumer, payload = worker(repo)
        monkeypatch.setattr(lambda_handler, "runtime", lambda: consumer)
        record = dict(messageId="delivery", eventSource="aws:sqs", eventSourceARN="arn:aws:sqs:us-east-1:123456789012:input",
            body=json.dumps(dict(Type="Notification", TopicArn=UPSTREAM, Message=json.dumps(payload))))
        context = SimpleNamespace(get_remaining_time_in_millis=lambda: 300_000)
        for _ in range(2):
            assert lambda_handler.handler(dict(Records=[record]), context) == dict(batchItemFailures=[])
        assert len(consumer.calls) == len(consumer.publisher.payloads) == 1
        assert json.loads(consumer.publisher.payloads[0])["event_type"] == "earnings.extracted"
    finally:
        repo.close()
