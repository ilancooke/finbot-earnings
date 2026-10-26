"""Injected S3/SNS clients; construction never creates a session or calls AWS."""

from urllib.parse import unquote, urlsplit

from .errors import TechnicalFailure


class S3Documents:
    def __init__(self, client, bucket):
        self.client, self.bucket = client, bucket

    def read(self, artifact, *, max_bytes):
        parts = urlsplit(artifact.s3_uri)
        if parts.netloc != self.bucket:
            raise TechnicalFailure("unexpected_source_bucket", retryable=False)
        if artifact.size_bytes > max_bytes:
            raise TechnicalFailure("stored_object_exceeds_limit", retryable=False)
        response = self.client.get_object(Bucket=self.bucket, Key=unquote(parts.path[1:], errors="strict"))
        body = response["Body"]
        try:
            if response.get("ContentLength") != artifact.size_bytes:
                raise TechnicalFailure("stored_object_size_mismatch")
            data = body.read(min(max_bytes, artifact.size_bytes) + 1)
            if len(data) != artifact.size_bytes:
                raise TechnicalFailure("stored_object_size_mismatch")
            return data
        finally:
            body.close()


class SNSPublisher:
    def __init__(self, client, topic_arn):
        self.client, self.topic_arn = client, topic_arn

    def publish(self, payload):
        if len(payload.encode("utf-8")) > 256 * 1024:
            raise TechnicalFailure("publication_exceeds_limit", retryable=False)
        response = self.client.publish(TopicArn=self.topic_arn, Message=payload)
        acknowledgment = response.get("MessageId")
        if not isinstance(acknowledgment, str) or not acknowledgment.strip():
            raise TechnicalFailure("missing_publication_acknowledgment")
        return acknowledgment
