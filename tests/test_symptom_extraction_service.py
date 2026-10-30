from unittest.mock import MagicMock

import numpy as np

from src.services.symptom_extraction_service import (
    SymptomExtractionService,
)


class FakeEmbeddingModel:
    def encode(self, texts):
        return np.ones((len(texts), 384), dtype=np.float32)

    def similarity(self, query, corpus):
        return np.zeros((1, len(corpus)), dtype=np.float32)


def test_empty_text_returns_no_symptoms():
    service = SymptomExtractionService(FakeEmbeddingModel())

    assert service.extract_concepts("") == []
    assert service.extract_concepts("   ") == []


def test_fuzzy_matching_detects_known_alias():
    service = SymptomExtractionService(FakeEmbeddingModel())

    assert "headache" in service.extract_concepts(
        "I have a head ache"
    )


def test_fuzzy_matching_handles_spelling_errors():
    service = SymptomExtractionService(
        FakeEmbeddingModel(),
        fuzzy_threshold=70,
    )

    assert "nausea" in service.extract_concepts(
        "I have nausia"
    )


def test_strong_semantic_matches_are_combined_with_fuzzy_matches():
    service = SymptomExtractionService(FakeEmbeddingModel())

    service._semantic_scores = lambda text: {
        "headache": 0.90,
        "dizziness": 0.82,
        "fever": 0.40,
    }

    assert service.extract_concepts("I have a headache") == [
        "dizziness",
        "headache",
    ]

def test_semantic_match_does_not_return_weakly_related_symptoms():
    service = SymptomExtractionService(FakeEmbeddingModel())

    service._semantic_scores = lambda text: {
        "headache": 0.90,
        "palpitations": 0.59,
        "dizziness": 0.51,
    }

    assert service.extract_concepts(
        "My head has been pounding."
    ) == ["headache"]


def test_multiple_strong_symptoms_are_preserved():
    service = SymptomExtractionService(FakeEmbeddingModel())

    service._semantic_scores = lambda text: {
        "fever": 0.91,
        "cough": 0.88,
        "headache": 0.42,
    }

    assert service.extract_concepts(
        "I have fever and cough."
    ) == ["cough", "fever"]


def test_fuzzy_match_is_preserved():
    service = SymptomExtractionService(FakeEmbeddingModel())

    service._semantic_scores = lambda text: {
        "headache": 0.40,
        "fever": 0.35,
    }

    assert "headache" in service.extract_concepts(
        "I have a head ache."
    )

