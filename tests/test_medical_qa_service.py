
from unittest.mock import MagicMock, patch

import pytest

from src.services.medical_qa_service import MedicalQAService


@patch("src.services.medical_qa_service.embed_chunks")
@patch("src.services.medical_qa_service.load_embedding_model")
@patch("src.services.medical_qa_service.chunk_documents")
@patch("src.services.medical_qa_service.load_all_documents")
def test_initialization_prepares_knowledge_base_once(
    mock_load_documents,
    mock_chunk_documents,
    mock_load_model,
    mock_embed_chunks,
):
    mock_load_documents.return_value = [{"text": "Medical information"}]
    mock_chunk_documents.return_value = [
        {"text": "Medical information", "filename": "who_test.html"}
    ]
    mock_load_model.return_value = MagicMock()
    mock_embed_chunks.return_value = [[0.1, 0.2, 0.3]]

    service = MedicalQAService()

    assert len(service.chunks) == 1
    mock_load_documents.assert_called_once()
    mock_chunk_documents.assert_called_once()
    mock_load_model.assert_called_once()
    mock_embed_chunks.assert_called_once()


@patch("src.services.medical_qa_service.generate_grounded_answer")
@patch("src.services.medical_qa_service.retrieve_relevant_chunks")
@patch("src.services.medical_qa_service.embed_chunks")
@patch("src.services.medical_qa_service.load_embedding_model")
@patch("src.services.medical_qa_service.chunk_documents")
@patch("src.services.medical_qa_service.load_all_documents")
def test_ask_connects_retrieval_to_answer_generation(
    mock_load_documents,
    mock_chunk_documents,
    mock_load_model,
    mock_embed_chunks,
    mock_retrieve,
    mock_generate,
):
    mock_load_documents.return_value = [{"text": "Medical information"}]
    mock_chunk_documents.return_value = [
        {"text": "Medical information", "filename": "who_test.html"}
    ]
    mock_load_model.return_value = MagicMock()
    mock_embed_chunks.return_value = [[0.1, 0.2, 0.3]]

    retrieved = [
        {
            "text": "High salt intake is a risk factor.",
            "filename": "who_hypertension.html",
            "chunk_index": 4,
            "similarity_score": 0.8,
        }
    ]
    expected = {
        "status": "success",
        "answer": "High salt intake is a risk factor. [S1]",
        "sources": [],
    }

    mock_retrieve.return_value = retrieved
    mock_generate.return_value = expected

    service = MedicalQAService()
    result = service.ask("What is a risk factor?", top_k=2)

    assert result == expected

    mock_retrieve.assert_called_once_with(
        query="What is a risk factor?",
        chunks=service.chunks,
        chunk_embeddings=service.embeddings,
        model=service.model,
        top_k=2,
        vector_store=service.vector_store,
    )
    mock_generate.assert_called_once_with(
        query="What is a risk factor?",
        retrieved_chunks=retrieved,
    )


@patch("src.services.medical_qa_service.load_all_documents")
def test_initialization_fails_when_no_documents_are_available(
    mock_load_documents,
):
    mock_load_documents.return_value = []

    with pytest.raises(RuntimeError, match="No medical documents were loaded"):
        MedicalQAService()
