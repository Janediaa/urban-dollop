import numpy as np
from unittest.mock import Mock
import pytest

from src.services.retrieval_service import retrieve_relevant_chunks


def test_retrieve_relevant_chunks_ranks_results_and_preserves_metadata():
    chunks = [
        {
            "filename": "heart.html",
            "title": "Heart Health",
            "text": "Information about heart health.",
            "chunk_index": 0,
        },
        {
            "filename": "blood_pressure.html",
            "title": "Blood Pressure",
            "text": "Information about blood pressure.",
            "chunk_index": 0,
        },
        {
            "filename": "brain.html",
            "title": "Brain Health",
            "text": "Information about the brain.",
            "chunk_index": 0,
        },
    ]

    # The query vector will be [1, 0].
    # Chunk 2 is most similar, then chunk 1, then chunk 3.
    chunk_embeddings = np.array([
        [0.8, 0.6],
        [1.0, 0.0],
        [0.0, 1.0],
    ])

    model = Mock()
    model.encode.return_value = np.array([[1.0, 0.0]])

    results = retrieve_relevant_chunks(
        query="Tell me about blood pressure",
        chunks=chunks,
        chunk_embeddings=chunk_embeddings,
        model=model,
        top_k=2,
    )

    assert len(results) == 2
    assert results[0]["filename"] == "blood_pressure.html"
    assert results[0]["title"] == "Blood Pressure"
    assert results[0]["text"] == "Information about blood pressure."

    # The original chunk records must remain unchanged.
    assert "similarity_score" not in chunks[0]
    assert "similarity_score" not in chunks[1]
    assert "similarity_score" not in chunks[2]

    # Scores should be descending.
    scores = [result["similarity_score"] for result in results]
    assert scores == sorted(scores, reverse=True)

    # Returned records preserve their metadata and gain a score.
    assert results[0]["chunk_index"] == 0
    assert results[1]["filename"] == "heart.html"
    assert results[1]["title"] == "Heart Health"
    assert all("similarity_score" in result for result in results)

    # The query is encoded once; stored chunk embeddings are reused.
    model.encode.assert_called_once_with(["Tell me about blood pressure"])

def make_test_data():
    """Return deterministic chunks, vectors, and a mocked model."""
    chunks = [
        {
            "filename": "heart.html",
            "title": "Heart Health",
            "text": "Information about heart health.",
            "chunk_index": 0,
        },
        {
            "filename": "blood_pressure.html",
            "title": "Blood Pressure",
            "text": "Information about blood pressure.",
            "chunk_index": 0,
        },
        {
            "filename": "brain.html",
            "title": "Brain Health",
            "text": "Information about the brain.",
            "chunk_index": 0,
        },
    ]

    chunk_embeddings = np.array([
        [0.8, 0.6],
        [1.0, 0.0],
        [0.0, 1.0],
    ])

    model = Mock()
    model.encode.return_value = np.array([[1.0, 0.0]])

    return chunks, chunk_embeddings, model


@pytest.mark.parametrize("query", ["", "   ", "\t\n"])
def test_retrieve_relevant_chunks_rejects_empty_query(query):
    chunks, embeddings, model = make_test_data()

    with pytest.raises(ValueError, match="query must not be empty"):
        retrieve_relevant_chunks(query, chunks, embeddings, model)

    model.encode.assert_not_called()


def test_retrieve_relevant_chunks_returns_empty_for_no_chunks():
    _, embeddings, model = make_test_data()

    result = retrieve_relevant_chunks(
        query="heart health",
        chunks=[],
        chunk_embeddings=embeddings,
        model=model,
    )

    assert result == []
    model.encode.assert_not_called()


@pytest.mark.parametrize("top_k", [0, -1, -5])
def test_retrieve_relevant_chunks_rejects_non_positive_top_k(top_k):
    chunks, embeddings, model = make_test_data()

    with pytest.raises(ValueError, match="top_k must be positive"):
        retrieve_relevant_chunks(
            "heart health", chunks, embeddings, model, top_k=top_k
        )


@pytest.mark.parametrize("top_k", [1.5, "2", True, False])
def test_retrieve_relevant_chunks_rejects_invalid_top_k_type(top_k):
    chunks, embeddings, model = make_test_data()

    with pytest.raises(TypeError, match="top_k must be an integer"):
        retrieve_relevant_chunks(
            "heart health", chunks, embeddings, model, top_k=top_k
        )


def test_retrieve_relevant_chunks_returns_all_when_top_k_is_too_large():
    chunks, embeddings, model = make_test_data()

    results = retrieve_relevant_chunks(
        "heart health",
        chunks,
        embeddings,
        model,
        top_k=10,
    )

    assert len(results) == len(chunks)


def test_retrieve_relevant_chunks_rejects_chunk_embedding_count_mismatch():
    chunks, embeddings, model = make_test_data()

    # Three chunks but only two embedding vectors.
    mismatched_embeddings = embeddings[:2]

    with pytest.raises(
        ValueError,
        match="Number of chunks must match number of chunk embeddings",
    ):
        retrieve_relevant_chunks(
            "heart health",
            chunks,
            mismatched_embeddings,
            model,
        )
