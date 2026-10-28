
"""Test semantic similarity using sentence embeddings."""

from sentence_transformers import SentenceTransformer, util


def main() -> None:
    # Load the previously used model on the CPU.
    model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2",
        device="cpu",
    )

    sentences = [
        "High blood pressure is called hypertension.",
        "Hypertension can increase the risk of heart disease.",
        "The brain processes information through neural networks.",
    ]

    # Generate embeddings for all three sentences.
    embeddings = model.encode(sentences)

    # Compare sentence 1 with sentence 2.
    similarity_1_2 = util.cos_sim(embeddings[0], embeddings[1]).item()

    # Compare sentence 1 with sentence 3.
    similarity_1_3 = util.cos_sim(embeddings[0], embeddings[2]).item()

    print(f"Similarity (sentence 1 vs. sentence 2): {similarity_1_2:.4f}")
    print(f"Similarity (sentence 1 vs. sentence 3): {similarity_1_3:.4f}")

    print(
        "Is sentence 1 more similar to sentence 2 than sentence 3?",
        similarity_1_2 > similarity_1_3,
    )


if __name__ == "__main__":
    main()
