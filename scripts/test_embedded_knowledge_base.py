
"""Manually test embedding the medical knowledge base."""

from src.services.document_loader import load_all_documents
from src.services.knowledge_base import chunk_documents
from src.services.embedding_service import (
    generate_embeddings,
    load_embedding_model,
)


def main() -> None:
    # 1. Load all available medical documents.
    documents = load_all_documents()
    print(f"Documents loaded: {len(documents)}")

    # 2. Split the documents into chunks using default settings.
    chunks = chunk_documents(documents)
    print(f"Chunks created: {len(chunks)}")

    if not chunks:
        print("No chunks available to embed.")
        return

    # 3. Load the embedding model once.
    model = load_embedding_model()

    # 4. Embed every chunk in one call.
    chunk_texts = [chunk["text"] for chunk in chunks]
    embeddings = generate_embeddings(chunk_texts, model)

    # 5. Display the results.
    print(f"Embedding array shape: {embeddings.shape}")

    first_chunk = chunks[0]
    print(f"First chunk title: {first_chunk['title']}")
    print(f"First chunk embedding dimensions: {embeddings.shape[1]}")


if __name__ == "__main__":
    main()
