
"""Identify symptom concepts and their supporting evidence clauses."""

import re
from collections.abc import Callable

from src.services.symptom_vocabulary import SYMPTOM_VOCABULARY
from src.services.text_segmentation_service import split_sentences


CLAUSE_BOUNDARY_PATTERN = re.compile(
    r"\s*,\s*(?:but|however|whereas)\s+"
    r"|\s+(?:but|however|whereas)\s+",
    re.IGNORECASE,
)


class SymptomEvidenceService:
    """Associate recognized symptom concepts with evidence clauses."""

    def __init__(
        self,
        concept_extractor: Callable[[str], list[str]] | None = None,
    ):
        self.concept_extractor = concept_extractor
        self.alias_patterns = {}

        for symptom, definition in SYMPTOM_VOCABULARY.items():
            patterns = []

            for alias in definition["aliases"]:
                pattern = re.compile(
                    rf"(?<!\w){re.escape(alias)}(?!\w)",
                    re.IGNORECASE,
                )
                patterns.append(pattern)

            self.alias_patterns[symptom] = patterns

    def _split_clauses(self, sentence: str) -> list[str]:
        """Separate contrastive clauses while preserving their text."""

        return [
            clause.strip()
            for clause in CLAUSE_BOUNDARY_PATTERN.split(sentence)
            if clause.strip()
        ]

    def _find_symptoms(self, clause: str) -> list[str]:
        """Combine exact vocabulary matching with semantic extraction."""

        lexical_matches = []

        for symptom, patterns in self.alias_patterns.items():
            positions = [
                match.start()
                for pattern in patterns
                for match in pattern.finditer(clause)
            ]

            if positions:
                lexical_matches.append((min(positions), symptom))

        lexical_matches.sort(key=lambda item: item[0])

        matched_symptoms = {
            symptom for _, symptom in lexical_matches
        }

        semantic_matches = set()

        if self.concept_extractor is not None:
            semantic_matches = set(
                self.concept_extractor(clause)
            )

        # Ignore concepts outside our controlled vocabulary.
        semantic_matches.intersection_update(self.alias_patterns)

        # Preserve lexical order. Semantic-only matches are appended
        # in deterministic alphabetical order because their exact
        # mention positions are not available.
        return [
            symptom for _, symptom in lexical_matches
        ] + sorted(semantic_matches - matched_symptoms)

    def extract_evidence(self, text: str) -> list[dict]:
        """Return symptom concepts with their supporting clauses."""

        evidence_records = []

        for sentence in split_sentences(text):
            for clause in self._split_clauses(sentence):
                symptoms = self._find_symptoms(clause)

                for symptom in symptoms:
                    evidence_records.append(
                        {
                            "symptom": symptom,
                            "evidence": clause,
                        }
                    )

        return evidence_records
