
from src.services.symptom_evidence_service import SymptomEvidenceService


def test_extracts_symptoms_from_multiple_sentences():
    service = SymptomEvidenceService()

    result = service.extract_evidence(
        "I have a headache. I also have a fever."
    )

    assert result == [
        {
            "symptom": "headache",
            "evidence": "I have a headache.",
        },
        {
            "symptom": "fever",
            "evidence": "I also have a fever.",
        },
    ]


def test_extracts_clause_specific_evidence():
    service = SymptomEvidenceService()

    result = service.extract_evidence(
        "I have a headache, but I don't have a fever."
    )

    assert result == [
        {
            "symptom": "headache",
            "evidence": "I have a headache",
        },
        {
            "symptom": "fever",
            "evidence": "I don't have a fever.",
        },
    ]


def test_multiple_symptoms_in_same_clause_share_evidence():
    service = SymptomEvidenceService()

    result = service.extract_evidence(
        "I have a headache and fever."
    )

    assert result == [
        {
            "symptom": "headache",
            "evidence": "I have a headache and fever.",
        },
        {
            "symptom": "fever",
            "evidence": "I have a headache and fever.",
        },
    ]


def test_returns_empty_list_for_unrecognized_text():
    service = SymptomEvidenceService()

    assert service.extract_evidence(
        "My laptop battery is draining quickly."
    ) == []


def test_empty_input_returns_empty_list():
    service = SymptomEvidenceService()

    assert service.extract_evidence("") == []


def test_semantic_extractor_detects_paraphrased_symptoms():
    class FakeConceptExtractor:
        def extract_concepts(self, text):
            if "head has been pounding" in text.lower():
                return ["headache"]
            return []

    extractor = FakeConceptExtractor()

    service = SymptomEvidenceService(
        concept_extractor=extractor.extract_concepts
    )

    result = service.extract_evidence(
        "My head has been pounding since yesterday."
    )

    assert result == [
        {
            "symptom": "headache",
            "evidence": "My head has been pounding since yesterday.",
        }
    ]


def test_semantic_and_lexical_matches_are_deduplicated():
    class FakeConceptExtractor:
        def extract_concepts(self, text):
            return ["headache", "fever"]

    service = SymptomEvidenceService(
        concept_extractor=FakeConceptExtractor().extract_concepts
    )

    result = service.extract_evidence(
        "I have a headache."
    )

    assert result == [
        {
            "symptom": "headache",
            "evidence": "I have a headache.",
        },
        {
            "symptom": "fever",
            "evidence": "I have a headache.",
        },
    ]

