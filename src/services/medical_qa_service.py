
"""Orchestrate medical document retrieval and grounded answer generation."""

import hashlib
import json

from src.services.answer_generation_service import generate_grounded_answer
from src.services.document_loader import load_all_documents
from src.services.embedding_service import load_embedding_model
from src.services.knowledge_base import chunk_documents, embed_chunks
from src.services.retrieval_service import retrieve_relevant_chunks
from src.services.vector_store import MedicalVectorStore


CHUNK_SIZE = 800
CHUNK_OVERLAP = 120
EMBEDDING_MODEL_ID = "sentence-transformers/all-MiniLM-L6-v2"


def _source_fingerprint(documents: list[dict]) -> str:
    """Hash source content, metadata, and settings affecting the index."""
    sources = []

    for document in documents:
        sources.append({
            "metadata": {
                key: value
                for key, value in document.items()
                if key not in {"text", "path"}
            },
            "text": document["text"],
        })

    payload = {
        "sources": sources,
        "chunk_size": CHUNK_SIZE,
        "chunk_overlap": CHUNK_OVERLAP,
        "embedding_model": EMBEDDING_MODEL_ID,
    }

    serialized = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )

    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


class MedicalQAService:
    """Reusable medical question-answering service."""

    def __init__(self) -> None:
        """Load a valid saved index or build one from source documents."""
        documents = load_all_documents()

        if not documents:
            raise RuntimeError("No medical documents were loaded")

        fingerprint = _source_fingerprint(documents)
        self.vector_store = MedicalVectorStore()
        self.manifest_path = self.vector_store.directory / "manifest.json"

        manifest_matches = False

        try:
            with self.manifest_path.open("r", encoding="utf-8") as file:
                manifest = json.load(file)

            manifest_matches = (
                isinstance(manifest, dict)
                and manifest.get("fingerprint") == fingerprint
            )
        except (OSError, json.JSONDecodeError):
            manifest_matches = False

        if manifest_matches:
            try:
                self.vector_store.load()
            except (OSError, ValueError, RuntimeError):
                manifest_matches = False

        self.model = load_embedding_model()

        if manifest_matches:
            self.chunks = self.vector_store.chunks
            self.embeddings = None
            return

        self.chunks = chunk_documents(
            documents,
            chunk_size=CHUNK_SIZE,
            overlap=CHUNK_OVERLAP,
        )

        if not self.chunks:
            raise RuntimeError(
                "No chunks were generated from medical documents"
            )

        self.embeddings = embed_chunks(self.chunks, self.model)
        self.vector_store.build(self.chunks, self.embeddings)

        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)

        with self.manifest_path.open("w", encoding="utf-8") as file:
            json.dump({"fingerprint": fingerprint}, file, indent=2)

    def ask(self, query: str, top_k: int = 3) -> dict:
        """Retrieve relevant evidence and generate a grounded answer."""
        retrieved_chunks = retrieve_relevant_chunks(
            query=query,
            chunks=self.chunks,
            chunk_embeddings=self.embeddings,
            model=self.model,
            top_k=top_k,
            vector_store=self.vector_store,
        )

        return generate_grounded_answer(
            query=query,
            retrieved_chunks=retrieved_chunks,
        )
