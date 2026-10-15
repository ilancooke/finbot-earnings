from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import shutil
from unittest.mock import Mock

import boto3
from botocore.stub import Stubber
import pytest

from finbot_earnings.evaluation.__main__ import LocalBedrockModel, main
from finbot_earnings.evaluation.corpus import load_corpus
from finbot_earnings.evaluation.runner import Pricing, run
from finbot_earnings.evaluation.scoring import counts, metrics
from finbot_earnings.processing.aws_adapters import NovaLiteModel
from finbot_earnings.processing.domain import ExtractionConfig, ModelResult
from finbot_earnings.processing.sqlite_store import SQLiteProcessingRepository

ROOT = Path(__file__).resolve().parents[1]
STARTER = ROOT / "evaluations/starter/corpus.json"
CONFIG = ROOT / "infra/cdk/config.prod.json"


@pytest.fixture
def config():
    return ExtractionConfig(**json.loads(CONFIG.read_text())["extraction"])


@pytest.fixture
def corpus_copy(tmp_path):
    destination = tmp_path / "corpus"
    shutil.copytree(STARTER.parent, destination)
    return destination / "corpus.json"


def save(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def single_case(path):
    value = json.loads(path.read_text())
    value["cases"] = value["cases"][:1]
    save(path, value)
    return path.parent / value["cases"][0]


def test_starter_checks_all_formats_and_reports_validation_gaps_locally(tmp_path, config):
    corpus = load_corpus(STARTER, config, offline=True)
    report = run(corpus, tmp_path / "run", config, None, provider="fixture", pricing=Pricing("1", "2"))
    summary = report["summary"]
    assert report["complete"] and summary["cases"] == 8
    assert summary["classification_accuracy"] == summary["exact_extraction_accuracy"] == 1
    assert summary["extraction"]["recall"] == 1
    assert summary["accepted"]["recall"] == .5
    assert summary["outcomes"] == {"validated": 3, "review_required": 3, "no_relevant_earnings": 2}
    assert summary["model_calls"] == 8 and summary["calls_with_unknown_usage"] == 0
    assert summary["estimated_cost_usd"] == "0.0016"
    assert summary["p95_model_seconds"] >= summary["median_model_seconds"] >= 0
    assert json.loads((tmp_path / "run/report.json").read_text()) == report
    assert "Accepted precision/recall" in (tmp_path / "run/report.md").read_text()
    with SQLiteProcessingRepository(tmp_path / "run/processing.sqlite3") as repository:
        for row in report["cases"]:
            job = repository.get_job(row["work_id"])
            assert job["identity"]["run_mode"] == "evaluation"
            assert job["completion"]["publications"] == []
            assert repository.pending_publications(row["work_id"]) == []
        assert repository.db.execute("SELECT count(*) FROM canonical_events").fetchone()[0] == 0
        assert repository.db.execute("SELECT count(*) FROM event_revisions").fetchone()[0] == 0
    pdf = json.loads((tmp_path / "run/cases/pdf-only.json").read_text())
    assert {finding["code"] for finding in pdf["result"]["findings"]} == {"pdf_evidence_requires_review"}
    assert pdf["processing_record"]["response"]["response"]["facts"]


def test_economic_scoring_penalizes_wrong_period_precision_duplicates_and_hallucinations(config):
    fact = load_corpus(STARTER, config).cases[0].expected["facts"][0]
    correct = deepcopy(fact)
    correct.update(evidence="Different wording", source_artifact_id="other/document")
    correct["period"]["label"] = "Alternate label"
    assert counts([fact], [correct]) == dict(true_positive=1, false_positive=0, false_negative=0)
    for change in (lambda item: item.update(value="1.230"),
                   lambda item: item["period"].update(end_date="2025-09-30"),
                   lambda item: item.update(currency="EUR"),
                   lambda item: item.update(value="-1.23")):
        wrong = deepcopy(fact)
        change(wrong)
        assert counts([fact], [wrong]) == dict(true_positive=0, false_positive=1, false_negative=1)
    scored = metrics(counts([fact], [fact, fact]))
    assert scored["precision"] == .5 and scored["recall"] == 1
    assert metrics(counts([], []))["f1"] is None


@pytest.mark.parametrize("condition", ["hash", "missing", "extra_mapping", "outside", "symlink", "duplicate_case", "bad_label", "bad_source"])
def test_entire_corpus_preflight_rejects_bad_inputs(corpus_copy, config, condition):
    path = corpus_copy.parent / "html-multiple/case.json"
    case = json.loads(path.read_text())
    artifact_id = next(iter(case["documents"]))
    mapping = case["documents"][artifact_id]
    if condition == "hash":
        document = corpus_copy.parent / mapping["path"]
        original = document.read_bytes()
        document.write_bytes(b"x" + original[1:])
    elif condition == "missing":
        (corpus_copy.parent / mapping["path"]).unlink()
    elif condition == "extra_mapping":
        case["documents"]["extra"] = mapping
    elif condition == "outside":
        mapping["path"] = "../outside.txt"
    elif condition == "symlink":
        document = corpus_copy.parent / mapping["path"]
        document.unlink()
        outside = corpus_copy.parent.parent / "outside.txt"
        outside.write_text("outside")
        document.symlink_to(outside)
    elif condition == "duplicate_case":
        value = json.loads(corpus_copy.read_text())
        value["cases"].append(value["cases"][0])
        save(corpus_copy, value)
    elif condition == "bad_label":
        case["expected"]["facts"][0]["value"] = "invalid"
    else:
        case["expected"]["facts"][0]["source_artifact_id"] = "unknown/document"
    save(path, case)
    with pytest.raises((ValueError, RuntimeError)):
        load_corpus(corpus_copy, config)


def test_frozen_file_change_after_preflight_blocks_inference(corpus_copy, config, tmp_path):
    single_case(corpus_copy)
    corpus = load_corpus(corpus_copy, config)
    next(iter(corpus.cases[0].documents.values())).write_text("tampered")
    model = Mock()
    report = run(corpus, tmp_path / "run", config, model)
    model.classify_and_extract.assert_not_called()
    assert report["summary"]["technical_failures"] == 1
    assert report["summary"]["model_calls"] == 0
    assert report["summary"]["extraction"]["false_negative"] == 2


@pytest.mark.parametrize("response", [None, {"wrong_schema": True}])
def test_failed_and_invalid_cases_stay_in_scores_and_preserve_available_usage(corpus_copy, config, tmp_path, response):
    single_case(corpus_copy)
    corpus = load_corpus(corpus_copy, config)
    model = Mock()
    if response is None:
        model.classify_and_extract.side_effect = TimeoutError("secret diagnostic")
    else:
        model.classify_and_extract.return_value = ModelResult(response, config.model_id, {"input_tokens": 10, "output_tokens": 5})
    report = run(corpus, tmp_path / "run", config, model, pricing=Pricing("1", "2"))
    summary = report["summary"]
    assert summary["classification_accuracy"] == summary["exact_extraction_accuracy"] == 0
    assert summary["technical_failures"] == summary["model_calls"] == 1
    assert summary["extraction"]["false_negative"] == 2
    if response is None:
        assert summary["calls_with_unknown_usage"] == 1
        assert summary["estimated_cost_usd"] is None
        assert summary["known_estimated_cost_usd"] == "0"
    else:
        assert summary["calls_with_unknown_usage"] == 0
        assert summary["estimated_cost_usd"] == "0.00002"
        record = json.loads((tmp_path / "run/cases/html-multiple.json").read_text())
        assert record["processing_record"]["response"]["response"] == response
    assert "secret diagnostic" not in (tmp_path / "run/report.json").read_text()
    model.classify_and_extract.assert_called_once()


def test_oversized_snapshot_is_reviewed_without_a_model_call(config, tmp_path):
    bounded = replace(config, max_input_bytes=1)
    corpus = load_corpus(STARTER, bounded)
    model = Mock()
    report = run(corpus, tmp_path / "run", bounded, model)
    model.classify_and_extract.assert_not_called()
    assert report["summary"]["outcomes"] == {"review_required": 8}
    assert report["summary"]["model_calls"] == 0


def test_existing_output_is_never_overwritten(config, tmp_path):
    corpus = load_corpus(STARTER, config)
    output = tmp_path / "important"
    output.mkdir()
    marker = output / "existing.txt"
    marker.write_text("keep")
    model = Mock()
    with pytest.raises(FileExistsError):
        run(corpus, output, config, model)
    assert marker.read_text() == "keep"
    model.classify_and_extract.assert_not_called()


def test_bedrock_tool_response_passes_through_local_evaluation_without_gold_labels(corpus_copy, config, tmp_path):
    case_path = single_case(corpus_copy)
    corpus = load_corpus(corpus_copy, config)
    expected = corpus.cases[0].expected
    # Deliberately wrong gold values must not leak into the inference request.
    case = json.loads(case_path.read_text())
    case["expected"]["facts"][0]["value"] = "98765.43"
    save(case_path, case)
    corpus = load_corpus(corpus_copy, config)
    client, seen = boto3.client("bedrock-runtime"), []
    client.meta.events.register("before-parameter-build.bedrock-runtime.Converse", lambda params, **kwargs: seen.append(params))
    with Stubber(client) as stub:
        stub.add_response("converse", dict(output={"message": {"role": "assistant", "content": [{"toolUse": {
            "toolUseId": "one", "name": "report_earnings", "input": expected}}]}}, stopReason="tool_use",
            usage={"inputTokens": 100, "outputTokens": 50, "totalTokens": 150}, metrics={"latencyMs": 1}))
        report = run(corpus, tmp_path / "run", config, NovaLiteModel(client))
        stub.assert_no_pending_responses()
    assert len(seen) == 1 and len(seen[0]["messages"][0]["content"]) == 4
    assert "98765.43" not in repr(seen)
    assert report["summary"]["extraction"]["true_positive"] == 1
    assert report["summary"]["extraction"]["false_positive"] == 1
    assert report["summary"]["extraction"]["false_negative"] == 1


def test_cli_check_and_offline_run_never_create_aws_session(monkeypatch, tmp_path, capsys):
    def forbidden(*args, **kwargs):
        raise AssertionError("AWS client construction forbidden")
    monkeypatch.setattr(boto3, "Session", forbidden)
    common = ["--corpus", str(STARTER), "--config", str(CONFIG), "--offline"]
    assert main(["check", *common]) == 0
    assert main(["run", *common, "--output-dir", str(tmp_path / "run")]) == 0
    assert "synthetic-starter-v1" in capsys.readouterr().out


def test_bedrock_client_is_lazy_reused_and_has_no_sdk_retries(monkeypatch, config):
    delegate = Mock()
    session = Mock()
    session.client.return_value = delegate
    factory = Mock(return_value=session)
    monkeypatch.setattr(boto3, "Session", factory)
    model = LocalBedrockModel("chosen-profile", "us-east-1")
    factory.assert_not_called()
    corpus = load_corpus(STARTER, config)
    from finbot_earnings.processing.domain import ModelRequest
    request = ModelRequest(corpus.cases[0].filing, (), config)
    # Bypass the real adapter; here we test the client lifecycle, not provider I/O.
    adapter = Mock()
    monkeypatch.setattr("finbot_earnings.evaluation.__main__.NovaLiteModel", lambda client: adapter)
    model.classify_and_extract(request)
    model.classify_and_extract(request)
    factory.assert_called_once_with(profile_name="chosen-profile", region_name="us-east-1")
    assert session.client.call_args.args == ("bedrock-runtime",)
    assert session.client.call_args.kwargs["config"].retries["total_max_attempts"] == 1
    assert session.client.call_count == 1 and adapter.classify_and_extract.call_count == 2


@pytest.mark.parametrize("rate", ["-1", "NaN", "Infinity", "invalid"])
def test_invalid_prices_rejected(rate):
    with pytest.raises(ValueError):
        Pricing(rate, "1")


def test_cli_rejects_partial_prices_before_any_calls(tmp_path):
    with pytest.raises(SystemExit) as caught:
        main(["run", "--corpus", str(STARTER), "--config", str(CONFIG),
              "--output-dir", str(tmp_path / "run"), "--input-usd-per-million", "1"])
    assert caught.value.code == 2 and not (tmp_path / "run").exists()


def test_corpus_identity_survives_location_and_provider_changes_but_not_label_changes(corpus_copy, config):
    original = load_corpus(STARTER, config)
    copied = load_corpus(corpus_copy, config, offline=True)
    assert original.sha256 == copied.sha256
    case_path = corpus_copy.parent / "html-multiple/case.json"
    case = json.loads(case_path.read_text())
    case["expected"]["facts"][0]["value"] = "9.99"
    save(case_path, case)
    assert load_corpus(corpus_copy, config).sha256 != original.sha256


def test_case_named_report_cannot_overwrite_summary(corpus_copy, config, tmp_path):
    case_path = single_case(corpus_copy)
    case = json.loads(case_path.read_text())
    case["case_id"] = "report"
    save(case_path, case)
    corpus = load_corpus(corpus_copy, config, offline=True)
    run(corpus, tmp_path / "run", config, None, provider="fixture")
    assert (tmp_path / "run/cases/report.json").is_file()
    assert json.loads((tmp_path / "run/report.json").read_text())["complete"]


def test_real_draft_labels_are_preserved_without_claiming_human_review(corpus_copy, config, tmp_path):
    single_case(corpus_copy)
    value = json.loads(corpus_copy.read_text())
    value.update(corpus_id="real-draft-example", label_source="agent_draft", label_notes="Pending human review")
    save(corpus_copy, value)
    corpus = load_corpus(corpus_copy, config, offline=True)
    report = run(corpus, tmp_path / "run", config, None, provider="fixture")
    assert report["run"]["label_source"] == "agent_draft"
    assert json.loads((tmp_path / "run/corpus-snapshot.json").read_text())["label_source"] == "agent_draft"
    assert "await human review" in (tmp_path / "run/report.md").read_text()
