"""Lazy direct-provider wiring. Construction and inspection never read the secret."""
import os

from .aws_adapters import S3Documents, SNSPublisher
from .errors import TechnicalFailure
from .fiscal_consumer import FiscalConsumer


class FiscalS3Documents(S3Documents):
    def read(self, artifact, *, max_bytes):
        from botocore.exceptions import BotoCoreError, ClientError
        try:
            return super().read(artifact, max_bytes=max_bytes)
        except ClientError as exc:
            code = exc.response.get("Error", {}).get("Code")
            if code in {"NoSuchKey", "NoSuchBucket", "404", "NotFound"}:
                raise TechnicalFailure("source_object_missing") from None
            raise TechnicalFailure("source_read_failed", retryable=code not in {"AccessDenied", "InvalidAccessKeyId", "KMSAccessDeniedException"}) from None
        except BotoCoreError:
            raise TechnicalFailure("source_read_failed") from None


class SecretFiscalExtractor:
    def __init__(self, secrets, secret_arn):
        if not isinstance(secret_arn, str) or not secret_arn.startswith("arn:aws:secretsmanager:"):
            raise ValueError("dedicated OpenAI secret ARN required")
        self.secrets, self.secret_arn = secrets, secret_arn

    def extract(self, *args, **kwargs):
        from .fiscal import OpenAIFiscalExtractor, make_client
        # Resolve AWSCURRENT on each attempt so explicit redrive sees rotated keys.
        # Never retain or log the credential in processing/configuration records.
        value = self.secrets.get_secret_value(SecretId=self.secret_arn, VersionStage="AWSCURRENT")
        key = value.get("SecretString")
        if not isinstance(key, str) or not key.strip():
            raise TechnicalFailure("provider_secret_invalid", retryable=False)
        with make_client(key) as client:
            return OpenAIFiscalExtractor(client).extract(*args, **kwargs)


def make_repository(session=None):
    import boto3
    from botocore.config import Config
    from .fiscal_stores import DynamoDBFiscalRepository
    session = session or boto3.Session()
    short = Config(connect_timeout=3, read_timeout=10, retries={"total_max_attempts": 2, "mode": "standard"})
    return DynamoDBFiscalRepository(session.resource("dynamodb", config=short).meta.client, os.environ["EARNINGS_TABLE_NAME"])


def build_consumer(repository=None, session=None):
    import boto3
    from botocore.config import Config
    from .fiscal.config import digest, load_config
    config = load_config()
    if os.environ["EARNINGS_FISCAL_CONFIG_SHA256"] != digest(config):
        raise ValueError("configured fiscal digest differs from packaged configuration")
    session = session or boto3.Session()
    short = Config(connect_timeout=3, read_timeout=10, retries={"total_max_attempts": 2, "mode": "standard"})
    return FiscalConsumer(repository or make_repository(session),
        FiscalS3Documents(session.client("s3", config=short), os.environ["EARNINGS_SOURCE_BUCKET"]),
        SecretFiscalExtractor(session.client("secretsmanager", config=short), os.environ["EARNINGS_OPENAI_SECRET_ARN"]),
        SNSPublisher(session.client("sns", config=short), os.environ["EARNINGS_TOPIC_ARN"]),
        config=config, expected_topic_arn=os.environ["FILING_READY_TOPIC_ARN"])
