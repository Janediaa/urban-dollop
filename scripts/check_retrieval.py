
from src.services.document_loader import load_all_documents
from src.services.knowledge_base import chunk_documents, embed_chunks
from src.services.embedding_service import load_embedding_model
from src.services.retrieval_service import retrieve_relevant_chunks

docs = load_all_documents()
chunks = chunk_documents(docs)
model = load_embedding_model()
embeddings = embed_chunks(chunks, model)


questions = [
    "Which factors increase a person's risk of developing type 2 diabetes?",
    "How does tuberculosis spread from an infected person to another person?",
    "What sudden symptoms indicate a possible stroke and require emergency care?",
]


for question in questions:
    print(f"\n{'=' * 80}")
    print(f"QUESTION: {question}")
    print("=" * 80)

    results = retrieve_relevant_chunks(
        query=question,
        chunks=chunks,
        chunk_embeddings=embeddings,
        model=model,
        top_k=3,
    )

    for rank, result in enumerate(results, start=1):
        print(
            f"\n{rank}. {result['filename']} "
            f"| score={result['similarity_score']:.4f}"
        )
        print(result["text"].replace("\n", " "))
