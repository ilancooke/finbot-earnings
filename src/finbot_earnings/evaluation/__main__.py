"""Evaluate saved filings locally; only explicit runs use Bedrock inference."""

import argparse
import json
from pathlib import Path
import re

from finbot_earnings.processing.aws_adapters import NovaLiteModel, NOVA_LITE_MODEL_ID, NOVA_PROMPT_VERSION
from finbot_earnings.processing.domain import ExtractionConfig
from finbot_earnings.processing.errors import TechnicalFailure

from .corpus import load_corpus, read_json
from .runner import Pricing, run


class LocalBedrockModel:
    """Resolve AWS credentials and reuse one client only if a case needs inference."""

    def __init__(self, profile, region):
        self.profile, self.region, self.delegate = profile, region, None

    def classify_and_extract(self, request):
        if self.delegate is None:
            import boto3
            from botocore.config import Config
            session = boto3.Session(profile_name=self.profile, region_name=self.region)
            client = session.client("bedrock-runtime", config=Config(connect_timeout=5, read_timeout=180,
                retries={"total_max_attempts": 1, "mode": "adaptive"}))
            self.delegate = NovaLiteModel(client)
        return self.delegate.classify_and_extract(request)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("check", "run"))
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("infra/cdk/config.prod.json"))
    parser.add_argument("--output-dir", type=Path, help="New local directory for one experiment")
    parser.add_argument("--offline", action="store_true", help="Use saved fixture responses instead of Bedrock")
    parser.add_argument("--profile", help="AWS profile; defaults to the normal AWS credential chain")
    parser.add_argument("--input-usd-per-million", help="Current input-token price for the selected model and region")
    parser.add_argument("--output-usd-per-million", help="Current output-token price for the selected model and region")
    args = parser.parse_args(argv)
    try:
        value = read_json(args.config)
        config = ExtractionConfig(**value["extraction"])
        region = value["region"]
        if config.model_id != NOVA_LITE_MODEL_ID or config.prompt_version != NOVA_PROMPT_VERSION:
            raise ValueError("Evaluation currently uses the versioned Nova Lite adapter")
        if not isinstance(region, str) or not re.fullmatch(r"[a-z]{2}-[a-z]+-\d", region):
            raise ValueError("Invalid AWS region")
        corpus = load_corpus(args.corpus, config, offline=args.offline)
        pricing = None
        if args.input_usd_per_million is not None or args.output_usd_per_million is not None:
            if args.input_usd_per_million is None or args.output_usd_per_million is None:
                raise ValueError("Supply both token prices or neither")
            pricing = Pricing(args.input_usd_per_million, args.output_usd_per_million)
        if args.operation == "check":
            print(json.dumps(dict(corpus_id=corpus.corpus_id, cases=len(corpus.cases),
                label_source=corpus.label_source, corpus_sha256=corpus.sha256, model_id=config.model_id), indent=2))
            return 0
        if args.output_dir is None:
            raise ValueError("run requires --output-dir")
        report = run(corpus, args.output_dir, config, LocalBedrockModel(args.profile, region),
                     provider="fixture" if args.offline else "bedrock", region=region, pricing=pricing)
    except (OSError, ValueError, TypeError, KeyError, TechnicalFailure) as exc:
        parser.error(str(exc))
    print(json.dumps(report["summary"], indent=2))
    print(f"Reports: {args.output_dir / 'report.md'} and {args.output_dir / 'report.json'}")
    return 1 if report["summary"]["technical_failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
