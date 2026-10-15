"""SQS partial-batch handler and explicit, publication-free evaluation entry point."""

from dataclasses import asdict
from functools import lru_cache
import logging
import os

import boto3
from botocore.config import Config

from .aws_adapters import NovaLiteModel, S3Documents, SNSPublisher
from .contracts import fields, json_value
from .domain import ExtractionConfig
from .dynamodb_store import DynamoDBProcessingRepository
from .pipeline import FilingPipeline

LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def runtime():
    # No clients or credentials are resolved at import time. Reuse clients in
    # warm invocations; the Lambda role supplies temporary credentials.
    extraction = ExtractionConfig(**json_value(os.environ["EARNINGS_EXTRACTION_CONFIG"]))
    if extraction.model_id == "unselected":
        raise ValueError("Select a structured-output Bedrock model before evaluation or consumption")
    short = Config(connect_timeout=3, read_timeout=10, retries={"total_max_attempts": 2, "mode": "standard"})
    inference = Config(connect_timeout=5, read_timeout=180, retries={"total_max_attempts": 1, "mode": "adaptive"})
    session = boto3.Session()
    repository = DynamoDBProcessingRepository(session.resource("dynamodb", config=short).meta.client,
                                              os.environ["EARNINGS_TABLE_NAME"])
    return FilingPipeline(repository,
        S3Documents(session.client("s3", config=short), os.environ["EARNINGS_SOURCE_BUCKET"]),
        NovaLiteModel(session.client("bedrock-runtime", config=inference)),
        SNSPublisher(session.client("sns", config=short), os.environ["EARNINGS_TOPIC_ARN"]),
        extraction, expected_topic_arn=os.environ["FILING_READY_TOPIC_ARN"])


def handler(event, context):
    if isinstance(event, dict) and event.get("operation") == "evaluate":
        fields(event, ("operation", "filing", "run_id"))
        result = runtime().process(event["filing"], run_mode="evaluation", run_id=event["run_id"])
        return asdict(result)
    if not isinstance(event, dict) or not isinstance(event.get("Records"), list) or not event["Records"]:
        raise ValueError("Expected SQS records or explicit evaluation request")
    failures = []
    for record in event["Records"]:
        # An invalid identifier cannot be expressed as a partial failure: reject
        # the whole invocation instead of accidentally acknowledging the batch.
        identifier = record.get("messageId")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("Missing SQS message identifier")
        try:
            if record.get("eventSource") != "aws:sqs" or record.get("eventSourceARN") != os.environ["EARNINGS_QUEUE_ARN"]:
                raise ValueError("Unexpected queue")
            wrapper = json_value(record["body"])
            if not isinstance(wrapper, dict) or wrapper.get("Type") != "Notification" or wrapper.get("TopicArn") != os.environ["FILING_READY_TOPIC_ARN"]:
                raise ValueError("Expected wrapped notification from filing-ready topic")
            if context.get_remaining_time_in_millis() < 240_000:
                failures.append({"itemIdentifier": identifier})
                continue
            result = runtime().process(wrapper)
            LOGGER.info("Filing message processed", extra={"message_id": identifier, "work_id": result.work_id,
                "outcome": result.outcome, "exhausted": result.exhausted})
            if not result.acknowledge:
                failures.append({"itemIdentifier": identifier})
        except Exception as exc:
            LOGGER.warning("Filing message deferred", extra={"message_id": identifier, "error_type": type(exc).__name__})
            failures.append({"itemIdentifier": identifier})
    return {"batchItemFailures": failures}
