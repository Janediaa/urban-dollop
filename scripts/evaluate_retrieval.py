
"""Evaluate medical retrieval using manually judged relevant chunks."""

from src.services.document_loader import load_all_documents
from src.services.knowledge_base import chunk_documents, embed_chunks
from src.services.embedding_service import load_embedding_model
from src.services.retrieval_service import retrieve_relevant_chunks


EVALUATION_CASES = [
    {
        "query": "What are the risk factors for hypertension?",
        "expected_content": "The WHO risk-factor discussion",
    },
    {
        "query": "What symptoms can high blood pressure cause?",
        "expected_content": (
            "The symptoms section, including the caveat that "
            "most people have no symptoms"
        ),
    },
    {
        "query": "How can hypertension be prevented?",
        "expected_content": (
            "The prevention section or lifestyle measures such as a "
            "healthy low-salt diet, physical activity, and avoiding tobacco"
        ),
    },
]

# These labels must be verified against the actual chunk excerpts.
# Each index refers to the position in the complete `chunks` list,
# not necessarily the per-document chunk_index.
RELEVANT_CHUNKS = {
    "What are the risk factors for hypertension?": {
        ("who_hypertension.html", 2),
        ("who_hypertension.html", 3),
        ("who_hypertension.html", 4),
    },
    "What symptoms can high blood pressure cause?": {
        ("who_hypertension.html", 4),
        ("who_hypertension.html", 5),
    },
    "How can hypertension be prevented?": {
        ("who_hypertension.html", 8),
        ("who_hypertension.html", 9),
        ("who_hypertension.html", 10),
    },
}


def main() -> None:
    documents = load_all_documents()
    if not documents:
        print("No supported medical documents were found.")
        return

    chunks = chunk_documents(documents)
    if not chunks:
        print("No chunks were created.")
        return

    print(f"Documents loaded: {len(documents)}")
    print(f"Chunks created: {len(chunks)}")

    # Load the model once and generate chunk embeddings once.
    model = load_embedding_model()
    chunk_embeddings = embed_chunks(chunks, model)
    print(f"Embedding shape: {chunk_embeddings.shape}")

    # Inspect actual chunk content before trusting relevance labels.
    print("\n" + "=" * 80)
    print("CHUNK INSPECTION: use these excerpts to verify relevance labels")
    print("=" * 80)

    for index, chunk in enumerate(chunks):
        print(f"\nChunk index: {index}")
        print(f"Title: {chunk.get('title', 'Unknown')}")
        print(f"Filename: {chunk.get('filename', 'Unknown')}")
        print(chunk["text"][:600].strip())

    print("\n" + "=" * 80)
    print("RETRIEVAL EVALUATION")
    print("=" * 80)

    precision_scores = []
    missing_labels = []

    for case in EVALUATION_CASES:
        query = case["query"]
        relevant_chunks = RELEVANT_CHUNKS.get(query, set())

        print(f"\nQuery: {query}")
        print(f"Expected content: {case['expected_content']}")

        results = retrieve_relevant_chunks(
            query=query,
            chunks=chunks,
            chunk_embeddings=chunk_embeddings,
            model=model,
            top_k=3,
        )

        if not relevant_chunks:
            missing_labels.append(query)
            print(
                "Relevance labels not assigned. Inspect the chunks above, "
                "update RELEVANT_CHUNKS, and rerun."
            )

            for rank, result in enumerate(results, start=1):
                chunk_index = result["chunk_index"]
                print(
                    f"  Rank {rank}: filename={result.get('filename', 'Unknown')}, "
                    f"chunk_index={chunk_index}, "
                    f"score={result['similarity_score']:.4f}"
                )
                print(f"    Excerpt: {result['text'][:250].strip()}")

            continue

        
        relevant_count = 0

        for rank, result in enumerate(results, start=1):
            is_relevant = (
                result.get("filename"),
                result.get("chunk_index"),
            ) in relevant_chunks

            relevant_count += int(is_relevant)
            label = "RELEVANT" if is_relevant else "NOT RELEVANT"

            print(
                f"\n  Rank {rank}: "
                f"filename={result.get('filename', 'Unknown')}, "
                f"chunk_index={result['chunk_index']}, "
                f"score={result['similarity_score']:.4f}, "
                f"{label}"
            )
            print(f"    Excerpt: {result['text'][:250].strip()}")

        # Divide by the number actually retrieved (up to three results).
        precision_at_3 = relevant_count / len(results) if results else 0.0
        precision_scores.append(precision_at_3)
        print(
            f"\nPrecision@3: {relevant_count}/{len(results)} "
            f"= {precision_at_3:.2f}"
        )

    if missing_labels:
        print(
            "\nMean Precision@3 is provisional: relevance labels are missing "
            "for the following queries:"
        )
        for query in missing_labels:
            print(f"  - {query}")

    if precision_scores and not missing_labels:
        mean_precision = sum(precision_scores) / len(precision_scores)
        print(f"\nMean Precision@3: {mean_precision:.2f}")
    else:
        print(
            "\nMean Precision@3 unavailable as a complete evaluation. "
            "Verify relevance labels for all three queries and rerun."
        )


if __name__ == "__main__":
    main()