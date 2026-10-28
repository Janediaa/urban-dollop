
import numpy as np
import pytest

from src.services.vector_store import MedicalVectorStore


def sample_chunks():
    return [
        {"filename": "heart.html", "text": "Heart health", "chunk_index": 0},
        {"filename": "blood.html", "text": "Blood pressure", "chunk_index": 0},
        {"filename": "brain.html", "text": "Brain health", "chunk_index": 0},
    ]


def sample_embeddings():
    return np.array(
        [
            [0.8, 0.6],
            [1.0, 0.0],
            [0.0, 1.0],
        ],
        dtype=np.float32,
    )


def test_vector_store_builds_and_searches(tmp_path):
    store = MedicalVectorStore(tmp_path)
    store.build(sample_chunks(), sample_embeddings())

    results = store.search([1.0, 0.0], top_k=2)

    assert len(results) == 2
    assert results[0]["filename"] == "blood.html"
    assert results[0]["similarity_score"] == pytest.approx(1.0)


def test_vector_store_persists_across_instances(tmp_path):
    first_store = MedicalVectorStore(tmp_path)
    first_store.build(sample_chunks(), sample_embeddings())

    second_store = MedicalVectorStore(tmp_path)
    second_store.load()

    results = second_store.search([1.0, 0.0], top_k=1)

    assert results[0]["filename"] == "blood.html"


def test_vector_store_rejects_mismatched_counts(tmp_path):
    store = MedicalVectorStore(tmp_path)

    with pytest.raises(ValueError, match="counts must match"):
        store.build(sample_chunks(), sample_embeddings()[:2])


def test_vector_store_rejects_non_finite_embeddings(tmp_path):
    store = MedicalVectorStore(tmp_path)
    embeddings = sample_embeddings()
    embeddings[0, 0] = np.nan

    with pytest.raises(ValueError, match="finite values"):
        store.build(sample_chunks(), embeddings)


def test_vector_store_requires_load_before_search(tmp_path):
    store = MedicalVectorStore(tmp_path)

    with pytest.raises(RuntimeError, match="before searching"):
        store.search([1.0, 0.0])


def test_vector_store_rejects_wrong_query_dimension(tmp_path):
    store = MedicalVectorStore(tmp_path)
    store.build(sample_chunks(), sample_embeddings())

    with pytest.raises(ValueError, match="dimensions must match"):
        store.search([1.0, 0.0, 0.0])
