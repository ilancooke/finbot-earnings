from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_DATA_DIR = Path("/Users/ilan/workspace/finbot/data/earnings")


@dataclass(frozen=True)
class CompanyConfig:
    ticker: str
    cik: str
    ir_adapter: str | None = None


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    sec_user_agent: str
    openai_model: str
    poll_interval_seconds: float
    companies: dict[str, CompanyConfig]

    def company(self, ticker: str) -> CompanyConfig:
        try:
            return self.companies[ticker.upper()]
        except KeyError as exc:
            raise KeyError(f"unknown company {ticker!r}; configure it in companies.toml") from exc


def load_settings(config_path: Path | None = None) -> Settings:
    config_path = config_path or Path(__file__).with_name("companies.toml")
    raw = tomllib.loads(config_path.read_text(encoding="utf-8"))
    companies = {
        ticker.upper(): CompanyConfig(
            ticker=ticker.upper(), cik=str(values["cik"]).zfill(10),
            ir_adapter=values.get("ir", {}).get("adapter"),
        )
        for ticker, values in raw.get("companies", {}).items()
    }
    return Settings(
        data_dir=Path(os.environ.get("EARNINGS_DATA_DIR", DEFAULT_DATA_DIR)).expanduser(),
        sec_user_agent=os.environ.get("SEC_USER_AGENT", ""),
        openai_model=os.environ.get("OPENAI_MODEL", "gpt-5.4-mini"),
        poll_interval_seconds=float(os.environ.get("EARNINGS_POLL_INTERVAL", "5")),
        companies=companies,
    )

