
"""Identify symptom concepts and their supporting evidence clauses."""

import re

from src.services.symptom_vocabulary import SYMPTOM_VOCABULARY
from src.services.text_segmentation_service import split_sentences


CLAUSE_BOUNDARY_PATTERN = re.compile(
    r"\s*,\s*(?:but|however|whereas)\s+"
    r"|\s+(?:but|however|whereas)\s+",
    re.IGNORECASE,
)


class SymptomEvidenceService:
    """Associate symptom concepts with their supporting clauses."""

    def __init__(self):
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

    def extract_evidence(self, text: str) -> list[dict]:
        """Return symptom concepts with their supporting clauses."""

        evidence_records = []

        for sentence in split_sentences(text):
            for clause in self._split_clauses(sentence):
                matches = []

                for symptom, patterns in self.alias_patterns.items():
                    positions = [
                        match.start()
                        for pattern in patterns
                        for match in pattern.finditer(clause)
                    ]

                    if positions:
                        matches.append((min(positions), symptom))

                # Preserve the order in which symptoms appear in the text.
                matches.sort(key=lambda item: item[0])

                for _, symptom in matches:
                    evidence_records.append(
                        {
                            "symptom": symptom,
                            "evidence": clause,
                        }
                    )

        return evidence_records
