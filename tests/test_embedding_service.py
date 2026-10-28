
"""Tests for the embedding service."""

import numpy as np
import pytest

from src.services.embedding_service import (
    generate_embeddings,
    load_embedding_model,
)


@pytest.fixture(scope="module")
def embedding_model():
    """Load the real embedding model once for this test module."""
    return load_embedding_model()


def test_load_embedding_model_returns_usable_model(embedding_model):
    assert embedding_model is not None
    assert embedding_model.max_seq_length == 256


def test_generate_embeddings_returns_expected_shape(embedding_model):
    texts = [
        "Regular exercise supports heart health.",
        "Sleep helps the brain process information.",
    ]

    embeddings = generate_embeddings(texts, embedding_model)

    assert embeddings.shape == (2, 384)


def test_generate_embeddings_contains_finite_values(embedding_model):
    texts = [
        "Regular exercise supports heart health.",
        "Sleep helps the brain process information.",
    ]

    embeddings = generate_embeddings(texts, embedding_model)

    assert np.isfinite(embeddings).all()
