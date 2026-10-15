from copy import deepcopy
from dataclasses import replace
from datetime import timedelta
import json
import socket

import pytest

from finbot_earnings.processing.contracts import FilingReady
from finbot_earnings.processing.domain import Document, ExtractionConfig, WorkIdentity
from finbot_earnings.processing.errors import StaleClaim, WorkBusy
from finbot_earnings.processing.pipeline import FilingPipeline
from finbot_earnings.processing.sqlite_store import SQLiteProcessingRepository
from finbot_earnings.processing.validation import ValidationResult, validate
from tests.processing_helpers import (
    ADJUSTED, EVENT_ID, GAAP, NOW, PERIOD, Documents, Model, Publisher, fixture, rehash,
)


@pytest.fixture(autouse=True)
def offline_only(monkeypatch):
    def denied(*args, **kwargs):
        raise AssertionError("Network use forbidden in offline processing tests")
    monkeypatch.setattr(socket.socket, "connect", denied)
    monkeypatch.setattr(socket, "create_connection", denied)


@pytest.fixture
def store(tmp_path):
    with SQLiteProcessingRepository(tmp_path / "processing.sqlite3") as repository:
        yield repository


def pipeline(store, payload=None, bodies=None, response=None, *, publisher=None, config=None):
    default_payload, default_bodies, default_response = fixture()
    documents = Documents(default_bodies if bodies is None else bodies)
    model = Model(default_response if response is None else response)
    publisher = publisher or Publisher()
    worker = FilingPipeline(store, documents, model, publisher,
        config or ExtractionConfig("test-v1"), now=lambda: NOW)
    return worker, default_payload if payload is None else payload


def check_validation(payload, bodies, response):
    filing = FilingReady.parse(payload)
    documents = tuple(Document(ref, bodies[ref.artifact_id]) for ref in filing.artifacts)
    return validate(filing, documents, response, ExtractionConfig("test-v1"))


def test_complete_filing_one_call_persist_and_durable_duplicate(store):
    worker, payload = pipeline(store)
    result = worker.process(payload)
    assert (result.outcome, result.acknowledge, result.publications) == ("validated", True, ((EVENT_ID, 1),))
    assert len(worker.model.requests) == 1
    request = worker.model.requests[0]
    assert len(request.documents) == 3
    assert {doc.reference.artifact_id for doc in request.documents} == set(worker.documents.bodies)
    assert all(doc.body == worker.documents.bodies[doc.reference.artifact_id] for doc in request.documents)
    job = store.get_job(result.work_id)
    assert job["response"]["usage"] == {"input_tokens": 100, "output_tokens": 50}
    assert job["response"]["model_id"] == "fixture"
    assert len(job["completion"]["accepted_facts"]) == 2
    assert job["input"] == FilingReady.parse(payload).to_dict()
    event = store.event(EVENT_ID)
    assert event["event_type"] == "earnings.validated"
    assert len(event["source_snapshots"][0]["artifacts"]) == 3
    assert json.loads(worker.publisher.payloads[0]) == event
    # Reopen the database to demonstrate duplicate handling survives process restart.
    with SQLiteProcessingRepository(store.path) as restarted:
        next_worker, _ = pipeline(restarted)
        assert next_worker.process(payload) == result
        assert not next_worker.model.requests and not next_worker.documents.reads
        assert not next_worker.publisher.payloads


def test_publication_lost_ack_resumes_identical_payload_without_loading_or_model(store):
    publisher = Publisher(failures=1)
    worker, payload = pipeline(store, publisher=publisher)
    first = worker.process(payload)
    assert first.outcome == "retry" and not first.acknowledge
    assert store.event(EVENT_ID)["revision"] == 1
    assert len(store.pending_publications(first.work_id)) == 1
    with SQLiteProcessingRepository(store.path) as restarted:
        resumed, _ = pipeline(restarted, publisher=publisher)
        assert resumed.process(payload).acknowledge
        assert not resumed.model.requests and not resumed.documents.reads
        assert not restarted.pending_publications(first.work_id)
    assert publisher.payloads[0] == publisher.payloads[1]
    assert "sensitive provider diagnostic" not in json.dumps(store.get_job(first.work_id))


def test_saved_response_reused_after_validation_checkpoint_failure(store, monkeypatch):
    worker, payload = pipeline(store)
    original = store.complete
    def unavailable(*args):
        raise OSError("temporary persistence outage")
    monkeypatch.setattr(store, "complete", unavailable)
    first = worker.process(payload)
    assert first.outcome == "retry"
    assert store.get_job(first.work_id)["response"] is not None
    monkeypatch.setattr(store, "complete", original)
    assert worker.process(payload).outcome == "validated"
    assert len(worker.model.requests) == 1


def test_evaluation_and_deliberate_runs_are_isolated(store):
    worker, payload = pipeline(store)
    evaluation = worker.process(payload, run_mode="evaluation", run_id="candidate-1")
    assert evaluation.outcome == "validated" and evaluation.acknowledge
    assert not worker.publisher.payloads and store.event(EVENT_ID) is None
    assert worker.process(payload, run_mode="evaluation", run_id="candidate-1") == evaluation
    worker.process(payload, run_mode="evaluation", run_id="candidate-2")
    production = worker.process(payload)
    assert production.work_id != evaluation.work_id
    assert len(worker.model.requests) == 3 and len(worker.publisher.payloads) == 1


def test_economic_duplicate_enrichment_and_conflict_preserve_revisions(store):
    initial, bodies, response = fixture()
    response["facts"] = response["facts"][:1]
    first, _ = pipeline(store, bodies=bodies, response=response)
    assert first.process(initial).publications == ((EVENT_ID, 1),)
    original = store.event(EVENT_ID)
    # A second filing confirms the same number with more decimal places.
    duplicate, bodies, response = fixture(2, gaap=GAAP.replace("1.23", "1.230"))
    response["facts"] = response["facts"][:1]
    response["facts"][0]["value"] = "1.230"
    second, _ = pipeline(store, bodies=bodies, response=response)
    assert second.process(duplicate).publications == ((EVENT_ID, 1),)
    assert not second.publisher.payloads and store.event(EVENT_ID) == original
    enriched, bodies, response = fixture(3)
    third, _ = pipeline(store, bodies=bodies, response=response)
    assert third.process(enriched).publications == ((EVENT_ID, 2),)
    assert store.event(EVENT_ID, 1) == original
    assert len(store.event(EVENT_ID)["facts"]) == 2
    assert len(store.event(EVENT_ID)["source_snapshots"]) == 2
    conflicting, bodies, response = fixture(4, gaap=GAAP.replace("1.23", "1.24"))
    response["facts"][0]["value"] = "1.24"
    fourth, _ = pipeline(store, bodies=bodies, response=response)
    result = fourth.process(conflicting)
    assert result.outcome == "review_required" and result.acknowledge
    assert result.findings[0]["code"] == "canonical_fact_conflict"
    assert store.event(EVENT_ID)["revision"] == 2 and not fourth.publisher.payloads


@pytest.mark.parametrize("response,outcome", [
    ({"classification": "does_not_report_earnings", "facts": []}, "no_relevant_earnings"),
    ({"classification": "uncertain", "facts": []}, "review_required"),
    ({"classification": "reports_earnings", "facts": []}, "review_required"),
])
def test_semantic_outcomes_complete_without_retry(store, response, outcome):
    worker, payload = pipeline(store, response=response)
    result = worker.process(payload)
    assert (result.outcome, result.acknowledge) == (outcome, True)
    assert worker.process(payload) == result
    assert len(worker.model.requests) == 1 and not worker.publisher.payloads


@pytest.mark.parametrize("condition,code", [
    ("count", "too_many_documents"), ("size", "filing_input_exceeds_limit"),
    ("pdf", "unsupported_document_format"), ("encoding", "unsupported_document_encoding"),
    ("empty", "empty_document"),
])
def test_whole_snapshot_bounds_review_without_model(store, condition, code):
    payload, bodies, response = fixture()
    config = ExtractionConfig("test-v1")
    if condition == "count":
        config = replace(config, max_documents=2)
    elif condition == "size":
        config = replace(config, max_input_bytes=10)
    elif condition == "pdf":
        payload["artifacts"][2]["content_type"] = "application/pdf"
    else:
        ref = payload["artifacts"][0]
        bodies[ref["artifact_id"]] = b"\xff" if condition == "encoding" else b""
        ref["size_bytes"] = len(bodies[ref["artifact_id"]])
    rehash(payload)
    worker, _ = pipeline(store, bodies=bodies, response=response, config=config)
    result = worker.process(payload)
    assert (result.outcome, result.acknowledge) == ("review_required", True)
    assert result.findings == ({"code": code},)
    assert not worker.model.requests and not worker.publisher.payloads
    if condition in {"count", "size", "pdf"}:
        assert not worker.documents.reads


@pytest.mark.parametrize("failure", ["missing", "size", "model", "publisher"])
def test_bounded_technical_failures_require_explicit_redrive(store, failure):
    worker, payload = pipeline(store)
    if failure == "missing":
        worker.documents.bodies.clear()
    elif failure == "size":
        worker.documents.bodies[payload["primary_artifact_id"]] = b"wrong"
    elif failure == "model":
        def unavailable(request):
            raise TimeoutError("provider unavailable")
        worker.model.classify_and_extract = unavailable
    else:
        worker.publisher.failures = 10
    for attempt in range(3):
        result = worker.process(payload)
        assert not result.acknowledge
        assert result.exhausted == (attempt == 2)
    saved = store.get_job(result.work_id)
    assert worker.process(payload).exhausted
    assert store.get_job(result.work_id)["attempt_count"] == saved["attempt_count"]
    if failure == "publisher":
        worker.publisher.failures = 0
        store.rearm(result.work_id, NOW)
        assert worker.process(payload).acknowledge
        assert len(worker.model.requests) == 1


@pytest.mark.parametrize("mutate", [
    lambda r: r.update(extra="invalid"),
    lambda r: r["facts"][0].update(value=1.23),
    lambda r: r["facts"][0].update(value="NaN"),
    lambda r: r["facts"][0].update(currency=None),
    lambda r: r["facts"][0]["period"].update(end_date="2026-02-30"),
])
def test_malformed_model_response_is_saved_and_terminal(store, mutate):
    _, _, response = fixture()
    mutate(response)
    worker, payload = pipeline(store, response=response)
    result = worker.process(payload)
    assert result.exhausted and result.outcome == "processing_failed" and not result.acknowledge
    assert store.get_job(result.work_id)["response"]["response"] == response
    assert result.findings[0]["code"] == "invalid_model_response"
    worker.process(payload)
    assert len(worker.model.requests) == 1


def test_active_claim_expiry_and_fencing(store):
    payload, _, _ = fixture()
    filing, config = FilingReady.parse(payload), ExtractionConfig("test-v1", lease_seconds=10)
    identity = WorkIdentity(filing.filing_id, filing.snapshot_id, config.version)
    first = store.claim(filing, config, identity, NOW)
    with SQLiteProcessingRepository(store.path) as other:
        with pytest.raises(WorkBusy):
            other.claim(filing, config, identity, NOW)
        reclaimed = other.claim(filing, config, identity, NOW + timedelta(seconds=11))
        assert reclaimed["claim_token"] != first["claim_token"]
        with pytest.raises(StaleClaim):
            store.save_response(identity.work_id, first["claim_token"], {}, NOW + timedelta(seconds=11))
        with pytest.raises(WorkBusy):
            store.rearm(identity.work_id, NOW + timedelta(seconds=11))


def test_config_version_cannot_be_reused_with_changed_settings(store):
    worker, payload = pipeline(store)
    worker.process(payload)
    worker.config = replace(worker.config, max_documents=5)
    result = worker.process(payload)
    assert result.exhausted and result.findings[0]["code"] == "work_identity_conflict"


@pytest.mark.parametrize("change,code", [
    (lambda f: f.update(source_artifact_id="other/file.htm"), "source_not_in_manifest"),
    (lambda f: f.update(currency="EUR"), "currency_mismatch"),
    (lambda f: f.update(value="-1.23"), "value_sign_or_precision_mismatch"),
    (lambda f: f.update(value="1.230"), "value_sign_or_precision_mismatch"),
    (lambda f: f.update(evidence="invented quotation"), "evidence_not_in_supported_prose"),
    (lambda f: f["period"].update(end_date="2025-09-30"), "current_reporting_period_unresolved"),
    (lambda f: f["period"].update(label="Q3 2026"), "period_label_mismatch"),
])
def test_bad_optional_fact_withheld_independent_good_fact_survives(change, code):
    payload, bodies, response = fixture()
    change(response["facts"][0])
    result = check_validation(payload, bodies, response)
    assert result.outcome == "validated"
    assert len(result.accepted) == 1 and result.accepted[0]["metric"] == "adjusted_diluted_eps"
    assert result.findings[0]["code"] == code


@pytest.mark.parametrize("quote,value,code", [
    (GAAP.replace("earnings", "loss"), "-1.23", None),
    (GAAP.replace("1.23", "(1.23)"), "-1.23", None),
    (GAAP.replace("1.23", "−1.23"), "-1.23", None),
    (GAAP.replace("US$", "$"), "1.23", "metric_value_binding_unresolved"),
    (GAAP.replace("US$1.23", "US$123 cents"), "123", "units_or_share_basis_unresolved"),
    (GAAP.replace("US$1.23", "US$1.23 million"), "1.23", "units_or_share_basis_unresolved"),
    (GAAP.replace("diluted", "basic"), "1.23", "units_or_share_basis_unresolved"),
    (GAAP.replace("1.23", "1,234"), "1", "metric_value_binding_unresolved"),
])
def test_sign_currency_units_and_share_basis(quote, value, code):
    payload, bodies, response = fixture(gaap=quote)
    response["facts"] = response["facts"][:1]
    response["facts"][0]["value"] = value
    result = check_validation(payload, bodies, response)
    assert result.outcome == ("validated" if code is None else "review_required")
    if code:
        assert result.findings[0]["code"] == code


def test_table_hidden_wrong_company_and_ambiguous_period_require_review():
    for replacement, code in [
        (f"<h1>Apple results — {PERIOD}</h1><table><tr><td>{GAAP}</td></tr></table>", "evidence_not_in_supported_prose"),
        (f"<h1>Apple results — {PERIOD}</h1><p hidden>{GAAP}</p>", "evidence_not_in_supported_prose"),
        (f"<h1>Other company results — {PERIOD}</h1><p>{GAAP}</p>", "company_identity_unresolved"),
        (f"<h1>Apple results — {PERIOD} and Three months ended September 30, 2025</h1><p>{GAAP}</p>", "current_reporting_period_unresolved"),
    ]:
        payload, bodies, response = fixture()
        response["facts"] = response["facts"][:1]
        bodies[response["facts"][0]["source_artifact_id"]] = replacement.encode()
        result = check_validation(payload, bodies, response)
        assert result.outcome == "review_required" and result.findings[0]["code"] == code


def test_material_conflict_blocks_other_facts_for_affected_period():
    payload, bodies, response = fixture()
    conflicting = deepcopy(response["facts"][0])
    conflicting["value"] = "2.00"
    response["facts"].append(conflicting)
    result = check_validation(payload, bodies, response)
    assert result.outcome == "review_required" and not result.accepted
    assert {f["code"] for f in result.findings} == {"material_fact_conflict"}


def test_clipped_quote_cannot_hide_units_and_forecasts_require_review():
    for paragraph, expected in [
        (GAAP[:-1] + " million.", "evidence_not_in_supported_prose"),
        ("We expect " + GAAP, "reported_result_unresolved"),
    ]:
        payload, bodies, response = fixture(gaap=paragraph)
        response["facts"] = response["facts"][:1]
        if "million" in paragraph:
            response["facts"][0]["evidence"] = GAAP[:-1]
        result = check_validation(payload, bodies, response)
        assert result.outcome == "review_required" and result.findings[0]["code"] == expected


def test_future_period_cannot_be_accepted_as_current_reported_earnings():
    payload, bodies, response = fixture()
    payload["filed_at"] = "2026-09-01T00:00:00.000000Z"
    rehash(payload)
    result = check_validation(payload, bodies, response)
    assert result.outcome == "review_required"
    assert {finding["code"] for finding in result.findings} == {"current_reporting_period_unresolved"}


def test_explicit_half_year_non_gaap_plain_text(store):
    label = "Six months ended September 30, 2026"
    quote = f"For the {label.lower()}, non-GAAP diluted earnings per share were EUR2.45."
    payload, bodies, response = fixture()
    reference = payload["artifacts"][0]
    reference.update(filename="release.txt", artifact_id=payload["filing_id"] + "/release.txt",
                     s3_uri="s3://artifacts/release.txt", content_type="text/plain")
    body = f"Apple financial results\n{label}\n{quote}".encode()
    reference["size_bytes"] = len(body)
    payload["primary_artifact_id"] = reference["artifact_id"]
    payload["artifacts"] = [reference]
    rehash(payload)
    response["facts"] = [dict(metric="adjusted_diluted_eps", value="2.45", currency="EUR",
        period=dict(kind="half_year", end_date="2026-09-30", label=label),
        source_artifact_id=reference["artifact_id"], evidence=quote)]
    worker, _ = pipeline(store, bodies={reference["artifact_id"]: body}, response=response)
    result = worker.process(payload)
    assert result.outcome == "validated" and result.acknowledge
    assert store.event("0000320193:half_year:2026-09-30")["facts"][0]["currency"] == "EUR"


def test_quarter_and_annual_are_distinct_events(store):
    annual_label = "Year ended September 30, 2026"
    annual_quote = f"For the {annual_label.lower()}, GAAP diluted earnings per share were US$5.00."
    payload, bodies, response = fixture(adjusted=annual_quote, heading_period=PERIOD + " and " + annual_label)
    annual = response["facts"][1]
    annual.update(metric="gaap_diluted_eps", value="5.00",
                  period=dict(kind="annual", end_date="2026-09-30", label=annual_label))
    worker, _ = pipeline(store, bodies=bodies, response=response)
    result = worker.process(payload)
    assert result.outcome == "validated" and len(result.publications) == 2
    assert store.event(EVENT_ID)["facts"][0]["value"] == "1.23"
    assert store.event("0000320193:annual:2026-09-30")["facts"][0]["value"] == "5.00"
    assert len(worker.model.requests) == 1


def test_multi_event_commit_rolls_back_all_writes_on_failure(store, monkeypatch):
    payload, _, response = fixture()
    filing, config = FilingReady.parse(payload), ExtractionConfig("test-v1")
    identity = WorkIdentity(filing.filing_id, filing.snapshot_id, config.version)
    job = store.claim(filing, config, identity, NOW)
    annual = deepcopy(response["facts"][0])
    annual["period"]["kind"] = "annual"
    validation = ValidationResult("validated", (), (annual, response["facts"][0]))
    original = store.event
    def fail_second(event_id, revision=None):
        if event_id == EVENT_ID:
            raise OSError("second event write failed")
        return original(event_id, revision)
    monkeypatch.setattr(store, "event", fail_second)
    with pytest.raises(OSError):
        store.complete(identity.work_id, job["claim_token"], validation, NOW)
    monkeypatch.setattr(store, "event", original)
    assert store.event("0000320193:annual:2026-09-30") is None
    assert store.get_job(identity.work_id)["completion"] is None
    assert not store.pending_publications(identity.work_id)
    assert store.db.execute("SELECT COUNT(*) FROM event_revisions").fetchone()[0] == 0


def test_two_claimed_filings_reconcile_against_latest_revision(store):
    # Both jobs are claimed before either completes, as with concurrent workers.
    payload1, _, response1 = fixture(1)
    payload2, _, response2 = fixture(2)
    config = ExtractionConfig("test-v1")
    with SQLiteProcessingRepository(store.path) as other:
        claims = []
        for repo, payload in ((store, payload1), (other, payload2)):
            filing = FilingReady.parse(payload)
            identity = WorkIdentity(filing.filing_id, filing.snapshot_id, config.version)
            claims.append((repo, repo.claim(filing, config, identity, NOW)))
        for (repo, claim), fact in zip(claims, (response1["facts"][0], response2["facts"][1])):
            repo.complete(claim["work_id"], claim["claim_token"], ValidationResult("validated", (), (fact,)), NOW)
        assert store.event(EVENT_ID)["revision"] == 2
        assert len(store.event(EVENT_ID)["facts"]) == 2


def test_offline_demo_creates_reviewable_outputs(tmp_path):
    from finbot_earnings.processing.demo import run
    output = tmp_path / "demo"
    summary = run(output)
    assert summary["model_calls"] == 1 and summary["documents_per_call"] == [3]
    assert summary["published_events"] == 1 and summary["duplicate_acknowledged"]
    assert json.loads((output / "published-events.jsonl").read_text())["event_id"] == EVENT_ID
    assert json.loads((output / "processing-record.json").read_text())["completion"]["outcome"] == "validated"
    with pytest.raises(FileExistsError):
        run(output)


@pytest.mark.parametrize("mode", ["mixed", "pdf_only", "conflict"])
def test_pdf_bytes_reach_model_but_pdf_facts_require_review(store, mode):
    payload, bodies, response = fixture()
    ref = payload["artifacts"][2]
    old_id = ref["artifact_id"]
    pdf_id = payload["filing_id"] + "/supplement.pdf"
    raw_pdf = b"%PDF-1.7\n\xff\xfe\x00Synthetic fixture"
    ref.update(artifact_id=pdf_id, filename="supplement.pdf", s3_uri="s3://artifacts/" + pdf_id,
               content_type="application/pdf", size_bytes=len(raw_pdf))
    del bodies[old_id]
    bodies[pdf_id] = raw_pdf
    response["facts"][1]["source_artifact_id"] = pdf_id
    if mode == "pdf_only":
        payload["artifacts"] = [ref]
        payload["primary_artifact_id"] = pdf_id
        bodies = {pdf_id: raw_pdf}
        response["facts"][0]["source_artifact_id"] = pdf_id
    elif mode == "conflict":
        conflicting = deepcopy(response["facts"][0])
        conflicting.update(source_artifact_id=pdf_id, value="1.24")
        response["facts"].append(conflicting)
    rehash(payload)
    worker, _ = pipeline(store, bodies=bodies, response=response)
    result = worker.process(payload)
    assert result.acknowledge
    assert len(worker.model.requests) == 1
    assert next(doc.body for doc in worker.model.requests[0].documents if doc.reference.artifact_id == pdf_id) == raw_pdf
    job = store.get_job(result.work_id)
    assert job["response"]["response"] == response
    if mode == "mixed":
        assert result.outcome == "validated"
        assert {fact["metric"] for fact in job["completion"]["accepted_facts"]} == {"gaap_diluted_eps"}
        assert result.findings[0]["code"] == "pdf_evidence_requires_review"
    else:
        assert result.outcome == "review_required" and not worker.publisher.payloads
        code = "material_fact_conflict" if mode == "conflict" else "pdf_evidence_requires_review"
        assert {finding["code"] for finding in result.findings} == {code}
    assert worker.process(payload) == result
    assert len(worker.model.requests) == 1


def test_invalid_pdf_header_reviews_before_inference(store):
    payload, bodies, response = fixture()
    ref = payload["artifacts"][2]
    old_id = ref["artifact_id"]
    new_id = payload["filing_id"] + "/supplement.pdf"
    bodies[new_id] = bodies.pop(old_id)
    ref.update(artifact_id=new_id, filename="supplement.pdf", s3_uri="s3://artifacts/" + new_id,
               content_type="application/pdf")
    rehash(payload)
    worker, _ = pipeline(store, bodies=bodies, response=response)
    result = worker.process(payload)
    assert result.acknowledge and result.outcome == "review_required"
    assert result.findings == ({"code": "invalid_pdf_document"},)
    assert not worker.model.requests and not worker.publisher.payloads


def test_provider_input_limit_becomes_durable_review(store):
    from finbot_earnings.processing.errors import InputReview

    worker, payload = pipeline(store)
    def exceeds_provider_limit(request):
        raise InputReview("document_exceeds_provider_limit")
    worker.model.classify_and_extract = exceeds_provider_limit
    result = worker.process(payload)
    assert result.acknowledge and result.outcome == "review_required"
    assert result.findings == ({"code": "document_exceeds_provider_limit"},)
    assert store.get_job(result.work_id)["response"] is None
    assert worker.process(payload) == result
    assert not worker.publisher.payloads
