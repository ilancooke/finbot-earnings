from __future__ import annotations

from abc import ABC, abstractmethod

from ..models import EarningsExtraction, ParsedArtifact


class ExtractionError(RuntimeError):
    pass


class TransientExtractionError(ExtractionError):
    pass


class PermanentExtractionError(ExtractionError):
    pass


class EarningsExtractor(ABC):
    provider = "unknown"
    display_name = "extractor"

    @abstractmethod
    def extract(self, artifact: ParsedArtifact) -> EarningsExtraction:
        raise NotImplementedError
