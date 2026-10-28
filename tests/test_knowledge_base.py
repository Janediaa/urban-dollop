import numpy as np
import pytest

from src.services.embedding_service import load_embedding_model
from src.services.knowledge_base import chunk_documents, embed_chunks



def test_chunk_documents_preserves_metadata_and_resets_indices():
    documents = [
        {
            "filename": "heart.html",
            "title": "Heart Health",
            "source": "Test Source A",
            "url": "https://example.org/heart",
            "text": "ABCDEFGHIJ",
        },
        {
            "filename": "brain.html",
            "title": "Brain Health",
            "source": "Test Source B",
            "url": "https://example.org/brain",
            "text": "KLMNOP",
        },
    ]

    result = chunk_documents(
        documents,
        chunk_size=4,
        overlap=0,
    )

    # 10 characters -> 3 chunks; 6 characters -> 2 chunks.
    assert len(result) == 5

    heart_chunks = [
        chunk for chunk in result
        if chunk["filename"] == "heart.html"
    ]
    brain_chunks = [
        chunk for chunk in result
        if chunk["filename"] == "brain.html"
    ]

    assert len(heart_chunks) == 3
    assert len(brain_chunks) == 2

    # Metadata should be preserved on every chunk.
    assert all(
        chunk["title"] == "Heart Health"
        and chunk["source"] == "Test Source A"
        and chunk["url"] == "https://example.org/heart"
        for chunk in heart_chunks
    )
    assert all(
        chunk["title"] == "Brain Health"
        and chunk["source"] == "Test Source B"
        and chunk["url"] == "https://example.org/brain"
        for chunk in brain_chunks
    )

    # Indices must restart from zero for each document.
    assert [chunk["chunk_index"] for chunk in heart_chunks] == [0, 1, 2]
    assert [chunk["chunk_index"] for chunk in brain_chunks] == [0, 1]

    # Each chunk should contain the expected text.
    assert [chunk["text"] for chunk in heart_chunks] == [
        "ABCD", "EFGH", "IJ"
    ]
    assert [chunk["text"] for chunk in brain_chunks] == [
        "KLMN", "OP"
    ]


@pytest.fixture(scope="module")
def embedding_model():
    """Load the real embedding model once for this test module."""
    return load_embedding_model()


def test_embed_chunks_returns_embeddings_without_changing_chunks(
    embedding_model,
):
    chunks = [
        {
            "filename": "heart.html",
            "title": "Heart Health",
            "source": "Test Source A",
            "url": "https://example.org/heart",
            "chunk_index": 0,
            "text": "Regular exercise supports heart health.",
        },
        {
            "filename": "brain.html",
            "title": "Brain Health",
            "source": "Test Source B",
            "url": "https://example.org/brain",
            "chunk_index": 0,
            "text": "Sleep helps the brain process information.",
        },
    ]

    # Save a copy to verify that embedding doesn't modify the chunks.
    original_chunks = [chunk.copy() for chunk in chunks]

    embeddings = embed_chunks(chunks, embedding_model)

    assert embeddings.shape == (2, 384)
    assert chunks == original_chunks
    assert np.isfinite(embeddings).all()
