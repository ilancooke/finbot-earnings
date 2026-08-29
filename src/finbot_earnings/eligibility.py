from __future__ import annotations

from dataclasses import dataclass

from .models import ArtifactRecord, ArtifactType


@dataclass(frozen=True)
class EligibilityDecision:
    analyze: bool
    reason: str


class ArtifactEligibilityPolicy:
    def decide(self, artifact: ArtifactRecord) -> EligibilityDecision:
        kind = artifact.artifact_type
        if kind in {
            ArtifactType.IR_EARNINGS_RELEASE, ArtifactType.EXHIBIT_99_1,
            ArtifactType.CFO_COMMENTARY, ArtifactType.SEC_10Q, ArtifactType.SEC_10K,
        }:
            return EligibilityDecision(True, f"eligible artifact type: {kind.value}")
        if kind == ArtifactType.SEC_8K:
            items = str(artifact.metadata.get("items", ""))
            return EligibilityDecision("2.02" in items, "8-K Item 2.02" if "2.02" in items else "unrelated 8-K")
        if kind == ArtifactType.COMPANY_FACTS:
            return EligibilityDecision(False, "deterministic enrichment source")
        return EligibilityDecision(False, "unsupported artifact type")

