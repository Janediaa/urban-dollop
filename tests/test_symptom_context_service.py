
import pytest

from src.services.symptom_context_service import analyze_symptom_context


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
