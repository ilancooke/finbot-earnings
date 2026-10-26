"""Verify that a downloaded cloud assembly matches the exact CI release."""

import argparse
import json
from pathlib import Path

from scripts.build_lambda import asset_hash


def verify(directory, commit):
    directory = Path(directory)
    manifest = json.loads((directory / "release-manifest.json").read_text())
    if manifest["commit"] != commit:
        raise ValueError("Release commit mismatch")
    if asset_hash(directory / "cdk.out") != manifest["assembly_sha256"]:
        raise ValueError("Release cloud assembly checksum mismatch")
    assembly = directory / "cdk.out"
    assets = json.loads((assembly / (manifest["stack_name"] + ".assets.json")).read_text())
    paths = [assembly / item["source"]["path"] for item in assets["files"].values()
             if item["source"]["packaging"] == "zip"]
    if len(paths) != 1 or not paths[0].resolve().is_relative_to(assembly.resolve()) or asset_hash(paths[0]) != manifest["asset_sha256"]:
        raise ValueError("Release Lambda asset checksum mismatch")
    template = json.loads((assembly / (manifest["stack_name"] + ".template.json")).read_text())
    resources = list(template["Resources"].values())
    workers = [r["Properties"] for r in resources if r["Type"] == "AWS::Lambda::Function"]
    mappings = [r["Properties"] for r in resources if r["Type"] == "AWS::Lambda::EventSourceMapping"]
    if len(workers) != 1 or len(mappings) != 1 or mappings[0]["Enabled"] != manifest["consumption_enabled"]:
        raise ValueError("Release consumption configuration mismatch")
    if workers[0]["Environment"]["Variables"]["EARNINGS_FISCAL_CONFIG_SHA256"] != manifest["fiscal_config_sha256"]:
        raise ValueError("Release fiscal configuration mismatch")
    if manifest.get("source_dirty", True):
        raise ValueError("Release source must be clean successful-CI input")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    verify(args.directory, args.commit)
    print("Release commit and assembly checksum verified")


if __name__ == "__main__":
    main()
