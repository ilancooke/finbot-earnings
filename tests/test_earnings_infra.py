from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile

# Set before importing jsii, including during test collection on macOS.
os.environ.setdefault("JSII_RUNTIME_PACKAGE_CACHE", str(Path(tempfile.gettempdir()) / "finbot-earnings-jsii"))

from aws_cdk import App, Environment
from aws_cdk.assertions import Match, Template
import pytest

from infra.cdk.settings import Settings
from infra.cdk.stack import EarningsStack

CONFIG = Path(__file__).resolve().parents[1] / "infra/cdk/config.prod.json"


@pytest.fixture
def template(tmp_path):
    asset = tmp_path / "asset"
    asset.mkdir()
    (asset / "handler.py").write_text("def handler(event, context): return {}\n")
    app = App(outdir=str(tmp_path / "assembly"))
    settings = Settings.load(CONFIG)
    stack = EarningsStack(app, settings.stack_name, settings=settings, asset_path=asset,
                          env=Environment(account=settings.account, region=settings.region))
    yield Template.from_stack(stack)


def test_queue_subscription_alias_and_limits(template):
    template.has_resource_properties("AWS::Lambda::EventSourceMapping", {
        "BatchSize": 1, "Enabled": False, "FunctionResponseTypes": ["ReportBatchItemFailures"],
        "ScalingConfig": {"MaximumConcurrency": 2}, "FunctionName": {"Fn::Join": ["", Match.array_with([":production"])]}})
    template.has_resource_properties("AWS::Lambda::Function", {
        "Runtime": "python3.13", "Architectures": ["x86_64"], "Timeout": 300,
        "ReservedConcurrentExecutions": Match.absent(), "LoggingConfig": Match.object_like({"LogFormat": "JSON"})})
    template.has_resource_properties("AWS::SQS::Queue", {
        "VisibilityTimeout": 1800, "MessageRetentionPeriod": 1209600, "SqsManagedSseEnabled": True,
        "RedrivePolicy": Match.object_like({"maxReceiveCount": 5})})
    template.has_resource_properties("AWS::SNS::Subscription", {
        "TopicArn": Settings.load(CONFIG).filing_topic_arn, "RawMessageDelivery": False,
        "RedrivePolicy": Match.object_like({"deadLetterTargetArn": Match.any_value()})})
    template.has_resource_properties("AWS::Lambda::Alias", {"Name": "production"})
    template.resource_count_is("AWS::Lambda::Version", 1)


def test_state_is_retained_and_source_resources_are_not_owned(template):
    template.has_resource("AWS::DynamoDB::Table", {
        "DeletionPolicy": "Retain", "UpdateReplacePolicy": "Retain", "Properties": Match.object_like({
            "DeletionProtectionEnabled": True, "BillingMode": "PAY_PER_REQUEST",
            "PointInTimeRecoverySpecification": {"PointInTimeRecoveryEnabled": True}})})
    template.resource_count_is("AWS::S3::Bucket", 0)
    template.resource_count_is("AWS::SNS::Topic", 2)
    template.resource_count_is("AWS::CloudWatch::Alarm", 9)


def statements(template, kind="AWS::IAM::Policy"):
    return [s for p in template.find_resources(kind).values()
            for s in p["Properties"]["PolicyDocument"]["Statement"]]


def test_fiscal_runtime_permissions_and_delivery_policies(template):
    worker = statements(template)
    for statement in worker:
        assert statement["Resource"] != "*"
        assert "bedrock" not in json.dumps(statement)
        assert "s3:PutObject" not in statement["Action"]
        assert "dynamodb:Scan" not in statement["Action"]
    table = next(s for s in worker if "dynamodb:PutItem" in s["Action"])
    assert {"dynamodb:Query", "dynamodb:DeleteItem"} <= set(table["Action"])
    secret = next(s for s in worker if s["Action"] == "secretsmanager:GetSecretValue")
    assert isinstance(secret["Resource"], dict) and "Ref" in secret["Resource"]
    queue = [s for s in statements(template, "AWS::SQS::QueuePolicy") if s["Effect"] == "Allow"]
    assert len(queue) == 4
    assert all(s["Principal"] == {"Service": "sns.amazonaws.com"} for s in queue)
    assert all(s["Condition"]["StringEquals"]["aws:SourceAccount"] == Settings.load(CONFIG).account for s in queue)
    assert sum(s["Condition"]["ArnEquals"]["aws:SourceArn"] == Settings.load(CONFIG).filing_topic_arn for s in queue) == 2
    alarm = [s for s in statements(template, "AWS::SNS::TopicPolicy") if s["Effect"] == "Allow"]
    assert len(alarm) == 9
    assert all(s["Principal"] == {"Service": "cloudwatch.amazonaws.com"} for s in alarm)
    assert all("aws:SourceArn" in s["Condition"]["ArnEquals"] for s in alarm)


@pytest.mark.parametrize("change", [
    lambda v: v.update(fiscal_config_sha256="0" * 64),
    lambda v: v.update(consumption_enabled="false"),
    lambda v: v.update(filing_topic_arn="arn:aws:sns:us-west-2:559007813222:other"),
    lambda v: v.update(openai_secret_name="shared-key"),
    lambda v: v.update(bedrock_resource_arns=["*"]),
    lambda v: v.update(alarm_email="other@example.com"),
])
def test_invalid_activation_or_permissions_rejected(tmp_path, change):
    value = json.loads(CONFIG.read_text())
    change(value)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        Settings.load(path)


def test_enabled_update_preserves_resource_identity(tmp_path, template):
    app = App(outdir=str(tmp_path / "enabled"))
    settings = replace(Settings.load(CONFIG), consumption_enabled=True)
    asset = tmp_path / "code"
    asset.mkdir()
    (asset / "handler.py").write_text("# fixture")
    enabled = Template.from_stack(EarningsStack(app, settings.stack_name, settings=settings, asset_path=asset,
        env=Environment(account=settings.account, region=settings.region)))
    enabled.has_resource_properties("AWS::Lambda::EventSourceMapping", {"Enabled": True})
    for kind in ("AWS::DynamoDB::Table", "AWS::SQS::Queue", "AWS::SNS::Topic", "AWS::SecretsManager::Secret"):
        assert enabled.find_resources(kind) == template.find_resources(kind)


def test_empty_secret_operator_access_and_alarm_subscription(template):
    secret = next(iter(template.find_resources("AWS::SecretsManager::Secret").values()))
    assert secret["DeletionPolicy"] == "Retain"
    assert "SecretString" not in secret["Properties"] and "GenerateSecretString" not in secret["Properties"]
    assert secret["Properties"]["Name"] == Settings.load(CONFIG).openai_secret_name
    template.has_resource_properties("AWS::SNS::Subscription", {"Protocol": "email", "Endpoint": "ilancooke@gmail.com"})
    template.has_resource_properties("AWS::SNS::Subscription", {"Protocol": "sqs", "RawMessageDelivery": True})
    policies = template.find_resources("AWS::IAM::ManagedPolicy")
    assert len(policies) == 2
    inspection = next(p for k, p in policies.items() if "OperatorInspection" in k)
    assert "secretsmanager" not in json.dumps(inspection)
    assert "DeleteMessage" not in json.dumps(inspection)
    assert "Scan" not in json.dumps(policies)
    template.has_resource_properties("AWS::SQS::Queue", {"QueueName": "finbot-earnings-prod-output", "MessageRetentionPeriod": 1209600})


def test_committed_fiscal_configuration_starts_disabled(template):
    settings = Settings.load(CONFIG)
    assert not settings.consumption_enabled
    worker = next(iter(template.find_resources("AWS::Lambda::Function").values()))["Properties"]
    env = worker["Environment"]["Variables"]
    assert env["EARNINGS_FISCAL_CONFIG_SHA256"] == settings.fiscal_config_sha256
    assert "EARNINGS_OPENAI_SECRET_ARN" in env
    assert "EARNINGS_EXTRACTION_CONFIG" not in env


def test_release_roles_use_verified_immutable_oidc_subjects(tmp_path):
    from infra.cdk.access_app import ReleaseAccessStack
    app = App(outdir=str(tmp_path / "access"))
    t = Template.from_stack(ReleaseAccessStack(app, "access", env=Environment(account="559007813222", region="us-east-1")))
    roles = t.find_resources("AWS::IAM::Role")
    subjects = {r["Properties"]["AssumeRolePolicyDocument"]["Statement"][0]["Condition"]["StringEquals"]["token.actions.githubusercontent.com:sub"] for r in roles.values()}
    assert subjects == {"repo:ilancooke@8453151/finbot-earnings@1350331204:ref:refs/heads/main",
                        "repo:ilancooke@8453151/finbot-earnings@1350331204:environment:production"}
    assert "finbot-filings" not in json.dumps(t.to_json())
    assert "AdministratorAccess" not in json.dumps(t.to_json())
