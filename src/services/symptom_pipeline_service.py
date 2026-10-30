
"""Orchestrate symptom evidence extraction and context analysis."""

from collections.abc import Callable

from src.services.symptom_context_service import analyze_symptom_contexts
from src.services.symptom_evidence_service import SymptomEvidenceService


class SymptomPipelineService:
    """Extract symptoms and associate each with its individual context."""

    def __init__(
        self,
        concept_extractor: Callable[[str], list[str]] | None = None,
    ):
        self.evidence_service = SymptomEvidenceService(
            concept_extractor=concept_extractor
        )

    def extract_symptoms(self, text: str) -> list[dict]:
        """Return symptom evidence enriched with contextual information."""

        evidence_records = self.evidence_service.extract_evidence(text)

        return analyze_symptom_contexts(evidence_records)
