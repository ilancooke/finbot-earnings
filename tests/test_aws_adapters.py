from dataclasses import replace
from io import BytesIO

import boto3
from botocore.response import StreamingBody
from botocore.stub import Stubber
import pytest

from finbot_earnings.processing.aws_adapters import S3Documents, SNSPublisher
from finbot_earnings.processing.contracts import FilingReady
from finbot_earnings.processing.errors import TechnicalFailure
from tests.processing_helpers import fixture


def test_s3_decodes_key_once_and_closes_stream():
    client = boto3.client("s3")
    artifact = replace(FilingReady.parse(fixture()[0]).artifacts[0], s3_uri="s3://artifacts/a%20b%2520%23%2B.htm", size_bytes=3)
    stream = BytesIO(b"abc")
    with Stubber(client) as stub:
        stub.add_response("get_object", {"Body": StreamingBody(stream, 3), "ContentLength": 3},
                          {"Bucket": "artifacts", "Key": "a b%20#+.htm"})
        assert S3Documents(client, "artifacts").read(artifact, max_bytes=3) == b"abc"
        stub.assert_no_pending_responses()
    assert stream.closed


def test_s3_bounds_bucket_and_mismatch_fail_safely():
    client = boto3.client("s3")
    artifact = FilingReady.parse(fixture()[0]).artifacts[0]
    with Stubber(client) as stub:
        with pytest.raises(TechnicalFailure, match="unexpected_source_bucket"):
            S3Documents(client, "other").read(artifact, max_bytes=1000)
        with pytest.raises(TechnicalFailure, match="stored_object_exceeds_limit"):
            S3Documents(client, "artifacts").read(artifact, max_bytes=1)
        stream = BytesIO(b"abc")
        stub.add_response("get_object", {"Body": StreamingBody(stream, 3), "ContentLength": 3})
        with pytest.raises(TechnicalFailure, match="stored_object_size_mismatch"):
            S3Documents(client, "artifacts").read(artifact, max_bytes=1000)
    assert stream.closed


def test_sns_publishes_exact_saved_payload_and_requires_ack():
    client = boto3.client("sns")
    topic = "arn:aws:sns:us-east-1:123456789012:earnings"
    payload = '{"schema_version":"1.0","literal":"é"}'
    with Stubber(client) as stub:
        stub.add_response("publish", {"MessageId": "ack"}, {"TopicArn": topic, "Message": payload})
        assert SNSPublisher(client, topic).publish(payload) == "ack"
        stub.add_response("publish", {}, {"TopicArn": topic, "Message": payload})
        with pytest.raises(TechnicalFailure, match="missing_publication_acknowledgment"):
            SNSPublisher(client, topic).publish(payload)
        with pytest.raises(TechnicalFailure, match="publication_exceeds_limit"):
            SNSPublisher(client, topic).publish("é" * (256 * 1024))
