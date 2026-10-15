from dataclasses import replace
from datetime import timedelta
import json

import boto3
import pytest
from moto import mock_aws

from finbot_earnings.processing.contracts import FilingReady
from finbot_earnings.processing.domain import ExtractionConfig, WorkIdentity
from finbot_earnings.processing.dynamodb_store import DynamoDBProcessingRepository
from finbot_earnings.processing.errors import StaleClaim, TechnicalFailure, WorkBusy, WorkConflict
from finbot_earnings.processing.validation import ValidationResult
from tests.processing_helpers import ADJUSTED, EVENT_ID, GAAP, NOW, Publisher, fixture
from tests.test_filing_processing import pipeline


@pytest.fixture
def repository():
    with mock_aws():
        resource = boto3.resource("dynamodb", region_name="us-east-1")
        resource.create_table(TableName="earnings", KeySchema=[{"AttributeName": name, "KeyType": kind}
            for name, kind in (("pk", "HASH"), ("sk", "RANGE"))],
            AttributeDefinitions=[{"AttributeName": name, "AttributeType": "S"} for name in ("pk", "sk")],
            BillingMode="PAY_PER_REQUEST")
        yield DynamoDBProcessingRepository(resource.meta.client, "earnings")


def claim(repository, sequence=1):
    payload, _, response = fixture(sequence)
    filing, config = FilingReady.parse(payload), ExtractionConfig("test-v1")
    identity = WorkIdentity(filing.filing_id, filing.snapshot_id, config.version)
    return repository.claim(filing, config, identity, NOW), response


def test_durable_processing_publication_recovery_and_duplicate(repository):
    publisher = Publisher(failures=1)
    worker, payload = pipeline(repository, publisher=publisher)
    first = worker.process(payload)
    assert first.outcome == "retry" and repository.event(EVENT_ID)["revision"] == 1
    restarted = DynamoDBProcessingRepository(repository.client, repository.table_name)
    resumed, _ = pipeline(restarted, publisher=publisher)
    result = resumed.process(payload)
    assert result.acknowledge and result.outcome == "validated"
    assert publisher.payloads[0] == publisher.payloads[1]
    assert not resumed.model.requests and not resumed.documents.reads
    assert resumed.process(payload) == result
    assert repository.get_job(result.work_id)["response"]["usage"]["input_tokens"] == 100
    assert not repository.pending_publications(result.work_id)


def test_claim_expiry_config_conflicts_and_stale_checkpoint(repository):
    job, _ = claim(repository)
    payload, _, _ = fixture()
    filing, config = FilingReady.parse(payload), ExtractionConfig("test-v1")
    identity = WorkIdentity(filing.filing_id, filing.snapshot_id, config.version)
    with pytest.raises(WorkBusy):
        repository.claim(filing, config, identity, NOW)
    with pytest.raises(WorkConflict):
        repository.claim(filing, replace(config, max_documents=2), identity, NOW)
    later = NOW + timedelta(seconds=301)
    second = repository.claim(filing, config, identity, later)
    assert second["claim_token"] != job["claim_token"]
    with pytest.raises(StaleClaim):
        repository.save_response(job["work_id"], job["claim_token"], {}, later)
    with pytest.raises(StaleClaim):
        repository.complete(job["work_id"], job["claim_token"], ValidationResult("review_required", ()), later)


def test_response_is_immutable_and_evaluation_cannot_publish(repository):
    worker, payload = pipeline(repository)
    result = worker.process(payload, run_mode="evaluation")
    assert result.acknowledge and result.outcome == "validated" and not result.publications
    assert repository.event(EVENT_ID) is None and not worker.publisher.payloads
    job, _ = claim(repository, 2)
    repository.save_response(job["work_id"], job["claim_token"], {"raw": "first"}, NOW)
    with pytest.raises(WorkConflict):
        repository.save_response(job["work_id"], job["claim_token"], {"raw": "different"}, NOW)


def test_racing_claimed_filings_enrich_then_reject_conflicts(repository, monkeypatch):
    first, response1 = claim(repository, 1)
    second, response2 = claim(repository, 2)
    # Force another worker to commit between this worker's read and its transaction.
    original = repository._transact
    raced = False
    def race(actions):
        nonlocal raced
        if not raced:
            raced = True
            other = DynamoDBProcessingRepository(repository.client, repository.table_name)
            other.complete(second["work_id"], second["claim_token"], ValidationResult("validated", (), (response2["facts"][1],)), NOW)
        return original(actions)
    monkeypatch.setattr(repository, "_transact", race)
    repository.complete(first["work_id"], first["claim_token"], ValidationResult("validated", (), (response1["facts"][0],)), NOW)
    assert repository.event(EVENT_ID)["revision"] == 2
    assert len(repository.event(EVENT_ID)["facts"]) == 2
    assert len(repository.event(EVENT_ID, 1)["facts"]) == 1
    conflict_payload, bodies, response = fixture(3, gaap=GAAP.replace("1.23", "9.99"))
    response["facts"][0]["value"] = "9.99"
    worker, _ = pipeline(repository, bodies=bodies, response=response)
    result = worker.process(conflict_payload)
    assert result.acknowledge and result.outcome == "review_required"
    assert repository.event(EVENT_ID)["revision"] == 2 and not worker.publisher.payloads


def test_conflict_for_second_period_does_not_partially_commit_first(repository, monkeypatch):
    job, response = claim(repository)
    annual = json.loads(json.dumps(response["facts"][0]))
    annual["period"]["kind"] = "annual"
    before = repository._transact
    def rejected(actions):
        # Invalid second operation forces the real API emulator to roll back all.
        actions.append({"ConditionCheck": dict(TableName="earnings", Key={"pk": "missing", "sk": "missing"},
                                               ConditionExpression="attribute_exists(pk)")})
        return before(actions)
    monkeypatch.setattr(repository, "_transact", rejected)
    with pytest.raises(TechnicalFailure):
        repository.complete(job["work_id"], job["claim_token"], ValidationResult("validated", (), (annual, response["facts"][0])), NOW)
    assert repository.event(EVENT_ID) is None
    assert repository.event("0000320193:annual:2026-09-30") is None
    assert repository.get_job(job["work_id"])["completion"] is None


def test_terminal_publication_requires_explicit_rearm(repository):
    publisher = Publisher(failures=3)
    worker, payload = pipeline(repository, publisher=publisher)
    for _ in range(3):
        result = worker.process(payload)
    assert result.exhausted and not result.acknowledge
    assert worker.process(payload).exhausted and len(publisher.payloads) == 3
    repository.rearm(result.work_id, NOW)
    assert worker.process(payload).acknowledge
    assert len(worker.model.requests) == 1 and len(publisher.payloads) == 4


def test_large_saved_record_rejected_before_any_partial_writes(repository):
    job, _ = claim(repository)
    with pytest.raises(TechnicalFailure, match="dynamodb_item_exceeds_limit"):
        repository.save_response(job["work_id"], job["claim_token"], {"large": "x" * (400 * 1024)}, NOW)
    assert repository.get_job(job["work_id"])["response"] is None
