from dataclasses import asdict, dataclass
from pathlib import Path
import re

from finbot_earnings.processing.contracts import fields, json_value


@dataclass(frozen=True)
class LegacyExtractionSettings:
    """CDK-only compatibility shape; replace with fiscal settings in Milestone 6."""
    version: str
    model_id: str = "fixture"
    prompt_version: str = "eps-v0"
    schema_version: str = "eps-v0"
    validation_policy: str = "explicit-prose-v1"
    max_documents: int = 16
    max_input_bytes: int = 4 * 1024 * 1024
    max_response_bytes: int = 64 * 1024
    max_facts: int = 32
    max_stage_failures: int = 3
    lease_seconds: int = 300
    max_output_tokens: int = 4096

    def __post_init__(self):
        for name in ("version", "model_id", "prompt_version", "schema_version"):
            value = getattr(self, name)
            if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9._:/-]{1,200}", value):
                raise ValueError(f"invalid {name}")
        if self.validation_policy != "explicit-prose-v1" or self.schema_version != "eps-v0":
            raise ValueError("unsupported validation policy or schema")
        bounds = {"max_documents": 100, "max_input_bytes": 64 * 1024 * 1024,
                  "max_response_bytes": 256 * 1024, "max_facts": 100,
                  "max_stage_failures": 10, "lease_seconds": 3600, "max_output_tokens": 16384}
        for name, maximum in bounds.items():
            if type(getattr(self, name)) is not int or not 1 <= getattr(self, name) <= maximum:
                raise ValueError(f"invalid {name}")

    def to_dict(self):
        return asdict(self)


@dataclass(frozen=True)
class Settings:
    account: str
    region: str
    stack_name: str
    filing_topic_arn: str
    source_bucket: str
    consumption_enabled: bool
    bedrock_resource_arns: tuple[str, ...]
    extraction: LegacyExtractionSettings
    source_kms_key_arn: str | None = None

    @classmethod
    def load(cls, path):
        value = json_value(Path(path).read_text())
        fields(value, ("account", "region", "stack_name", "filing_topic_arn", "source_bucket",
                       "consumption_enabled", "bedrock_resource_arns", "extraction"), ("source_kms_key_arn",))
        if not re.fullmatch(r"\d{12}", value["account"]) or not re.fullmatch(r"[a-z]{2}-[a-z]+-\d", value["region"]):
            raise ValueError("Expected explicit account and region")
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,40}", value["stack_name"]):
            raise ValueError("Invalid stack name")
        arn_prefix = f'arn:aws:sns:{value["region"]}:{value["account"]}:'
        if not value["filing_topic_arn"].startswith(arn_prefix) or value["filing_topic_arn"].count(":") != 5:
            raise ValueError("Filing topic must be in the configured account and region")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", value["source_bucket"]):
            raise ValueError("Invalid source bucket")
        if type(value["consumption_enabled"]) is not bool:
            raise ValueError("consumption_enabled must be boolean")
        extraction = LegacyExtractionSettings(**value["extraction"])
        if extraction.lease_seconds <= 300:
            raise ValueError("Lease must outlive the 300-second Lambda timeout")
        if not isinstance(value["bedrock_resource_arns"], list) or any(not isinstance(arn, str) or not re.fullmatch(
                r"arn:aws:bedrock:[a-z0-9-]+:(?:\d{12})?:(?:foundation-model|inference-profile|application-inference-profile)/[A-Za-z0-9.:/-]+", arn)
                for arn in value["bedrock_resource_arns"]):
            raise ValueError("Use explicit Bedrock resource ARNs without wildcards")
        if extraction.model_id == "unselected":
            if value["consumption_enabled"] or value["bedrock_resource_arns"]:
                raise ValueError("Select a model before enabling consumption or granting invocation")
        elif not value["bedrock_resource_arns"]:
            raise ValueError("Selected model requires explicit invocation resource ARNs")
        kms = value.get("source_kms_key_arn")
        if kms is not None and not re.fullmatch(r"arn:aws:kms:[a-z0-9-]+:\d{12}:key/[a-f0-9-]+", kms):
            raise ValueError("Invalid source KMS key ARN")
        return cls(**{key: item for key, item in value.items() if key not in {"extraction", "bedrock_resource_arns"}},
                   extraction=extraction, bedrock_resource_arns=tuple(value["bedrock_resource_arns"]))
