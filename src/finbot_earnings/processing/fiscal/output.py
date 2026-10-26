"""Strict provider envelope and fiscal schema handling; business acceptance is M3."""

from jsonschema import Draft202012Validator

from ..contracts import json_text, json_value
from .config import local_schema
from .errors import problem


def strict_json(text):
    value = json_value(text)
    # Reject overflowed JSON numbers and unpaired Unicode surrogates too.
    json_text(value).encode("utf-8")
    return value


def extraction_text(native):
    if native.get("status") != "completed" or native.get("error") or native.get("incomplete_details"):
        raise problem("incomplete_model_output", "extraction", outcome="review_required")
    output = native.get("output")
    if not isinstance(output, list) or any(not isinstance(i, dict) for i in output):
        raise problem("invalid_model_response", "response")
    messages = [i for i in output if i.get("type") == "message"]
    if (len(messages) != 1 or messages[0].get("status") != "completed" or messages[0].get("role") != "assistant"
            or any(i.get("type") not in {"message", "reasoning"} for i in output)):
        raise problem("invalid_model_response", "response")
    blocks = messages[0].get("content")
    if not isinstance(blocks, list) or any(not isinstance(b, dict) for b in blocks):
        raise problem("invalid_model_response", "response")
    if any(b.get("type") == "refusal" for b in blocks):
        raise problem("provider_refusal", "extraction", outcome="review_required")
    if len(blocks) != 1 or blocks[0].get("type") != "output_text" or not isinstance(blocks[0].get("text"), str):
        raise problem("invalid_model_response", "response")
    return blocks[0]["text"]


def parse_output(native, config):
    text = extraction_text(native)
    if len(text.encode("utf-8")) > config["persistence_limits"]["max_extraction_bytes"]:
        raise problem("invalid_model_response", "response", bound="max_extraction_bytes",
                      actual=len(text.encode("utf-8")), limit=config["persistence_limits"]["max_extraction_bytes"])
    try:
        labels = strict_json(text)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise problem("invalid_model_response", "response") from None
    validator = Draft202012Validator(local_schema())
    error = next(validator.iter_errors(labels), None)
    if error:
        raise problem("invalid_model_response", "response", path=list(error.absolute_path))
    for metric, rows in labels.items():
        for index, row in enumerate(rows):
            if type(row["fiscal_year"]) is not int or (row["fiscal_quarter"] is not None and type(row["fiscal_quarter"]) is not int):
                raise problem("invalid_model_response", "response", path=[metric, index])
    return labels


def normalized_usage(native):
    """Port of evals direct.normalized_usage; preserve unknown usage as unknown."""
    usage = native.get("usage")
    if not isinstance(usage, dict):
        return {}
    if any(type(usage.get(k)) is not int or usage[k] < 0 for k in ("input_tokens", "output_tokens")):
        return {"providerUsage": usage}
    details = usage.get("input_tokens_details") or {}
    if not isinstance(details, dict):
        return {"providerUsage": usage}
    read, write = details.get("cached_tokens", 0), details.get("cache_write_tokens", 0)
    if any(type(n) is not int or n < 0 for n in (read, write)):
        return {"providerUsage": usage}
    ordinary = usage["input_tokens"] - read - write
    if ordinary < 0:
        return {"providerUsage": usage}
    return dict(inputTokens=ordinary, outputTokens=usage["output_tokens"],
                cacheReadInputTokens=read, cacheWriteInputTokens=write,
                totalTokens=ordinary + read + write + usage["output_tokens"], providerUsage=usage)
