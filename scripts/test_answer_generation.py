
from src.services.answer_generation_service import generate_grounded_answer


retrieved_chunks = [
    {
        "filename": "who_hypertension.html",
        "title": "Hypertension",
        "url": "https://www.who.int/news-room/fact-sheets/detail/hypertension",
        "chunk_index": 4,
        "text": (
            "Risk factors for hypertension include high salt intake, "
            "physical inactivity, tobacco use, harmful use of alcohol, "
            "and being overweight or obese."
        ),
    }
]

result = generate_grounded_answer(
    query="What are the risk factors for hypertension?",
    retrieved_chunks=retrieved_chunks,
)

print("Status:", result["status"])
print("\nAnswer:\n", result["answer"])
print("\nSources:")

for source in result["sources"]:
    print(
        source["id"],
        source["title"],
        source["filename"],
        "chunk:", source["chunk_index"],
    )
