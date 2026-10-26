"""Record the reviewed commit, packaged code and immutable extraction configuration."""

from importlib.metadata import version
import json
from pathlib import Path
import subprocess

from scripts.build_lambda import ROOT, asset_hash
from infra.cdk.settings import Settings
from finbot_earnings.processing.fiscal.config import load_config


def main():
    settings = Settings.load(ROOT / "infra/cdk/config.prod.json")
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True))
    manifest = dict(commit=sha, asset_sha256=asset_hash(ROOT / "build/lambda"),
        assembly_sha256=asset_hash(ROOT / "cdk.out"),
        stack_name=settings.stack_name, account=settings.account, region=settings.region,
        source_dirty=dirty, extraction_config=load_config(), fiscal_config_sha256=settings.fiscal_config_sha256,
        consumption_enabled=settings.consumption_enabled,
        python_runtime="python3.13", architecture="x86_64", aws_cdk_lib=version("aws-cdk-lib"),
        cdk_cli=json.loads((ROOT / "package.json").read_text())["devDependencies"]["aws-cdk"])
    path = ROOT / "build/release-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    print(path)


if __name__ == "__main__":
    main()
