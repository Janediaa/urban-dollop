
from unittest.mock import MagicMock, patch

import pytest

from src.services.answer_generation_service import generate_grounded_answer


def test_empty_query_raises_value_error():
    with pytest.raises(ValueError, match="query must not be empty"):
        generate_grounded_answer("", [])


def test_empty_retrieved_chunks_return_insufficient_evidence():
    result = generate_grounded_answer(
        query="What causes hypertension?",
        retrieved_chunks=[],
    )

    assert result["status"] == "insufficient_evidence"
    assert result["answer"]
    assert result["sources"] == []


def test_invalid_retrieved_chunks_type_raises_type_error():
    with pytest.raises(
        TypeError,
        match="retrieved_chunks must be a list",
    ):
        generate_grounded_answer("What is hypertension?", None)


@patch("src.services.answer_generation_service.genai.Client")
def test_generated_answer_includes_source_metadata(mock_client_class):
    mock_client = MagicMock()
    mock_client_class.return_value = mock_client

    mock_response = MagicMock()
    mock_response.text = "Risk factors include high salt intake. [S1]"
    mock_client.models.generate_content.return_value = mock_response

    chunk = {
        "filename": "who_hypertension.html",
        "title": "Hypertension",
        "url": "https://www.who.int/",
        "chunk_index": 4,
        "text": "High salt intake is a risk factor for hypertension.",
    }

    with patch.dict("os.environ", {"GEMINI_API_KEY": "test-key"}):
        result = generate_grounded_answer(
            query="What is a risk factor?",
            retrieved_chunks=[chunk],
        )

    assert result["status"] == "success"
    assert result["answer"] == "Risk factors include high salt intake. [S1]"
    assert len(result["sources"]) == 1
    assert result["sources"][0]["id"] == "S1"
    assert result["sources"][0]["filename"] == "who_hypertension.html"
    assert result["sources"][0]["chunk_index"] == 4

    mock_client.models.generate_content.assert_called_once()
