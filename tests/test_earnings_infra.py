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
        "ReservedConcurrentExecutions": 2, "LoggingConfig": Match.object_like({"LogFormat": "JSON"})})
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
    template.resource_count_is("AWS::CloudWatch::Alarm", 4)


def test_runtime_permissions_are_scoped_to_nova_lite(template):
    policies = template.find_resources("AWS::IAM::Policy")
    statements = [statement for policy in policies.values() for statement in policy["Properties"]["PolicyDocument"]["Statement"]]
    for statement in statements:
        assert statement["Resource"] != "*"
        if "bedrock:InvokeModel" in statement["Action"]:
            assert statement["Resource"] == Settings.load(CONFIG).bedrock_resource_arns[0]
        assert "s3:PutObject" not in statement["Action"]
        assert "dynamodb:Scan" not in statement["Action"]
    assert sum("bedrock:InvokeModel" in s["Action"] for s in statements) == 1
    queue_policies = template.find_resources("AWS::SQS::QueuePolicy")
    receive = [s for p in queue_policies.values() for s in p["Properties"]["PolicyDocument"]["Statement"] if s["Effect"] == "Allow"]
    assert len(receive) == 2
    for statement in receive:
        assert statement["Condition"]["ArnEquals"]["aws:SourceArn"] == Settings.load(CONFIG).filing_topic_arn
        assert statement["Condition"]["StringEquals"]["aws:SourceAccount"] == Settings.load(CONFIG).account
    topic_policies = template.find_resources("AWS::SNS::TopicPolicy")
    alarm_publish = [statement for policy in topic_policies.values()
        for statement in policy["Properties"]["PolicyDocument"]["Statement"] if statement["Effect"] == "Allow"]
    assert len(alarm_publish) == 4
    assert all(statement["Principal"] == {"Service": "cloudwatch.amazonaws.com"} for statement in alarm_publish)
    assert all("aws:SourceArn" in statement["Condition"]["ArnEquals"] for statement in alarm_publish)


@pytest.mark.parametrize("change", [
    lambda value: (value.update(consumption_enabled=True), value["extraction"].update(model_id="unselected")),
    lambda value: value["extraction"].update(lease_seconds=300),
    lambda value: value.update(filing_topic_arn="arn:aws:sns:us-west-2:559007813222:other"),
    lambda value: value.update(bedrock_resource_arns=["*"]),
    lambda value: value.update(bedrock_resource_arns=[]),
])
def test_invalid_activation_or_permissions_rejected(tmp_path, change):
    value = json.loads(CONFIG.read_text())
    change(value)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(value))
    with pytest.raises(ValueError):
        Settings.load(path)


def test_selected_model_grants_only_explicit_resources(tmp_path):
    value = json.loads(CONFIG.read_text())
    arn = "arn:aws:bedrock:us-east-1::foundation-model/example-model"
    value["extraction"]["model_id"] = "example-model"
    value.update(bedrock_resource_arns=[arn], consumption_enabled=True)
    path = tmp_path / "config.json"
    path.write_text(json.dumps(value))
    asset = tmp_path / "asset"
    asset.mkdir()
    (asset / "handler.py").write_text("# fixture\n")
    app = App(outdir=str(tmp_path / "out"))
    settings = Settings.load(path)
    stack = EarningsStack(app, "Selected", settings=settings, asset_path=asset,
                          env=Environment(account=settings.account, region=settings.region))
    synthesized = Template.from_stack(stack)
    synthesized.has_resource_properties("AWS::IAM::Policy", {"PolicyDocument": Match.object_like({"Statement": Match.array_with([
        Match.object_like({"Action": "bedrock:InvokeModel", "Resource": arn, "Effect": "Allow"})])})})
    synthesized.has_resource_properties("AWS::Lambda::EventSourceMapping", {"Enabled": True})


def test_committed_nova_configuration_stays_disabled(template):
    settings = Settings.load(CONFIG)
    assert settings.extraction.model_id == "amazon.nova-lite-v1:0"
    assert settings.extraction.prompt_version == "eps-nova-tool-v1"
    assert settings.extraction.max_documents == 5
    assert not settings.consumption_enabled
    template.has_resource_properties("AWS::Lambda::Function", {"Environment": {"Variables": Match.object_like({
        "EARNINGS_EXTRACTION_CONFIG": Match.any_value()})}})
