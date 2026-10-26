"""Strict fiscal release configuration; no credential values or provider overrides."""
from dataclasses import dataclass
from pathlib import Path
import re

from finbot_earnings.processing.contracts import fields, json_value
from finbot_earnings.processing.fiscal.config import digest, load_config


@dataclass(frozen=True)
class Settings:
    account: str
    region: str
    stack_name: str
    filing_topic_arn: str
    source_bucket: str
    consumption_enabled: bool
    fiscal_config_sha256: str
    openai_secret_name: str
    alarm_email: str
    source_kms_key_arn: str | None = None

    @classmethod
    def load(cls, path):
        value = json_value(Path(path).read_text())
        fields(value, ("account", "region", "stack_name", "filing_topic_arn", "source_bucket",
                       "consumption_enabled", "fiscal_config_sha256", "openai_secret_name", "alarm_email"),
               ("source_kms_key_arn",))
        if not re.fullmatch(r"\d{12}", value["account"]) or not re.fullmatch(r"[a-z]{2}-[a-z]+-\d", value["region"]):
            raise ValueError("Expected explicit account and region")
        if not re.fullmatch(r"[a-z][a-z0-9-]{1,40}", value["stack_name"]):
            raise ValueError("Invalid stack name")
        if not re.fullmatch(rf'arn:aws:sns:{value["region"]}:{value["account"]}:[A-Za-z0-9_-]+', value["filing_topic_arn"]):
            raise ValueError("Filing topic must be in the configured account and region")
        if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", value["source_bucket"]):
            raise ValueError("Invalid source bucket")
        if type(value["consumption_enabled"]) is not bool:
            raise ValueError("consumption_enabled must be boolean")
        if value["fiscal_config_sha256"] != digest(load_config()):
            raise ValueError("Release must use the frozen fiscal configuration")
        if value["openai_secret_name"] != value["stack_name"] + "/openai-project-key":
            raise ValueError("Use the dedicated earnings secret name")
        if value["alarm_email"] != "ilancooke@gmail.com":
            raise ValueError("Use the approved alarm recipient")
        kms = value.get("source_kms_key_arn")
        if kms is not None and not re.fullmatch(r"arn:aws:kms:[a-z0-9-]+:\d{12}:key/[a-f0-9-]+", kms):
            raise ValueError("Invalid source KMS key ARN")
        return cls(**value)
