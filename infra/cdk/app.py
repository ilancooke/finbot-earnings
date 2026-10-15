"""Explicit account/config synthesis; never looks up or mutates AWS resources."""

import os
from pathlib import Path

from aws_cdk import App, Environment

from infra.cdk.settings import Settings
from infra.cdk.stack import EarningsStack


def main():
    root = Path(__file__).resolve().parents[2]
    settings = Settings.load(os.environ.get("FINBOT_EARNINGS_CONFIG", root / "infra/cdk/config.prod.json"))
    asset = Path(os.environ.get("FINBOT_EARNINGS_ASSET", root / "build/lambda"))
    if not (asset / "finbot_earnings/processing/lambda_handler.py").is_file():
        raise ValueError("Build the Lambda asset with scripts/build_lambda.py before synthesis")
    app = App()
    EarningsStack(app, settings.stack_name, settings=settings, asset_path=asset,
                  env=Environment(account=settings.account, region=settings.region))
    app.synth()


if __name__ == "__main__":
    main()
