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
