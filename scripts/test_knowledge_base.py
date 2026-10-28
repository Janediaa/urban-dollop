
"""Manually test document loading and chunking with real source files."""

from src.services.document_loader import load_all_documents
from src.services.knowledge_base import chunk_documents


def main() -> None:
    # Load the actual medical documents.
    documents = load_all_documents()

    # Split documents using the default chunk size and overlap.
    chunks = chunk_documents(documents)

    print(f"Documents loaded: {len(documents)}")
    print(f"Total chunks created: {len(chunks)}")
    print("\nChunk counts by document:")

    for document in documents:
        document_chunks = [
            chunk
            for chunk in chunks
            if chunk["filename"] == document["filename"]
        ]
        print(f"- {document['title']}: {len(document_chunks)} chunks")

    if chunks:
        # Measure the length of every chunk.
        chunk_lengths = [len(chunk["text"]) for chunk in chunks]

        print("\nChunk length statistics:")
        print(f"Shortest chunk: {min(chunk_lengths)} characters")
        print(f"Longest chunk: {max(chunk_lengths)} characters")

        print("\nFirst chunk preview (first 300 characters):")
        print(f"Title: {chunks[0]['title']}")
        print(f"Filename: {chunks[0]['filename']}")
        print(chunks[0]["text"][:300])

        print("\nLast chunk preview (first 100 characters):")
        print(f"Title: {chunks[-1]['title']}")
        print(f"Filename: {chunks[-1]['filename']}")
        print(chunks[-1]["text"][:100])
    else:
        print("\nNo chunks were created; length statistics are unavailable.")


if __name__ == "__main__":
    main()
