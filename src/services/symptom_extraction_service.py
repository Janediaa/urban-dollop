
"""Semantic and fuzzy matching for symptom concept extraction."""

from rapidfuzz import fuzz, process

from src.services.embedding_service import generate_embeddings
from src.services.symptom_vocabulary import SYMPTOM_VOCABULARY


class SymptomExtractionService:
    """Match natural-language text to canonical symptom concepts."""

    def __init__(
        self,
        model,
        semantic_threshold: float = 0.55,
        fuzzy_threshold: float = 85.0,
    ):
        self.model = model
        self.semantic_threshold = semantic_threshold
        self.fuzzy_threshold = fuzzy_threshold

        self.alias_to_symptom = {
            alias.lower(): symptom
            for symptom, definition in SYMPTOM_VOCABULARY.items()
            for alias in definition["aliases"]
        }

        self.semantic_examples = {
            symptom: definition["semantic_examples"]
            for symptom, definition in SYMPTOM_VOCABULARY.items()
        }

        self.example_texts = [
            example
            for examples in self.semantic_examples.values()
            for example in examples
        ]

        self.example_embeddings = generate_embeddings(
            self.example_texts,
            self.model,
        )

        self.example_owners = [
            symptom
            for symptom, examples in self.semantic_examples.items()
            for _ in examples
        ]

    def _fuzzy_match(self, text: str) -> set[str]:
        """Find symptom concepts using approximate alias matching."""

        matches = process.extract(
            text.lower(),
            self.alias_to_symptom.keys(),
            scorer=fuzz.partial_ratio,
            score_cutoff=self.fuzzy_threshold,
            limit=None,
        )

        return {
            self.alias_to_symptom[alias]
            for alias, _, _ in matches
        }

    
    def _semantic_scores(self, text: str) -> dict[str, float]:
        """Calculate the highest semantic similarity per symptom concept."""

        query_embedding = generate_embeddings(
            [text],
            self.model,
        )[0]

        similarities = self.model.similarity(
            query_embedding,
            self.example_embeddings,
        )[0]

        concept_scores = {}

        for index, similarity in enumerate(similarities):
            symptom = self.example_owners[index]
            score = float(similarity)

            concept_scores[symptom] = max(
                concept_scores.get(symptom, -1.0),
                score,
            )

        return concept_scores

    def extract_concepts(self, text: str) -> list[str]:
        """Return symptom concepts supported by lexical or semantic evidence."""

        if not text or not text.strip():
            return []

        fuzzy_matches = self._fuzzy_match(text)
        semantic_scores = self._semantic_scores(text)

        matched = set(fuzzy_matches)

        for symptom, score in semantic_scores.items():
            if score < self.semantic_threshold:
                continue

            matched.add(symptom)

        # Keep strong direct lexical matches even when semantic
        # similarity is relatively low.
        if fuzzy_matches:
            return sorted(fuzzy_matches | {
                symptom
                for symptom in matched - fuzzy_matches
                if semantic_scores.get(symptom, 0.0) >= 0.75
            })

        if not semantic_scores:
            return []

        best_score = max(semantic_scores.values())

        return sorted(
            symptom
            for symptom, score in semantic_scores.items()
            if score >= max(self.semantic_threshold, best_score - 0.20)
        )
