"""Offline consumer/storage recovery matrix; actual SDK over mocked HTTP and moto."""
from base64 import b64decode
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import boto3
import httpx
from jsonschema import Draft202012Validator, FormatChecker
from moto import mock_aws
import pytest

from finbot_earnings.processing.contracts import FilingReady, json_text
from finbot_earnings.processing.errors import StaleClaim, TechnicalFailure, WorkBusy, WorkConflict
from finbot_earnings.processing.fiscal import OpenAIFiscalExtractor, load_config, make_client
from finbot_earnings.processing.fiscal.config import digest
from finbot_earnings.processing.fiscal_contract import FiscalIdentity, accept
from finbot_earnings.processing.fiscal_consumer import FiscalConsumer
from finbot_earnings.processing.fiscal_stores import SQLiteFiscalRepository, DynamoDBFiscalRepository
from finbot_earnings.processing.operator import execute, parser
from tests.processing_helpers import Documents, Publisher, fixture, rehash
from tests.test_fiscal_extractor import labels, native, snapshot


@pytest.fixture(params=["sqlite", "dynamodb"])
def repo(request, tmp_path):
    clock = [datetime.now(timezone.utc) + timedelta(seconds=1)]
    if request.param == "sqlite":
        store = SQLiteFiscalRepository(tmp_path / "processing.sqlite3", now=lambda: clock[0])
        store.clock = clock
        yield store
        store.close()
    else:
        with mock_aws():
            resource = boto3.resource("dynamodb", region_name="us-east-1")
            resource.create_table(TableName="earnings", KeySchema=[dict(AttributeName=n, KeyType=k) for n,k in (("pk", "HASH"), ("sk", "RANGE"))],
                AttributeDefinitions=[dict(AttributeName=n, AttributeType="S") for n in ("pk", "sk")], BillingMode="PAY_PER_REQUEST")
            store = DynamoDBFiscalRepository(resource.meta.client, "earnings", now=lambda: clock[0])
            store.clock = clock
            yield store


def worker(repo, response=None, *, publisher=None, transport=None, source=None):
    calls = []
    def handler(request):
        calls.append(json.loads(request.content))
        return transport(request) if transport else httpx.Response(200, json=native(labels() if response is None else response))
    extractor = OpenAIFiscalExtractor(make_client("offline-synthetic-key", http_client=httpx.Client(transport=httpx.MockTransport(handler))))
    payload, bodies = fixture()
    consumer = FiscalConsumer(repo, source or Documents(bodies), extractor, publisher or Publisher())
    consumer.calls = calls
    return consumer, payload


def test_end_to_end_duplicate_event_schema_decimal_refs_and_provenance(repo):
    consumer, payload = worker(repo)
    first = consumer.process(payload)
    assert first.acknowledge and first.outcome == "accepted"
    assert consumer.process(payload) == first and len(consumer.calls) == 1
    assert len(consumer.publisher.payloads) == 1 and len(consumer.documents.reads) == 3
    event = repo.event(first.event_id)
    schema = json.loads(Path("docs/contracts/earnings_extracted_v1.schema.json").read_text())
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(event)
    assert event["extraction"] == labels() and event["extraction"]["reported_diluted_eps"][0]["value"] == "-1.230"
    job = repo.get_job(first.work_id)
    assert job["record_schema_version"] == 2 and job["input"] == FilingReady.parse(payload).to_dict()
    assert job["extraction_config"] == load_config()
    receipt = job["attempts"][0]["receipt"]
    assert json.loads(b64decode(receipt["response_body_base64"])) == native()
    assert receipt["usage"]["totalTokens"] == 1100
    assert repo.get_job(event["source"]["manifest_ref"]) == job["input"]
    assert repo.get_job(event["processing"]["processing_record_ref"])["work_id"] == first.work_id
    assert repo.list_status("accepted")["items"][0]["published_at"]
    assert "offline-synthetic-key" not in json_text(job)


def test_different_filings_changed_snapshots_and_fresh_runs_independent_even_equal_eps(repo):
    consumer, payload = worker(repo)
    first = consumer.process(payload)
    later, bodies = fixture(2)
    consumer.documents = Documents(bodies)
    second = consumer.process(later)
    changed = deepcopy(later)
    changed["company_name"] += " Inc."
    rehash(changed)
    third = consumer.process(changed)
    consumer.documents = Documents(fixture()[1])
    fresh = consumer.process(payload, run_id="manual-001")
    assert all(x.acknowledge for x in (first, second, third, fresh))
    assert len({x.event_id for x in (first, second, third, fresh)}) == 4
    assert len(consumer.publisher.payloads) == 4
    assert repo.event(first.event_id)["extraction"] == repo.event(second.event_id)["extraction"]


@pytest.mark.parametrize("mode,expected", [("empty", "no_eps_extracted"), ("duplicate", "review_required"), ("period", "review_required"), ("invalid", "processing_failed")])
def test_business_and_schema_outcomes_never_publish(repo, mode, expected):
    value = labels()
    if mode == "empty": value = dict(reported_diluted_eps=[], adjusted_diluted_eps=[])
    if mode == "duplicate": value["reported_diluted_eps"] *= 2
    if mode == "period": value["adjusted_diluted_eps"] = [{**value["reported_diluted_eps"][0], "fiscal_quarter": 4}]
    if mode == "invalid": value["reported_diluted_eps"][0]["fiscal_quarter"] = True
    consumer, payload = worker(repo, value)
    first = consumer.process(payload)
    assert first.outcome == expected
    assert first.acknowledge == (expected != "processing_failed")
    assert not consumer.publisher.payloads
    consumer.process(payload)
    assert len(consumer.calls) == 1
    job = repo.get_job(first.work_id)
    assert repo.list_status(expected)["items"]
    assert job["attempts"][0]["receipt"]["response"]


def test_unsupported_mixed_and_oversized_whole_snapshots_before_inference(repo):
    for filing, source in (snapshot(extra=[("selected.pdf", b"%PDF-1", "application/pdf")]), snapshot()):
        payload = filing.to_dict()
        if not any(a["filename"].endswith(".pdf") for a in payload["artifacts"]):
            payload["artifacts"][0]["size_bytes"] = 17 * 1024 * 1024
            rehash(payload)
        consumer, _ = worker(repo, source=source)
        result = consumer.process(payload)
        assert result.outcome == "review_required" and result.acknowledge
        assert not consumer.calls and not source.reads and not consumer.publisher.payloads
        assert repo.get_job(result.work_id)["attempts"][0]["receipt"]["provider_called"] is False


def test_saved_publication_lost_ack_no_new_source_or_inference_and_redrive(repo):
    consumer, payload = worker(repo, publisher=Publisher(failures=3))
    for _ in range(3): result = consumer.process(payload)
    assert result.exhausted and not result.acknowledge
    assert repo.event(result.event_id) and len(consumer.calls) == 1
    assert len(consumer.publisher.payloads) == 3 and len(set(consumer.publisher.payloads)) == 1
    consumer.process(payload)
    assert len(consumer.publisher.payloads) == 3
    repo.rearm(result.work_id)
    reads = len(consumer.documents.reads)
    recovered = consumer.process(payload)
    assert recovered.outcome == "accepted" and recovered.acknowledge
    assert len(consumer.calls) == 1 and len(consumer.documents.reads) == reads
    assert len(set(consumer.publisher.payloads)) == 1
    job = repo.get_job(result.work_id)
    assert job["publication_attempts"] == 4 and job["published_at"] and job["acknowledgment"]
    assert not repo.list_status("processing_failed")["items"]


def test_transient_provider_attempts_durable_and_not_reset_by_rearm(repo):
    consumer, payload = worker(repo, transport=lambda _: httpx.Response(503, json={"error": {"message": "private diagnostic"}}))
    for ordinal in range(1, 4):
        result = consumer.process(payload)
        job = repo.get_job(result.work_id)
        assert len(job["attempts"]) == ordinal and job["attempts"][-1]["receipt"]["attempt"] == ordinal
    assert result.exhausted and len(consumer.calls) == 3
    assert all(a["usage_unknown"] for a in job["attempts"])
    repo.rearm(result.work_id)
    assert consumer.process(payload).exhausted and len(consumer.calls) == 3
    assert "private diagnostic" not in json_text(repo.get_job(result.work_id))


def test_crashed_attempt_reservations_and_stale_workers_fenced(repo):
    payload, _ = fixture()
    filing = FilingReady.parse(payload)
    first = repo.claim(filing, load_config())
    repo.begin_attempt(first["work_id"], first["claim_token"])
    with pytest.raises(WorkBusy): repo.claim(filing, load_config())
    repo.clock[0] += timedelta(seconds=361)
    second = repo.claim(filing, load_config())
    with pytest.raises(StaleClaim): repo.complete(first["work_id"], first["claim_token"], "review_required", [])
    repo.begin_attempt(second["work_id"], second["claim_token"])
    repo.clock[0] += timedelta(seconds=361)
    third = repo.claim(filing, load_config())
    repo.begin_attempt(third["work_id"], third["claim_token"])
    repo.clock[0] += timedelta(seconds=361)
    consumer, _ = worker(repo)
    result = consumer.process(payload)
    assert result.exhausted and not consumer.calls
    assert all(a["receipt"] is None and a["usage_unknown"] for a in repo.get_job(result.work_id)["attempts"])


def test_receipt_checkpoint_recovers_without_inference(repo, monkeypatch):
    consumer, payload = worker(repo)
    original = repo.complete
    monkeypatch.setattr(repo, "complete", lambda *a, **kw: (_ for _ in ()).throw(TimeoutError()))
    failed = consumer.process(payload)
    assert not failed.acknowledge and len(consumer.calls) == 1
    monkeypatch.setattr(repo, "complete", original)
    assert consumer.process(payload).acknowledge and len(consumer.calls) == 1


def test_crash_before_receipt_persistence_counts_next_attempt(repo, monkeypatch):
    consumer, payload = worker(repo)
    original = repo.save_receipt
    monkeypatch.setattr(repo, "save_receipt", lambda *a: (_ for _ in ()).throw(TimeoutError()))
    failed = consumer.process(payload)
    assert not failed.acknowledge
    monkeypatch.setattr(repo, "save_receipt", original)
    assert consumer.process(payload).acknowledge and len(consumer.calls) == 2
    attempts = repo.get_job(failed.work_id)["attempts"]
    assert attempts[0]["receipt"] is None and attempts[0]["usage_unknown"]
    assert attempts[1]["receipt"]["attempt"] == 2


def test_large_native_response_roundtrip_split_and_integrity(repo):
    value = native()
    value["padding"] = "x" * (1500 * 1024)
    consumer, payload = worker(repo, transport=lambda _: httpx.Response(200, json=value))
    result = consumer.process(payload)
    assert result.acknowledge
    job = repo.get_job(result.work_id)
    receipt = job["attempts"][0]["receipt"]
    assert job["attempts"][0]["receipt_ref"]["chunks"] > 20
    assert json.loads(b64decode(receipt["response_body_base64"])) == value
    assert len(json_text(repo._state(result.work_id)).encode()) < 10 * 1024


def test_input_and_config_conflicts_and_legacy_namespace_preserved(repo):
    consumer, payload = worker(repo)
    original = consumer.process(payload)
    changed_ready = {**payload, "ready_at": "2026-10-15T00:00:00.000000Z"}
    assert consumer.process(changed_ready).exhausted
    config = {**load_config(), "model": "other"}
    other_payload, _ = fixture(2)
    with pytest.raises(WorkConflict): repo.claim(FilingReady.parse(other_payload), config)
    assert repo.get_job(original.work_id)["input"] == FilingReady.parse(payload).to_dict()
    if isinstance(repo, SQLiteFiscalRepository):
        assert repo.db.execute("SELECT name FROM sqlite_master WHERE name='processing_jobs'").fetchone() is None
    else:
        assert repo._get("JOB#" + original.work_id, "STATE") is None



def test_historical_records_survive_processing_and_duplicate_delivery(repo):
    # Seed historical storage directly: the retired application is not a dependency.
    old_job = '{"record_schema_version":1,"outcome":"validated"}'
    old_event = '{"event_type":"earnings.validated","revision":1}'
    if isinstance(repo, SQLiteFiscalRepository):
        repo.db.execute("CREATE TABLE processing_jobs (work_id TEXT PRIMARY KEY, record_json TEXT NOT NULL)")
        repo.db.execute("CREATE TABLE event_revisions (event_id TEXT, revision INTEGER, payload_json TEXT, PRIMARY KEY(event_id,revision))")
        repo.db.execute("INSERT INTO processing_jobs VALUES (?,?)", ("legacy-work", old_job))
        repo.db.execute("INSERT INTO event_revisions VALUES (?,?,?)", ("legacy-event", 1, old_event))
        before = list(repo.db.iterdump())
    else:
        legacy = [dict(pk="JOB#legacy-work", sk="STATE", record_json=old_job),
                  dict(pk="EVENT#legacy-event", sk="REV#0000000001", payload_json=old_event)]
        for item in legacy:
            repo.client.put_item(TableName=repo.table_name, Item=item)
    consumer, payload = worker(repo)
    result = consumer.process(payload)
    assert result.acknowledge and consumer.process(payload) == result
    assert len(consumer.calls) == len(consumer.publisher.payloads) == 1
    assert json.loads(consumer.publisher.payloads[0])["event_type"] == "earnings.extracted"
    if isinstance(repo, SQLiteFiscalRepository):
        after = list(repo.db.iterdump())
        for line in before:
            if '"processing_jobs"' in line or '"event_revisions"' in line or line.startswith("CREATE TABLE processing_jobs") or line.startswith("CREATE TABLE event_revisions"):
                assert line in after
        assert repo.db.execute("SELECT record_json FROM processing_jobs").fetchall() == [(old_job,)]
        assert repo.db.execute("SELECT payload_json FROM event_revisions").fetchall() == [(old_event,)]
    else:
        assert all(repo._get(item["pk"], item["sk"]) == item for item in legacy)


def test_atomic_completion_state_event_status_and_fencing(repo, monkeypatch):
    consumer, payload = worker(repo)
    original = repo._cas
    def fail_event(item, prior, token, now, extra, deletes):
        if any(v["pk"].startswith("EPS2#EVENT#") for v in extra):
            return False
        return original(item, prior, token, now, extra, deletes)
    monkeypatch.setattr(repo, "_cas", fail_event)
    failed = consumer.process(payload)
    identity = FiscalIdentity(payload["filing_id"], payload["snapshot_id"], load_config()["version"], digest(load_config()))
    assert repo.event(identity.event_id) is None and repo._state(failed.work_id)["completion_ref"] is None
    assert not repo.list_status("accepted")["items"]
    monkeypatch.setattr(repo, "_cas", original)
    assert consumer.process(payload).acknowledge and len(consumer.calls) == 1


def test_status_pagination_and_cli_inspection_new_run_and_saved_retry(repo):
    consumer, payload = worker(repo, publisher=Publisher(failures=1))
    failed = consumer.process(payload)
    parse = parser().parse_args
    inspect = execute(parse(["inspect", failed.work_id]), repo)
    assert inspect["attempts"][0]["receipt"]["extraction"] == labels()
    retried = execute(parse(["retry", failed.work_id]), repo, consumer_factory=lambda _: consumer)
    assert retried["acknowledge"] and len(consumer.calls) == 1
    fresh = execute(parse(["reprocess", failed.work_id, "--run-id", "operator-001"]), repo, consumer_factory=lambda _: consumer)
    assert fresh["acknowledge"] and fresh["event_id"] != retried["event_id"] and len(consumer.calls) == 2
    assert execute(parse(["event", fresh["event_id"]]), repo)["event_id"] == fresh["event_id"]
    with pytest.raises(WorkConflict): execute(parse(["reprocess", failed.work_id, "--run-id", "operator-001"]), repo)
    with pytest.raises(WorkConflict): execute(parse(["retry", fresh["work_id"]]), repo)
    first = execute(parse(["list", "accepted", "--limit", "1"]), repo)
    assert len(first["items"]) == 1 and first["cursor"]
    second = execute(parse(["list", "accepted", "--limit", "1", "--cursor", first["cursor"]]), repo)
    assert second["items"][0]["work_id"] != first["items"][0]["work_id"]


def test_synthetic_demo_uses_real_mocked_boundary(tmp_path):
    from finbot_earnings.processing.demo import run
    result = run(tmp_path / "demo")
    assert result["model_calls"] == 2 and result["published_events"] == 1
    assert result["duplicate_acknowledged"] and result["empty_outcome"] == "no_eps_extracted" and result["review_outcome"] == "review_required"


def test_documented_identity_vectors_and_acceptance_cases():
    examples = json.loads(Path("docs/contracts/examples.json").read_text())
    # Full event is a stable specification vector, independent of today's timestamps.
    event = examples["accepted_event"]
    identity = FiscalIdentity(event["source"]["filing_id"], event["source"]["snapshot_id"],
        event["processing"]["extraction_config_version"], event["processing"]["extraction_config_sha256"], event["processing"]["run_id"])
    assert identity.work_id == event["processing"]["work_id"] and identity.event_id == event["event_id"]
    assert accept(event["extraction"]) == ("accepted", [])


def test_claimed_independent_filings_commit_during_each_other_without_merge(repo, monkeypatch):
    consumer1, first = worker(repo)
    second, bodies = fixture(2)
    consumer2, _ = worker(repo, source=Documents(bodies))
    actual = repo._cas
    raced = False
    def race(item, prior, token, now, extra, deletes):
        nonlocal raced
        if not raced and any(v["pk"].startswith("EPS2#EVENT#") for v in extra):
            raced = True
            result2 = consumer2.process(second)
            assert result2.acknowledge
        return actual(item, prior, token, now, extra, deletes)
    monkeypatch.setattr(repo, "_cas", race)
    result1 = consumer1.process(first)
    assert result1.acknowledge and len(repo.list_status("accepted")["items"]) == 2
    events = [repo.event(row["event_id"]) for row in repo.list_status("accepted")["items"]]
    assert len({e["source"]["filing_id"] for e in events}) == 2 and all("revision" not in e for e in events)


def test_receipt_immutability_and_expiry_after_blob_staging_cannot_commit(repo, monkeypatch):
    consumer, payload = worker(repo)
    filing = FilingReady.parse(payload)
    state = repo.claim(filing, load_config())
    repo.begin_attempt(state["work_id"], state["claim_token"])
    receipt = consumer.extractor.extract(filing, consumer.documents)
    repo.save_receipt(state["work_id"], state["claim_token"], receipt)
    changed = {**receipt, "usage_unknown": True}
    with pytest.raises(WorkConflict): repo.save_receipt(state["work_id"], state["claim_token"], changed)
    actual = repo._blob
    def expire(value):
        ref = actual(value)
        repo.clock[0] += timedelta(seconds=361)
        return ref
    monkeypatch.setattr(repo, "_blob", expire)
    with pytest.raises(StaleClaim): repo.complete(state["work_id"], state["claim_token"], "review_required", [])
    assert repo._state(state["work_id"])["completion_ref"] is None


def test_partial_chunk_failure_does_not_link_receipt_and_recovery_is_budgeted(repo, monkeypatch):
    consumer, payload = worker(repo, transport=lambda _: httpx.Response(200, json={**native(), "padding": "x" * 600_000}))
    actual = repo._immutable
    failed = False
    def broken(item):
        nonlocal failed
        if item["sk"] == "CHUNK#0002" and not failed:
            failed = True
            raise TimeoutError()
        return actual(item)
    monkeypatch.setattr(repo, "_immutable", broken)
    first = consumer.process(payload)
    assert not first.acknowledge and repo.get_job(first.work_id)["attempts"][0]["receipt"] is None
    assert consumer.process(payload).acknowledge and len(consumer.calls) == 2
    assert repo.get_job(first.work_id)["attempts"][0]["usage_unknown"]


def test_accepted_event_bound_reviews_without_truncation_or_retry(repo):
    consumer, payload = worker(repo)
    payload["company_name"] = "X" * (240 * 1024)
    rehash(payload)
    result = consumer.process(payload)
    assert result.outcome == "review_required" and result.reasons[0]["code"] == "event_bound_exceeded"
    assert not consumer.publisher.payloads
    assert len(repo.get_job(result.work_id)["input"]["company_name"]) == 240 * 1024
    assert consumer.process(payload).acknowledge and len(consumer.calls) == 1


def test_configuration_failure_requires_explicit_redrive_then_retries_within_original_budget(repo):
    failed = [True]
    def transport(_):
        return httpx.Response(401, json={"error": {"code": "invalid_api_key"}}) if failed[0] else httpx.Response(200, json=native())
    consumer, payload = worker(repo, transport=transport)
    result = consumer.process(payload)
    assert result.exhausted and len(consumer.calls) == 1
    failed[0] = False
    assert consumer.process(payload).exhausted and len(consumer.calls) == 1
    repo.rearm(result.work_id)
    assert consumer.process(payload).acknowledge and len(consumer.calls) == 2


def test_sqlite_restart_reuses_saved_events(tmp_path):
    path = tmp_path / "restart.sqlite3"
    store = SQLiteFiscalRepository(path)
    consumer, payload = worker(store)
    first = consumer.process(payload)
    store.close()
    store = SQLiteFiscalRepository(path)
    try:
        consumer, _ = worker(store)
        assert consumer.process(payload) == first and not consumer.calls and not consumer.documents.reads
    finally:
        store.close()


def test_dynamodb_backend_failure_rolls_back_completion_and_status(repo, monkeypatch):
    if not isinstance(repo, DynamoDBFiscalRepository):
        return
    consumer, payload = worker(repo)
    client_write = repo.client.transact_write_items
    def fail_transaction(**kwargs):
        if any(action.get("Put", {}).get("Item", {}).get("pk", "").startswith("EPS2#EVENT#") for action in kwargs["TransactItems"]):
            kwargs["TransactItems"].append(dict(ConditionCheck=dict(TableName=repo.table_name,
                Key=dict(pk="missing", sk="missing"), ConditionExpression="attribute_exists(pk)")))
        return client_write(**kwargs)
    monkeypatch.setattr(repo.client, "transact_write_items", fail_transaction)
    result = consumer.process(payload)
    assert not result.acknowledge and not repo.list_status("accepted")["items"]
    identity = FiscalIdentity(payload["filing_id"], payload["snapshot_id"], load_config()["version"], digest(load_config()))
    assert repo.event(identity.event_id) is None and repo._state(result.work_id)["completion_ref"] is None


@pytest.mark.parametrize("kind", ["annual", "multicurrency", "adjusted_only", "boolyear", "duplicate", "mixedperiod"])
def test_acceptance_policy_preserves_supported_semantics(kind):
    value = labels()
    row = value["reported_diluted_eps"][0]
    expected = "accepted"
    if kind == "annual": row.update(period_type="annual", fiscal_quarter=None)
    if kind == "multicurrency": value["reported_diluted_eps"].append({**row, "currency": "TWD", "value": "20.0000"})
    if kind == "adjusted_only": value = dict(reported_diluted_eps=[], adjusted_diluted_eps=[row])
    if kind == "boolyear": row["fiscal_year"] = True; expected = "processing_failed"
    if kind == "duplicate": value["reported_diluted_eps"].append({**row, "value": "9.990"}); expected = "review_required"
    if kind == "mixedperiod": value["adjusted_diluted_eps"] = [{**row, "period_type": "annual", "fiscal_quarter": None}]; expected = "review_required"
    assert accept(value)[0] == expected
