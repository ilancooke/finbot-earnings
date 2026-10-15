"""Independent consumer implementation of FilingReady 1.0; no producer imports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from urllib.parse import urlsplit, unquote

from .errors import ContractError


def json_text(value) -> str:
    return json.dumps(value, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))


def utc_text(value: datetime) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("aware timestamp required")
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ContractError("duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(_):
    raise ContractError("nonfinite JSON value")


def json_value(text: str | bytes):
    return json.loads(text, object_pairs_hook=_pairs, parse_constant=_nonfinite)


def fields(value, required, optional=()):
    if not isinstance(value, dict) or not set(required) <= value.keys() or value.keys() - set(required) - set(optional):
        raise ContractError("unexpected or missing fields")


def nonempty(value, name):
    if not isinstance(value, str) or not value.strip() or any(ord(char) < 32 for char in value):
        raise ContractError(f"invalid {name}")
    return value


def timestamp(value):
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z", value):
        raise ContractError("timestamp must use fixed-width UTC")
    try:
        parsed = datetime.fromisoformat(value)
        if utc_text(parsed) != value:
            raise ValueError("noncanonical timestamp")
        return parsed
    except ValueError as exc:
        raise ContractError("invalid timestamp") from exc


@dataclass(frozen=True)
class ArtifactReference:
    artifact_id: str
    filename: str
    s3_uri: str
    size_bytes: int
    document_type: str | None = None
    content_type: str | None = None

    @classmethod
    def parse(cls, value, filing_id):
        fields(value, ("artifact_id", "filename", "s3_uri", "size_bytes"), ("document_type", "content_type"))
        filename = nonempty(value["filename"], "filename")
        if filename in {".", ".."} or "/" in filename or "\\" in filename or any(ord(char) == 127 for char in filename):
            raise ContractError("unsafe filename")
        if value["artifact_id"] != filing_id + "/" + filename:
            raise ContractError("artifact identity disagrees with filing/filename")
        uri = nonempty(value["s3_uri"], "s3_uri")
        try:
            parts = urlsplit(uri)
            if (parts.scheme != "s3" or not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", parts.netloc)
                    or not parts.path.startswith("/") or not parts.path[1:] or parts.query or parts.fragment
                    or re.search(r"%(?![0-9a-fA-F]{2})", parts.path)):
                raise ValueError("invalid S3 reference")
            unquote(parts.path, errors="strict")
        except (ValueError, UnicodeError) as exc:
            raise ContractError("invalid S3 reference") from exc
        if type(value["size_bytes"]) is not int or value["size_bytes"] < 0:
            raise ContractError("size_bytes must be a nonnegative integer")
        for name in ("content_type", "document_type"):
            if name in value:
                nonempty(value[name], name)
        return cls(**value)

    def to_dict(self):
        return {name: value for name, value in vars(self).items() if value is not None}


@dataclass(frozen=True)
class FilingReady:
    filing_id: str
    snapshot_id: str
    cik: str
    ticker: str
    company_name: str
    form_type: str
    filed_at: str
    ready_at: str
    primary_artifact_id: str
    artifacts: tuple[ArtifactReference, ...]

    @classmethod
    def parse(cls, message: str | bytes | dict, *, expected_topic_arn: str | None = None):
        try:
            if isinstance(message, (str, bytes)):
                size = len(message.encode("utf-8")) if isinstance(message, str) else len(message)
                # SNS wrapping adds metadata around the bounded producer payload.
                if size > 512 * 1024:
                    raise ContractError("notification exceeds envelope limit")
                value = json_value(message)
            else:
                value = json_value(json_text(message))
            if isinstance(value, dict) and value.get("Type") == "Notification":
                if expected_topic_arn is not None and value.get("TopicArn") != expected_topic_arn:
                    raise ContractError("unexpected SNS topic")
                if not isinstance(value.get("Message"), str):
                    raise ContractError("SNS Message must be a JSON string")
                value = json_value(value["Message"])
            required = ("event_type", "schema_version", "filing_id", "snapshot_id", "cik", "ticker",
                        "company_name", "form_type", "filed_at", "ready_at", "primary_artifact_id", "artifacts")
            fields(value, required)
            if len(json_text(value).encode("utf-8")) > 256 * 1024:
                raise ContractError("filing notification exceeds 256 KiB")
            if value["event_type"] != "filing.ready" or value["schema_version"] != "1.0":
                raise ContractError("unsupported event type or version")
            for name, pattern in (("filing_id", r"\d{10}-\d{2}-\d{6}"), ("snapshot_id", r"[0-9a-f]{64}"),
                                  ("cik", r"\d{10}"), ("ticker", r"[A-Za-z0-9][A-Za-z0-9.-]*")):
                if not isinstance(value[name], str) or not re.fullmatch(pattern, value[name]):
                    raise ContractError(f"invalid {name}")
            nonempty(value["company_name"], "company_name")
            if value["form_type"] not in {"8-K", "8-K/A", "10-Q", "10-Q/A", "10-K", "10-K/A", "6-K", "6-K/A"}:
                raise ContractError("unsupported form")
            timestamp(value["filed_at"])
            timestamp(value["ready_at"])
            if not isinstance(value["artifacts"], list) or not value["artifacts"]:
                raise ContractError("nonempty artifact manifest required")
            artifacts = tuple(sorted((ArtifactReference.parse(item, value["filing_id"]) for item in value["artifacts"]),
                                     key=lambda item: item.artifact_id))
            ids = [item.artifact_id for item in artifacts]
            if len(set(ids)) != len(ids) or ids.count(value["primary_artifact_id"]) != 1:
                raise ContractError("manifest requires unique identities and exactly one primary")
            canonical = {name: value[name] for name in ("filing_id", "cik", "ticker", "company_name", "form_type", "filed_at", "primary_artifact_id")}
            canonical["artifacts"] = [item.to_dict() for item in artifacts]
            digest = hashlib.sha256(json_text(canonical).encode("utf-8")).hexdigest()
            if digest != value["snapshot_id"]:
                raise ContractError("snapshot hash mismatch")
            return cls(**{name: value[name] for name in cls.__dataclass_fields__ if name != "artifacts"}, artifacts=artifacts)
        except ContractError:
            raise
        except (ValueError, TypeError, KeyError, UnicodeError, OverflowError) as exc:
            raise ContractError("invalid filing notification") from exc

    def to_dict(self):
        return {**{name: value for name, value in vars(self).items() if name != "artifacts"},
                "event_type": "filing.ready", "schema_version": "1.0",
                "artifacts": [item.to_dict() for item in self.artifacts]}
