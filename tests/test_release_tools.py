from pathlib import Path

import pytest
import yaml

from scripts.build_lambda import asset_hash, build
from scripts.verify_release import verify

ROOT = Path(__file__).resolve().parents[1]


def test_build_refuses_to_replace_unrelated_directory(tmp_path):
    output = tmp_path / "user-files"
    output.mkdir()
    (output / "important.txt").write_text("preserve me")
    with pytest.raises(ValueError, match="Refusing to replace"):
        build(output)
    assert (output / "important.txt").read_text() == "preserve me"


def test_asset_digest_changes_with_contents_and_ignores_host_directory(tmp_path):
    first, second = tmp_path / "first", tmp_path / "second"
    first.mkdir()
    second.mkdir()
    for path in (first, second):
        (path / "handler.py").write_text("version1")
    assert asset_hash(first) == asset_hash(second)
    (second / "handler.py").write_text("version2")
    assert asset_hash(first) != asset_hash(second)


def test_tampered_or_wrong_commit_release_cannot_be_deployed(tmp_path):
    import json
    assembly = tmp_path / "cdk.out"
    assembly.mkdir()
    (assembly / "manifest.json").write_text('{"version":"1"}')
    (tmp_path / "release-manifest.json").write_text(json.dumps({"commit": "abc", "assembly_sha256": asset_hash(assembly)}))
    assert verify(tmp_path, "abc")["commit"] == "abc"
    with pytest.raises(ValueError, match="commit mismatch"):
        verify(tmp_path, "different")
    (assembly / "manifest.json").write_text('{"version":"tampered"}')
    with pytest.raises(ValueError, match="checksum mismatch"):
        verify(tmp_path, "abc")


def workflow(name):
    return yaml.safe_load((ROOT / ".github/workflows" / name).read_text())


def test_ci_has_no_cloud_credentials_and_produces_self_contained_release():
    ci = workflow("ci.yml")
    assert ci["permissions"] == {"contents": "read"}
    steps = ci["jobs"]["check"]["steps"]
    assert not any("configure-aws-credentials" in step.get("uses", "") for step in steps)
    upload = next(step["with"] for step in steps if "upload-artifact" in step.get("uses", ""))
    assert upload["path"] == "build/release/" and upload["include-hidden-files"]
    commands = "\n".join(step.get("run", "") for step in steps)
    assert "python -m pytest" in commands and "npm run synth" in commands
    assert "cp -R cdk.out build/release/cdk.out" in commands


def test_deployment_reuses_ci_artifact_and_requires_review_before_apply():
    deploy = workflow("deploy.yml")
    assert deploy["on"] == {"workflow_dispatch": {"inputs": {"commit": {
        "description": "Full main commit SHA with successful CI (blank uses current main)",
        "required": False, "type": "string"}}}}
    assert deploy["concurrency"]["cancel-in-progress"] is False
    prepare, apply = deploy["jobs"]["prepare"], deploy["jobs"]["deploy"]
    assert apply["needs"] == "prepare" and apply["environment"] == "production"
    preparation = "\n".join(step.get("run", "") for step in prepare["steps"])
    application = "\n".join(step.get("run", "") for step in apply["steps"])
    assert "gh run download" in preparation and "event=push" in preparation
    assert "--method template" in preparation and "--app release/cdk.out" in preparation
    assert "cdk deploy" not in preparation
    assert "--app release/cdk.out" in application and "build_lambda" not in application
