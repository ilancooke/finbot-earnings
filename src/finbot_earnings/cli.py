from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from dotenv import find_dotenv, load_dotenv

from .config import Settings, load_settings
from .extractors.base import EarningsExtractor
from .extractors.openai import OpenAIEarningsExtractor, PROMPT_VERSION, SCHEMA_VERSION
from .models import EarningsExtraction, ParsedArtifact
from .pipeline import EarningsPipeline, Watcher
from .sources.base import HTTPFetcher, HTTPResponse
from .sources.nvidia_ir import NVIDIA_PRESS_RELEASE_RSS, NvidiaIRSource
from .sources.sec import SECSource
from .storage import ArtifactStore


class _UTCFormatter(logging.Formatter):
    converter = time.gmtime

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        rendered = time.strftime("%H:%M:%S", self.converter(record.created))
        return f"{rendered}.{int(record.msecs):03d}Z"


def configure_logging(debug: bool = False) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(_UTCFormatter("[%(asctime)s] %(message)s"))
    logger = logging.getLogger("finbot_earnings")
    logger.handlers[:] = [handler]
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.propagate = False


def load_environment() -> Path | None:
    """Load a working-directory .env, overriding inherited environment values."""
    dotenv_path = find_dotenv(usecwd=True)
    if not dotenv_path:
        return None
    load_dotenv(dotenv_path, override=True)
    return Path(dotenv_path)


def _runtime(settings: Settings, ticker: str, *, extraction: bool = True):
    company = settings.company(ticker)
    if not settings.sec_user_agent:
        raise SystemExit("SEC_USER_AGENT is required, e.g. 'finbot-earnings you@example.com'")
    fetcher = HTTPFetcher(settings.sec_user_agent)
    extractor = OpenAIEarningsExtractor(settings.openai_model) if extraction else None
    store = ArtifactStore(settings.data_dir)
    pipeline = EarningsPipeline(store, fetcher, extractor)
    sources = [SECSource(company.ticker, company.cik, fetcher)]
    if company.ir_adapter == "nvidia":
        sources.insert(0, NvidiaIRSource(fetcher))
    return store, pipeline, sources


class _FixtureFetcher(HTTPFetcher):
    def __init__(self, responses: dict[str, tuple[bytes, str]]):
        super().__init__("finbot-earnings fixtures@example.com")
        self.responses = responses

    def get(self, url: str, headers=None) -> HTTPResponse:
        try:
            body, content_type = self.responses[url]
        except KeyError as exc:
            raise RuntimeError(f"fixture URL not mapped: {url}") from exc
        return HTTPResponse(body, 200, {"Content-Type": content_type}, url)


class _FixtureExtractor(EarningsExtractor):
    provider = "fixture"
    display_name = "fixture"

    def __init__(self):
        self.calls = 0
        self.model = "fixture-model"

    def extract(self, artifact: ParsedArtifact) -> EarningsExtraction:
        self.calls += 1
        data = {
            "ticker": "NVDA", "fiscal_period_raw": "First quarter fiscal 2027",
            "facts": [
                {"canonical_name": "revenue", "reported_label": "Revenue", "value_raw": "$81.6 billion", "value_numeric": 81600000000, "unit": "USD", "period_raw": "first quarter fiscal 2027", "gaap_status": "GAAP", "source_locator": "opening summary"},
                {"canonical_name": "segment_revenue:data_center", "reported_label": "Data Center revenue", "value_raw": "$75.2 billion", "value_numeric": 75200000000, "unit": "USD", "period_raw": "first quarter fiscal 2027", "gaap_status": None, "source_locator": "highlights"},
            ],
            "guidance": [{"canonical_name": "revenue", "value_raw": "$91.0 billion, plus or minus 2%", "value_numeric": 91000000000, "unit": "USD", "period_raw": "second quarter fiscal 2027", "range_low": 89180000000, "range_high": 92820000000, "gaap_status": None, "source_locator": "outlook"}],
            "highlights": ["Record Data Center revenue"],
        }
        return EarningsExtraction.from_provider_dict(
            data, artifact=artifact, prompt_version=PROMPT_VERSION,
            schema_version=SCHEMA_VERSION, model=self.model, provider=self.provider,
            usage={"input_tokens": 100, "output_tokens": 50, "total_tokens": 150},
        )


def _fixture_runtime(data_dir: Path, fixture_dir: Path):
    submissions = (fixture_dir / "sec_submissions.json").read_bytes()
    index = (fixture_dir / "sec_index.json").read_bytes()
    rss = (fixture_dir / "nvidia_rss.xml").read_bytes()
    release = (fixture_dir / "nvda_release.html").read_bytes()
    cik = "0001045810"
    base = "https://www.sec.gov/Archives/edgar/data/1045810/000104581026000099"
    responses = {
        NVIDIA_PRESS_RELEASE_RSS: (rss, "application/xml"),
        "https://investor.nvidia.com/news/fixture-results": (release, "text/html"),
        "https://data.sec.gov/submissions/CIK0001045810.json": (submissions, "application/json"),
        f"{base}/index.json": (index, "application/json"),
        f"{base}/nvda-20260826.htm": (release, "text/html"),
        f"{base}/q2fy27pr.htm": (release, "text/html"),
        f"{base}/q2fy27cfocommentary.htm": (release, "text/html"),
    }
    fetcher = _FixtureFetcher(responses)
    extractor = _FixtureExtractor()
    store = ArtifactStore(data_dir)
    pipeline = EarningsPipeline(store, fetcher, extractor, retry_delay_seconds=0)
    sources = [NvidiaIRSource(fetcher), SECSource("NVDA", cik, fetcher)]
    return store, pipeline, sources, extractor


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="earnings", description="Official earnings artifact ingestion")
    parser.add_argument("--config", type=Path, help="company TOML path")
    parser.add_argument("--debug", action="store_true")
    sub = parser.add_subparsers(dest="command", required=True)
    watch = sub.add_parser("watch", help="continuously watch configured official sources")
    watch.add_argument("ticker")
    watch.add_argument("--interval", type=float)
    watch.add_argument("--no-extract", action="store_true")
    poll = sub.add_parser("poll", help="poll sources once")
    poll.add_argument("ticker")
    poll.add_argument("--include-existing", action="store_true", help="process current history instead of establishing a baseline")
    poll.add_argument("--no-extract", action="store_true")
    replay = sub.add_parser("replay", help="reparse a stored raw artifact without redownloading")
    replay.add_argument("artifact_id")
    replay.add_argument("--extract", action="store_true", help="make a new paid extraction run")
    listing = sub.add_parser("list-artifacts", help="list persisted artifacts")
    listing.add_argument("ticker", nargs="?")
    timeline = sub.add_parser("show-timeline", help="show the latest event timeline")
    timeline.add_argument("ticker")
    demo = sub.add_parser("demo", help="run the offline NVDA IR+SEC vertical slice")
    demo.add_argument("ticker", nargs="?", default="NVDA")
    demo.add_argument("--data-dir", type=Path)
    demo.add_argument("--fixtures", type=Path, default=Path("tests/fixtures"))
    return parser


def main(argv: list[str] | None = None) -> None:
    load_environment()
    args = build_parser().parse_args(argv)
    configure_logging(args.debug)
    settings = load_settings(args.config)
    if args.command == "demo":
        data_dir = args.data_dir or (settings.data_dir / "fixture-demo")
        store, pipeline, sources, extractor = _fixture_runtime(data_dir, args.fixtures)
        try:
            for source in sources:
                pipeline.poll_source(source, args.ticker, baseline_if_new=False)
                pipeline.poll_source(source, args.ticker, baseline_if_new=False)
            print(json.dumps({"artifacts": len(store.list_artifacts(args.ticker)), "extraction_calls": extractor.calls, "timeline": store.timeline(args.ticker)}, indent=2))
        finally:
            store.close()
        return
    if args.command in {"list-artifacts", "show-timeline"}:
        store = ArtifactStore(settings.data_dir)
        try:
            if args.command == "list-artifacts":
                records = store.list_artifacts(args.ticker)
                print(json.dumps([{"artifact_id": r.artifact_id, "ticker": r.ticker, "type": r.artifact_type.value, "state": r.state.value, "event_id": r.event_id, "source_url": r.source_url} for r in records], indent=2))
            else:
                print(json.dumps(store.timeline(args.ticker), indent=2))
        finally:
            store.close()
        return
    extraction = not getattr(args, "no_extract", False) and (args.command != "replay" or args.extract)
    if args.command == "replay" and not args.extract:
        store = ArtifactStore(settings.data_dir)
        pipeline = EarningsPipeline(store, HTTPFetcher("finbot-earnings replay@localhost"), None)
        try:
            parsed = pipeline.replay(args.artifact_id, extract=False)
            print(json.dumps({"artifact_id": parsed.artifact_id, "parser_version": parsed.parser_version, "characters": len(parsed.text)}, indent=2))
        finally:
            store.close()
        return
    ticker = getattr(args, "ticker", "NVDA")
    store, pipeline, sources = _runtime(settings, ticker, extraction=extraction)
    try:
        if args.command == "watch":
            Watcher(ticker, pipeline, sources, args.interval or settings.poll_interval_seconds).run()
        elif args.command == "poll":
            total = sum(pipeline.poll_source(source, ticker, baseline_if_new=not args.include_existing) for source in sources)
            print(f"processed={total}")
        elif args.command == "replay":
            parsed = pipeline.replay(args.artifact_id, extract=args.extract)
            print(f"replayed artifact={parsed.artifact_id} parser={parsed.parser_version}")
    finally:
        store.close()
