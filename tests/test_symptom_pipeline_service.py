
from src.services.symptom_pipeline_service import SymptomPipelineService


def test_extracts_multiple_symptoms_with_individual_context():
    service = SymptomPipelineService()

    result = service.extract_symptoms(
        "I have a headache, but I don't have a fever."
    )

    assert result == [
        {
            "symptom": "headache",
            "evidence": "I have a headache",
            "status": "present",
            "temporality": "current",
            "experiencer": "self",
            "resolution_status": "active",
        },
        {
            "symptom": "fever",
            "evidence": "I don't have a fever.",
            "status": "absent",
            "temporality": "current",
            "experiencer": "self",
            "resolution_status": "unknown",
        },
    ]


def test_distinguishes_symptoms_of_different_people():
    service = SymptomPipelineService()

    result = service.extract_symptoms(
        "I have a headache. My mother has a cough."
    )

    assert [
        (record["symptom"], record["experiencer"])
        for record in result
    ] == [
        ("headache", "self"),
        ("cough", "other"),
    ]


def test_preserves_historical_and_current_symptoms():
    service = SymptomPipelineService()

    result = service.extract_symptoms(
        "I had a fever last week. I have a cough."
    )

    assert [
        (record["symptom"], record["temporality"])
        for record in result
    ] == [
        ("fever", "historical"),
        ("cough", "current"),
    ]


def test_returns_empty_list_for_unrecognized_input():
    service = SymptomPipelineService()

    assert service.extract_symptoms(
        "My laptop battery is draining."
    ) == []


def test_returns_empty_list_for_empty_input():
    service = SymptomPipelineService()

    assert service.extract_symptoms("") == []


def test_pipeline_uses_semantic_extraction():
    class FakeConceptExtractor:
        def extract_concepts(self, text):
            if "head has been pounding" in text.lower():
                return ["headache"]
            return []

    extractor = FakeConceptExtractor()

    service = SymptomPipelineService(
        concept_extractor=extractor.extract_concepts
    )

    result = service.extract_symptoms(
        "My head has been pounding since yesterday."
    )

    assert result == [
        {
            "symptom": "headache",
            "evidence": "My head has been pounding since yesterday.",
            "status": "present",
            "temporality": "historical",
            "experiencer": "self",
            "resolution_status": "unknown",
        }
    ]

