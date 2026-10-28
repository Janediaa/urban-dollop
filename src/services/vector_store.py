
"""Persistent FAISS vector store for medical document chunks."""

import json
from pathlib import Path

import faiss
import numpy as np


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VECTOR_STORE_DIR = PROJECT_ROOT / "data" / "processed" / "medical_vector_store"
INDEX_PATH = VECTOR_STORE_DIR / "medical.index"
CHUNKS_PATH = VECTOR_STORE_DIR / "chunks.json"


class MedicalVectorStore:
    """Store medical chunk embeddings and metadata persistently."""

    def __init__(self, directory: Path = VECTOR_STORE_DIR) -> None:
        self.directory = Path(directory)
        self.index_path = self.directory / "medical.index"
        self.chunks_path = self.directory / "chunks.json"
        self.index = None
        self.chunks: list[dict] = []

    def build(self, chunks: list[dict], embeddings) -> None:
        """Build a new index and save its associated chunks."""
        vectors = np.asarray(embeddings, dtype=np.float32)

        if not chunks:
            raise ValueError("Cannot build a vector store without chunks.")

        if vectors.ndim != 2 or vectors.shape[0] != len(chunks):
            raise ValueError("Chunk and embedding counts must match.")

        if vectors.shape[1] == 0:
            raise ValueError("Embedding dimension must be positive.")

        if not np.isfinite(vectors).all():
            raise ValueError("Embeddings must contain only finite values.")

        self.directory.mkdir(parents=True, exist_ok=True)

        # Normalize vectors so inner-product ranking equals cosine similarity.
        faiss.normalize_L2(vectors)

        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)

        with self.chunks_path.open("w", encoding="utf-8") as file:
            json.dump(
                chunks,
                file,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

        faiss.write_index(index, str(self.index_path))

        self.index = index
        self.chunks = chunks

    def load(self) -> None:
        """Load the saved index and chunk metadata."""
        if not self.index_path.exists() or not self.chunks_path.exists():
            raise FileNotFoundError(
                "Persistent medical vector store has not been built."
            )

        index = faiss.read_index(str(self.index_path))

        with self.chunks_path.open("r", encoding="utf-8") as file:
            chunks = json.load(file)

        if not isinstance(chunks, list) or len(chunks) != index.ntotal:
            raise ValueError(
                "Saved chunk metadata does not match the vector index."
            )

        self.index = index
        self.chunks = chunks

    def search(self, query_embedding, top_k: int = 3) -> list[dict]:
        """Return the most similar chunks with their similarity scores."""
        if self.index is None:
            raise RuntimeError("Load or build the vector store before searching.")

        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k <= 0:
            raise ValueError("top_k must be a positive integer.")

        query = np.asarray(query_embedding, dtype=np.float32)

        if query.ndim == 1:
            query = query.reshape(1, -1)

        if query.ndim != 2 or query.shape[0] != 1:
            raise ValueError("Query embedding must contain one vector.")

        if query.shape[1] != self.index.d:
            raise ValueError("Query and index dimensions must match.")

        if not np.isfinite(query).all():
            raise ValueError("Query embedding must contain only finite values.")

        if np.linalg.norm(query) == 0:
            raise ValueError("Query embedding must not be a zero vector.")

        faiss.normalize_L2(query)

        scores, indices = self.index.search(
            query,
            min(top_k, self.index.ntotal),
        )

        results = []

        for score, index in zip(scores[0], indices[0]):
            if index < 0:
                continue

            result = self.chunks[int(index)].copy()
            result["similarity_score"] = float(score)
            results.append(result)

        return results
