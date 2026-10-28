
"""Test sentence embeddings using a pretrained SentenceTransformer model."""

from sentence_transformers import SentenceTransformer


def main() -> None:
    # Load the model on the CPU.
    model = SentenceTransformer(
        "sentence-transformers/all-MiniLM-L6-v2",
        device="cpu",
    )

    sentences = [
        "High blood pressure is called hypertension.",
        "Hypertension can increase the risk of heart disease.",
        "The brain processes information through neural networks.",
    ]

    # Convert each sentence into a numerical embedding.
    embeddings = model.encode(sentences)

    print(f"Maximum sequence length: {model.max_seq_length}")
    print(f"Embedding array shape: {embeddings.shape}")
    print(f"First five numbers in the first embedding: {embeddings[0][:5]}")


if __name__ == "__main__":
    main()
