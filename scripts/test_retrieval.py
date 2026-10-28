
"""Manually evaluate semantic retrieval against medical documents."""

from src.services.document_loader import load_all_documents
from src.services.knowledge_base import chunk_documents, embed_chunks
from src.services.embedding_service import load_embedding_model
from src.services.retrieval_service import retrieve_relevant_chunks


QUERIES = [
    "What are the risk factors for hypertension?",
    "What symptoms can high blood pressure cause?",
    "How can hypertension be prevented?",
]


def main() -> None:
    # 1. Load the available medical documents.
    documents = load_all_documents()
    print(f"Documents loaded: {len(documents)}")

    if not documents:
        print("No documents found. Check the medical documents directory.")
        return

    # 2. Create chunks using the default chunk size and overlap.
    chunks = chunk_documents(documents)
    print(f"Chunks created: {len(chunks)}")

    if not chunks:
        print("No chunks available for retrieval.")
        return

    # 3. Load the model once.
    model = load_embedding_model()

    # 4. Generate embeddings once and reuse them for every query.
    chunk_embeddings = embed_chunks(chunks, model)
    print(f"Chunk embedding shape: {chunk_embeddings.shape}")

    # 5. Retrieve and inspect the top three passages for each query.
    for query in QUERIES:
        print("\n" + "=" * 80)
        print(f"QUERY: {query}")
        print("=" * 80)

        results = retrieve_relevant_chunks(
            query=query,
            chunks=chunks,
            chunk_embeddings=chunk_embeddings,
            model=model,
            top_k=3,
        )

        if not results:
            print("No results returned.")
            continue

        for rank, result in enumerate(results, start=1):
            print(f"\nResult {rank}")
            print(f"Title: {result.get('title', 'Unknown')}")
            print(f"Source: {result.get('source', 'Unknown')}")
            print(f"Filename: {result.get('filename', 'Unknown')}")
            print(f"Chunk index: {result.get('chunk_index', 'Unknown')}")
            print(f"Similarity: {result['similarity_score']:.4f}")
            print(f"Excerpt: {result['text'][:400].strip()}")

            if len(result["text"]) > 400:
                print("...")

if __name__ == "__main__":
    main()
