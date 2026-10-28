
"""Generate local semantic embeddings for medical text."""

from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def load_embedding_model() -> SentenceTransformer:
    """Load the embedding model on the CPU."""
    model = SentenceTransformer(MODEL_NAME, device="cpu")
    return model


def generate_embeddings(
    texts: list[str],
    model: SentenceTransformer,
):
    """Convert a list of texts into embedding vectors."""
    embeddings = model.encode(texts)
    return embeddings
