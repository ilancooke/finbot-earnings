"""SQS partial-batch handler for complete FilingReady snapshots."""

from functools import lru_cache
import logging
import os
import time

from .contracts import json_value

LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def runtime():
    from .fiscal_runtime import build_consumer
    return build_consumer()


def handler(event, context):
    if not isinstance(event, dict) or not isinstance(event.get("Records"), list) or not event["Records"]:
        raise ValueError("Expected nonempty SQS records")
    failures = []
    for record in event["Records"]:
        started = time.monotonic()
        invoked_ms = round(time.time() * 1000)
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
            attributes = record.get("attributes", {})
            sent = attributes.get("SentTimestamp")
            queue_delay = invoked_ms - int(sent) if isinstance(sent, str) and sent.isdigit() else None
            LOGGER.info("Filing message processed", extra={"message_id": identifier, "work_id": result.work_id,
                "event_id": result.event_id, "outcome": result.outcome, "exhausted": result.exhausted,
                "invoked_at_epoch_ms": invoked_ms, "queue_to_invocation_ms": queue_delay,
                "handler_processing_ms": round((time.monotonic() - started) * 1000)})
            if not result.acknowledge:
                failures.append({"itemIdentifier": identifier})
        except Exception as exc:
            LOGGER.warning("Filing message deferred", extra={"message_id": identifier, "error_type": type(exc).__name__})
            failures.append({"itemIdentifier": identifier})
    return {"batchItemFailures": failures}
