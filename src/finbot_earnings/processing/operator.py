"""Focused fiscal-run commands. No .env loading, acquisition or fixture runtime."""
import argparse
from dataclasses import asdict
import json
import sys

from .contracts import json_value
from .errors import WorkConflict
from .fiscal_repository import STATUSES


def inspect_output(client, queue_url, *, limit=10):
    # A peek is observable delivery, not a permanent archive or deletion. Messages
    # can be received again immediately; capture SentTimestamp separately from view time.
    response = client.receive_message(QueueUrl=queue_url, MaxNumberOfMessages=limit,
        VisibilityTimeout=0, WaitTimeSeconds=0, MessageSystemAttributeNames=["SentTimestamp", "ApproximateReceiveCount"])
    return [dict(message_id=item["MessageId"], attributes=item.get("Attributes", {}), body=json_value(item["Body"]))
            for item in response.get("Messages", [])]


def parser():
    root = argparse.ArgumentParser(prog="earnings-ops", description=__doc__)
    root.add_argument("--sqlite", help="Offline v2 store; otherwise use EARNINGS_TABLE_NAME in AWS")
    sub = root.add_subparsers(dest="command", required=True)
    inspect = sub.add_parser("inspect", help="Full input/config/receipts/outcome/usage/timing; resolves processing refs")
    inspect.add_argument("work_id")
    event = sub.add_parser("event", help="Inspect immutable accepted event")
    event.add_argument("event_id")
    listing = sub.add_parser("list", help="Bounded, strongly consistent status page")
    listing.add_argument("status", choices=sorted(STATUSES))
    listing.add_argument("--limit", type=int, choices=range(1, 101), default=50, metavar="1..100")
    listing.add_argument("--cursor")
    retry = sub.add_parser("retry", help="Resume FAILED work; may incur inference charges or publish saved events")
    retry.add_argument("work_id")
    fresh = sub.add_parser("reprocess", help="Fresh extraction with new identity; incurs charges and can publish a new event")
    fresh.add_argument("work_id")
    fresh.add_argument("--run-id", required=True)
    output = sub.add_parser("output", help="Peek inspection SQS without deleting messages; increments receive count")
    output.add_argument("--queue-url", help="Defaults to EARNINGS_OUTPUT_QUEUE_URL")
    output.add_argument("--limit", type=int, choices=range(1, 11), default=10)
    return root


def execute(args, repository, *, consumer_factory=None, sqs=None):
    if args.command == "inspect":
        value = repository.get_job(args.work_id)
    elif args.command == "event":
        value = repository.event(args.event_id)
    elif args.command == "list":
        return repository.list_status(args.status, limit=args.limit, cursor=args.cursor)
    elif args.command in {"retry", "reprocess"}:
        job = repository.get_job(args.work_id)
        if job is None:
            raise KeyError(args.work_id)
        if args.command == "retry":
            if job["status"] != "processing_failed":
                raise WorkConflict("retry requires failed work; use a fresh run for completed outcomes")
            run_id = job["identity"]["run_id"]
        else:
            from .fiscal.config import digest, load_config
            from .fiscal_contract import FiscalIdentity
            config = load_config()
            identity = FiscalIdentity(job["input"]["filing_id"], job["input"]["snapshot_id"], config["version"], digest(config), args.run_id)
            if args.run_id == "initial" or args.run_id == job["identity"]["run_id"] or repository.get_job(identity.work_id) is not None:
                raise WorkConflict("fresh reprocessing requires an unused non-initial run ID")
            run_id = args.run_id
        if consumer_factory is None:
            from .fiscal_runtime import build_consumer
            consumer_factory = build_consumer
        consumer = consumer_factory(repository)
        if args.command == "retry" and consumer.config != job["extraction_config"]:
            raise WorkConflict("retry requires the saved configuration; use a fresh run")
        if args.command == "retry":
            repository.rearm(job["work_id"])
        return asdict(consumer.process(job["input"], run_id=run_id))
    else:
        import os
        if sqs is None:
            import boto3
            from botocore.config import Config
            sqs = boto3.Session().client("sqs", config=Config(connect_timeout=3, read_timeout=10, retries={"total_max_attempts": 2}))
        return inspect_output(sqs, args.queue_url or os.environ["EARNINGS_OUTPUT_QUEUE_URL"], limit=args.limit)
    if value is None:
        raise KeyError("record not found")
    return value


def main(argv=None):
    args = parser().parse_args(argv)
    repository = None
    try:
        if args.command != "output":
            if args.sqlite:
                from .fiscal_stores import SQLiteFiscalRepository
                repository = SQLiteFiscalRepository(args.sqlite)
            else:
                from .fiscal_runtime import make_repository
                repository = make_repository()
        value = execute(args, repository)
        # DynamoDB metadata is Decimal; application JSON payloads retain exact strings.
        from decimal import Decimal
        print(json.dumps(value, indent=2, ensure_ascii=False, default=lambda v: int(v) if isinstance(v, Decimal) and v == int(v) else str(v)))
        return 1 if isinstance(value, dict) and value.get("acknowledge") is False else 0
    except Exception as exc:
        # SDK/provider error strings may include sensitive data. Inspection bodies
        # are explicit output, errors expose only the type and a safe category.
        print(json.dumps(dict(error=type(exc).__name__, code="operator_command_failed")), file=sys.stderr)
        return 1
    finally:
        if repository is not None and hasattr(repository, "close"):
            repository.close()


if __name__ == "__main__":
    sys.exit(main())
