"""Prepare document chunks for the medical knowledge base."""
from sentence_transformers import SentenceTransformer

from src.services.embedding_service import generate_embeddings
from src.services.text_chunker import chunk_text


def chunk_documents(
    documents: list[dict],
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[dict]:
    """Split documents into chunks while preserving their metadata."""
    all_chunks = []

    for document in documents:
        text_chunks = chunk_text(
            document["text"],
            chunk_size=chunk_size,
            overlap=overlap,
        )

        for chunk_index, text in enumerate(text_chunks):
            chunk_record = {
                **{
                    key: value
                    for key, value in document.items()
                    if key != "text"
                },
                "chunk_index": chunk_index,
                "text": text,
            }
            all_chunks.append(chunk_record)

    return all_chunks

def embed_chunks(
    chunks: list[dict],
    model: SentenceTransformer,
):
    """Generate embeddings for chunks without modifying their records."""
    texts = [chunk["text"] for chunk in chunks]
    embeddings = generate_embeddings(texts, model)
    return embeddings
