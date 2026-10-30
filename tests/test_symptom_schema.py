
import pytest
from pydantic import ValidationError

from src.schemas.symptom import (
    ExtractedSymptom,
    SymptomExtractionResult,
)


def test_valid_extracted_symptom():
    symptom = ExtractedSymptom(
        symptom="headache",
        status="present",
        temporality="current",
        experiencer="self",
        duration="since yesterday",
        evidence="my head has been pounding since yesterday",
        confidence=0.85,
    )

    assert symptom.symptom == "headache"
    assert symptom.status == "present"
    assert symptom.experiencer == "self"


def test_confidence_must_be_between_zero_and_one():
    with pytest.raises(ValidationError):
        ExtractedSymptom(
            symptom="headache",
            status="present",
            temporality="current",
            experiencer="self",
            evidence="my head hurts",
            confidence=1.5,
        )


def test_invalid_status_is_rejected():
    with pytest.raises(ValidationError):
        ExtractedSymptom(
            symptom="fever",
            status="maybe",
            temporality="current",
            experiencer="self",
            evidence="I have a fever",
            confidence=0.9,
        )


def test_empty_result_is_valid():
    result = SymptomExtractionResult()

    assert result.symptoms == []
    assert result.requires_clarification is False

def test_resolved_symptom_is_supported():
    symptom = ExtractedSymptom(
        symptom="fever",
        status="absent",
        temporality="historical",
        experiencer="self",
        resolution_status="resolved",
        evidence="I had a fever, but it went away.",
        confidence=0.95,
    )

    assert symptom.status == "absent"
    assert symptom.temporality == "historical"
    assert symptom.resolution_status == "resolved"


def test_resolution_status_defaults_to_unknown():
    symptom = ExtractedSymptom(
        symptom="headache",
        status="present",
        temporality="current",
        experiencer="self",
        evidence="My head hurts.",
        confidence=0.9,
    )

    assert symptom.resolution_status == "unknown"

