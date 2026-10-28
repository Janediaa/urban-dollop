
"""Retrieve relevant medical chunks using cosine similarity or FAISS."""

import numpy as np
from sentence_transformers import SentenceTransformer, util

from src.services.embedding_service import generate_embeddings
from src.services.vector_store import MedicalVectorStore


def retrieve_relevant_chunks(
    query: str,
    chunks: list[dict],
    chunk_embeddings,
    model: SentenceTransformer,
    top_k: int = 3,
    vector_store: MedicalVectorStore | None = None,
) -> list[dict]:
    """Rank chunks by similarity, optionally using a persistent FAISS index."""
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must not be empty")

    if not isinstance(top_k, int) or isinstance(top_k, bool):
        raise TypeError("top_k must be an integer")

    if top_k <= 0:
        raise ValueError("top_k must be positive")

    if not chunks:
        return []

    query_embeddings = np.asarray(generate_embeddings([query], model))

    if query_embeddings.ndim != 2 or query_embeddings.shape[0] != 1:
        raise ValueError("query embedding must contain exactly one vector")

    if not np.isfinite(query_embeddings).all():
        raise ValueError("query embedding must contain only finite values")

    if vector_store is not None:
        return vector_store.search(query_embeddings, top_k=top_k)

    embeddings = np.asarray(chunk_embeddings)

    if embeddings.ndim != 2:
        raise ValueError("chunk_embeddings must be a 2D array")

    if len(chunks) != embeddings.shape[0]:
        raise ValueError(
            "Number of chunks must match number of chunk embeddings"
        )

    if not np.isfinite(embeddings).all():
        raise ValueError("chunk_embeddings must contain only finite values")

    if query_embeddings.shape[1] != embeddings.shape[1]:
        raise ValueError(
            "Query and chunk embeddings must have the same dimensions"
        )

    similarities = util.cos_sim(query_embeddings, embeddings)[0]
    ranked_indices = similarities.argsort(descending=True)[:top_k]

    results = []

    for index in ranked_indices:
        chunk_index = int(index)
        result = chunks[chunk_index].copy()
        result["similarity_score"] = float(similarities[chunk_index])
        results.append(result)

    return results
