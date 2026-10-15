"""Sequential evaluation through the production core, with local-only persistence."""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import math
from pathlib import Path
import statistics
import time
import uuid

from finbot_earnings.processing.aws_adapters import EPS_SCHEMA, SYSTEM_PROMPT
from finbot_earnings.processing.contracts import json_text, utc_text
from finbot_earnings.processing.domain import ModelResult, response_facts
from finbot_earnings.processing.errors import TechnicalFailure
from finbot_earnings.processing.pipeline import FilingPipeline
from finbot_earnings.processing.sqlite_store import SQLiteProcessingRepository
from finbot_earnings.processing import validation

from .corpus import LocalDocuments
from .scoring import ratio, score, summarize


@dataclass(frozen=True)
class Pricing:
    input_usd_per_million: str
    output_usd_per_million: str

    def __post_init__(self):
        for value in asdict(self).values():
            try:
                rate = Decimal(value)
            except (InvalidOperation, TypeError, ValueError) as exc:
                raise ValueError("Prices must be finite nonnegative decimals") from exc
            if not rate.is_finite() or not 0 <= rate <= 1_000_000:
                raise ValueError("Prices must be finite nonnegative decimals")

    def estimate(self, usage):
        value = (usage["input_tokens"] * Decimal(self.input_usd_per_million)
                 + usage["output_tokens"] * Decimal(self.output_usd_per_million)) / 1_000_000
        return format(value, "f")


class NoPublication:
    def publish(self, _):
        raise RuntimeError("Evaluation must never publish")


class MeasuredModel:
    def __init__(self, delegate):
        self.delegate, self.calls, self.seconds, self.result = delegate, 0, [], None

    def classify_and_extract(self, request):
        self.calls += 1
        started = time.perf_counter()
        try:
            self.result = self.delegate.classify_and_extract(request)
            return self.result
        finally:
            self.seconds.append(time.perf_counter() - started)


class FixtureModel:
    def __init__(self, fixture):
        self.fixture = fixture

    def classify_and_extract(self, request):
        return ModelResult(self.fixture["response"], request.config.model_id, self.fixture["usage"])


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json_text(value) + "\n", encoding="utf-8")
    temporary.replace(path)


def usage_of(model):
    usage = model.result.usage if isinstance(model.result, ModelResult) else {}
    names = ("input_tokens", "output_tokens")
    if not isinstance(usage, dict) or any(type(usage.get(name)) is not int or usage[name] < 0 for name in names):
        return None
    return {name: usage[name] for name in names}


def run(corpus, output_dir, config, model, *, provider="bedrock", region="us-east-1", pricing=None):
    """A fresh output directory is a deliberate new experiment, never a resume."""
    if provider not in {"bedrock", "fixture"}:
        raise ValueError("Unknown evaluation provider")
    if provider == "fixture" and any(case.fixture is None for case in corpus.cases):
        raise ValueError("Offline evaluation requires fixture responses")
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=False)
    (output_dir / "cases").mkdir()
    run_id = uuid.uuid4().hex
    manifest = dict(schema_version="1.0", run_id=run_id, started_at=utc_text(datetime.now(timezone.utc)),
        provider=provider, region=region, corpus_id=corpus.corpus_id, corpus_sha256=corpus.sha256,
        label_source=corpus.label_source, config=config.to_dict(), scoring_version="eps-exact-v1",
        prompt_sha256=hashlib.sha256(SYSTEM_PROMPT.encode()).hexdigest(),
        schema_sha256=hashlib.sha256(json_text(EPS_SCHEMA).encode()).hexdigest(),
        validator_sha256=hashlib.sha256(Path(validation.__file__).read_bytes()).hexdigest(),
        pricing=None if pricing is None else asdict(pricing))
    write_json(output_dir / "run.json", manifest)
    write_json(output_dir / "corpus-snapshot.json", corpus.snapshot)
    results = []
    with SQLiteProcessingRepository(output_dir / "processing.sqlite3") as repository:
        for case in corpus.cases:
            delegate = FixtureModel(case.fixture) if provider == "fixture" else model
            measured = MeasuredModel(delegate)
            worker = FilingPipeline(repository, LocalDocuments(case), measured, NoPublication(), config)
            started = time.perf_counter()
            result = worker.process(case.filing.to_dict(), run_mode="evaluation", run_id=run_id)
            elapsed = time.perf_counter() - started
            job = repository.get_job(result.work_id)
            saved = job["response"]
            response = None if saved is None else saved["response"]
            schema_valid, predicted = False, []
            if saved is not None:
                try:
                    predicted = [fact.to_dict() for fact in response_facts(response, config)]
                    schema_valid = True
                except TechnicalFailure:
                    pass
            accepted = [] if job["completion"] is None else job["completion"]["accepted_facts"]
            usage = usage_of(measured)
            row = dict(case_id=case.case_id, tags=list(case.tags), work_id=result.work_id,
                outcome=result.outcome, acknowledged=result.acknowledge, findings=list(result.findings),
                scores=score(case.expected, response, predicted, accepted, schema_valid=schema_valid),
                calls=measured.calls, model_seconds=measured.seconds, elapsed_seconds=elapsed, usage=usage,
                estimated_cost_usd=None if pricing is None or usage is None else pricing.estimate(usage))
            write_json(output_dir / "cases" / (case.case_id + ".json"), dict(result=row, processing_record=job))
            results.append(row)
            report = make_report(manifest, results, len(corpus.cases))
            write_json(output_dir / "report.json", report)
            (output_dir / "report.md").write_text(markdown(report), encoding="utf-8")
    return report


def make_report(manifest, results, expected_cases):
    summary = summarize(results)
    calls = sum(row["calls"] for row in results)
    known = [row for row in results if row["usage"] is not None]
    unknown = sum(row["calls"] for row in results if row["usage"] is None)
    durations = sorted(value for row in results for value in row["model_seconds"])
    cost = sum((Decimal(row["estimated_cost_usd"]) for row in results if row["estimated_cost_usd"] is not None), Decimal(0))
    summary.update(model_calls=calls, calls_with_unknown_usage=unknown,
        input_tokens=sum(row["usage"]["input_tokens"] for row in known),
        output_tokens=sum(row["usage"]["output_tokens"] for row in known),
        known_estimated_cost_usd=format(cost, "f") if manifest["pricing"] is not None else None,
        estimated_cost_usd=format(cost, "f") if manifest["pricing"] is not None and not unknown else None,
        median_model_seconds=statistics.median(durations) if durations else None,
        p95_model_seconds=durations[math.ceil(len(durations) * .95) - 1] if durations else None,
        elapsed_seconds=sum(row["elapsed_seconds"] for row in results),
        acceptance_rate=ratio(sum(row["outcome"] == "validated" for row in results), len(results)))
    return dict(run=manifest, complete=len(results) == expected_cases, expected_cases=expected_cases,
                summary=summary, cases=list(results))


def markdown(report):
    def number(value):
        return "n/a" if value is None else f"{value:.3f}"
    summary = report["summary"]
    lines = ["# Filing evaluation", "", f'Provider: {report["run"]["provider"]}; labels: {report["run"]["label_source"]}.',
        "Synthetic cases are smoke checks, not a representative quality baseline. Fixture playback does not measure model quality.", "",
        f'Cases: {summary["cases"]}/{report["expected_cases"]}; technical failures: {summary["technical_failures"]}.',
        f'Classification accuracy: {number(summary["classification_accuracy"])}; exact extraction: {number(summary["exact_extraction_accuracy"])}.',
        f'Extraction precision/recall/F1: {number(summary["extraction"]["precision"])}/{number(summary["extraction"]["recall"])}/{number(summary["extraction"]["f1"])}.',
        f'Accepted precision/recall/F1: {number(summary["accepted"]["precision"])}/{number(summary["accepted"]["recall"])}/{number(summary["accepted"]["f1"])}.',
        f'Model calls: {summary["model_calls"]}; known input/output tokens: {summary["input_tokens"]}/{summary["output_tokens"]}; calls with unknown usage: {summary["calls_with_unknown_usage"]}.',
        f'Estimated USD: {summary["estimated_cost_usd"] if summary["estimated_cost_usd"] is not None else "unknown"}; known subtotal: {summary["known_estimated_cost_usd"]}.',
        f'Model latency median/p95 seconds: {number(summary["median_model_seconds"])}/{number(summary["p95_model_seconds"])}.', "",
        "| Case | Exact extraction | Validation | Extracted TP/FP/FN | Accepted TP/FP/FN | Seconds |",
        "| --- | --- | --- | --- | --- | --- |"]
    if report["run"]["label_source"] == "agent_draft":
        lines.insert(4, "These assistant-drafted labels await human review; scores are provisional.")
    for row in report["cases"]:
        def values(group):
            return "/".join(str(row["scores"][group][key]) for key in ("true_positive", "false_positive", "false_negative"))
        lines.append(f'| {row["case_id"]} | {row["scores"]["exact_extraction"]} | {row["outcome"]} | {values("extraction")} | {values("accepted")} | {number(row["elapsed_seconds"])} |')
    return "\n".join(lines) + "\n"
