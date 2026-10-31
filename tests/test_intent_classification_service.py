
import json
from unittest.mock import MagicMock

import pytest

from src.services import intent_classification_service as intent_module
from src.services.intent_classification_service import (
    IntentClassificationService,
)


def valid_classification():
    return {
        "intent": "symptom_report",
        "subject": "self",
        "temporality": "current",
        "emergency_signal": False,
        "confidence": 0.95,
    }


def test_rejects_empty_question():
    service = IntentClassificationService()

    with pytest.raises(ValueError, match="question must not be empty"):
        service.classify("   ")


def test_missing_api_key_returns_none(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)

    service = IntentClassificationService()

    assert service.classify("I have a headache") is None


def test_valid_classification_is_returned(monkeypatch):
    classification = valid_classification()

    response = MagicMock()
    response.text = json.dumps(classification)

    client = MagicMock()
    client.models.generate_content.return_value = response

    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(
        intent_module.genai,
        "Client",
        lambda **kwargs: client,
    )

    service = IntentClassificationService()

    result = service.classify("I have a headache")

    assert result == classification
    client.models.generate_content.assert_called_once()


def test_fenced_json_response_is_accepted(monkeypatch):
    response = MagicMock()
    response.text = (
        "```json\n"
        + json.dumps(valid_classification())
        + "\n```"
    )

    client = MagicMock()
    client.models.generate_content.return_value = response

    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(
        intent_module.genai,
        "Client",
        lambda **kwargs: client,
    )

    result = IntentClassificationService().classify(
        "I have a headache"
    )

    assert result == valid_classification()


def test_invalid_json_returns_none(monkeypatch):
    response = MagicMock()
    response.text = "{invalid json"

    client = MagicMock()
    client.models.generate_content.return_value = response

    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(
        intent_module.genai,
        "Client",
        lambda **kwargs: client,
    )

    result = IntentClassificationService().classify(
        "I have a headache"
    )

    assert result is None


def test_empty_model_response_returns_none(monkeypatch):
    response = MagicMock()
    response.text = None

    client = MagicMock()
    client.models.generate_content.return_value = response

    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(
        intent_module.genai,
        "Client",
        lambda **kwargs: client,
    )

    result = IntentClassificationService().classify(
        "I have a headache"
    )

    assert result is None


def test_api_failure_returns_none(monkeypatch):
    client = MagicMock()
    client.models.generate_content.side_effect = RuntimeError(
        "Simulated Gemini API failure"
    )

    monkeypatch.setenv("GEMINI_API_KEY", "test-api-key")
    monkeypatch.setattr(
        intent_module.genai,
        "Client",
        lambda **kwargs: client,
    )

    result = IntentClassificationService().classify(
        "I have a headache"
    )

    assert result is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("intent", "emergency"),
        ("subject", "unknown_person"),
        ("temporality", "immediate"),
        ("emergency_signal", "true"),
        ("confidence", 1.5),
        ("confidence", -0.1),
        ("confidence", True),
        ("confidence", "high"),
    ],
)
def test_invalid_classification_fields_are_rejected(field, value):
    classification = valid_classification()
    classification[field] = value

    with pytest.raises(ValueError):
        IntentClassificationService._validate(classification)


@pytest.mark.parametrize(
    "classification",
    [
        {
            **valid_classification(),
            "intent": "medical_question",
            "subject": "hypothetical",
            "emergency_signal": True,
        },
        {
            **valid_classification(),
            "temporality": "historical",
            "emergency_signal": True,
        },
        {
            **valid_classification(),
            "subject": "general",
            "emergency_signal": True,
        },
    ],
)
def test_inconsistent_emergency_classifications_are_rejected(
    classification,
):
    with pytest.raises(ValueError, match="Inconsistent emergency"):
        IntentClassificationService._validate(classification)


def test_historical_symptom_classification_is_valid():
    classification = {
        "intent": "symptom_report",
        "subject": "self",
        "temporality": "historical",
        "emergency_signal": False,
        "confidence": 0.96,
    }

    result = IntentClassificationService._validate(classification)

    assert result["temporality"] == "historical"
    assert result["emergency_signal"] is False


def test_general_medical_question_classification_is_valid():
    classification = {
        "intent": "medical_question",
        "subject": "general",
        "temporality": "unknown",
        "emergency_signal": False,
        "confidence": 0.98,
    }

    result = IntentClassificationService._validate(classification)

    assert result["intent"] == "medical_question"
    assert result["subject"] == "general"
