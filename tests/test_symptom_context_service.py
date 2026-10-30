
import pytest

from src.services.symptom_context_service import (
    analyze_symptom_context,
    analyze_symptom_contexts,
)

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "I have a fever.",
            {
                "status": "present",
                "temporality": "current",
                "experiencer": "self",
                "resolution_status": "active",
            },
        ),
        (
            "I don't have a fever.",
            {
                "status": "absent",
                "temporality": "current",
                "experiencer": "self",
                "resolution_status": "unknown",
            },
        ),
        (
            "I had a fever last week.",
            {
                "status": "present",
                "temporality": "historical",
                "experiencer": "self",
                "resolution_status": "unknown",
            },
        ),
        (
            "My fever went away.",
            {
                "status": "present",
                "temporality": "historical",
                "experiencer": "self",
                "resolution_status": "resolved",
            },
        ),
        (
            "I might have a fever.",
            {
                "status": "uncertain",
                "temporality": "unknown",
                "experiencer": "self",
                "resolution_status": "unknown",
            },
        ),
        (
            "My mother has a fever.",
            {
                "status": "present",
                "temporality": "current",
                "experiencer": "other",
                "resolution_status": "active",
            },
        ),
    ],
)
def test_context_analysis(text, expected):
    assert analyze_symptom_context(text) == expected

def test_context_is_associated_with_individual_symptoms():
    evidence_records = [
        {
            "symptom": "headache",
            "evidence": "I have a headache",
        },
        {
            "symptom": "fever",
            "evidence": "I don't have a fever",
        },
    ]

    result = analyze_symptom_contexts(evidence_records)

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
            "evidence": "I don't have a fever",
            "status": "absent",
            "temporality": "current",
            "experiencer": "self",
            "resolution_status": "unknown",
        },
    ]


def test_context_preserves_different_experiencers():
    evidence_records = [
        {
            "symptom": "headache",
            "evidence": "I have a headache",
        },
        {
            "symptom": "cough",
            "evidence": "My mother has a cough",
        },
    ]

    result = analyze_symptom_contexts(evidence_records)

    assert [record["experiencer"] for record in result] == [
        "self",
        "other",
    ]


def test_context_handles_historical_symptoms_independently():
    evidence_records = [
        {
            "symptom": "fever",
            "evidence": "I had a fever last week",
        },
        {
            "symptom": "cough",
            "evidence": "I have a cough",
        },
    ]

    result = analyze_symptom_contexts(evidence_records)

    assert result[0]["temporality"] == "historical"
    assert result[0]["status"] == "present"

    assert result[1]["temporality"] == "current"
    assert result[1]["status"] == "present"

