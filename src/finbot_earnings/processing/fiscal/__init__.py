"""Isolated fiscal EPS port. The legacy FilingPipeline does not call this API."""

from .adapter import OpenAIFiscalExtractor, make_client
from .config import load_config

__all__ = ["OpenAIFiscalExtractor", "make_client", "load_config"]
