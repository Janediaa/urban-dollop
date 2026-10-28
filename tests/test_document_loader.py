import json
import pytest

from src.services.document_loader import (
    discover_documents,
    extract_html_text,
    load_source_metadata,
    load_documents_metadata,
    SOURCES_PATH,
    load_document,
    load_all_documents,
)


def test_extract_html_text_returns_content_and_ignores_script():
    html = """
    <html>
        <body>
            <main>
                <h1>Hypertension</h1>
                <p>High blood pressure</p>
                <script>ignore this</script>
            </main>
        </body>
    </html>
    """

    result = extract_html_text(html)

    assert "Hypertension" in result
    assert "High blood pressure" in result
    assert "ignore this" not in result


def test_load_source_metadata_reads_json(tmp_path, monkeypatch):
    metadata = [
        {
            "filename": "example.html",
            "title": "Example",
            "source": "Example Organization",
            "url": "https://example.org",
        }
    ]

    metadata_path = tmp_path / "sources.json"
    metadata_path.write_text(
        json.dumps(metadata),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "src.services.document_loader.SOURCES_PATH",
        metadata_path,
    )

    result = load_source_metadata()

    assert result == metadata


def test_load_source_metadata_rejects_non_list(tmp_path, monkeypatch):
    metadata_path = tmp_path / "sources.json"
    metadata_path.write_text('{"filename": "example.html"}', encoding="utf-8")

    monkeypatch.setattr(
        "src.services.document_loader.SOURCES_PATH",
        metadata_path,
    )

    with pytest.raises(ValueError, match="JSON list"):
        load_source_metadata()


def test_load_source_metadata_rejects_missing_required_field(
    tmp_path, monkeypatch
):
    metadata_path = tmp_path / "sources.json"
    metadata_path.write_text(
        json.dumps([
            {
                "filename": "example.html",
                "title": "Example",
                "source": "Example Organization",
            }
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "src.services.document_loader.SOURCES_PATH",
        metadata_path,
    )

    with pytest.raises(ValueError, match="missing fields"):
        load_source_metadata()


def test_load_source_metadata_rejects_empty_required_field(
    tmp_path, monkeypatch
):
    metadata_path = tmp_path / "sources.json"
    metadata_path.write_text(
        json.dumps([
            {
                "filename": "",
                "title": "Example",
                "source": "Example Organization",
                "url": "https://example.org",
            }
        ]),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "src.services.document_loader.SOURCES_PATH",
        metadata_path,
    )

    with pytest.raises(ValueError, match="non-empty string"):
        load_source_metadata()



def test_discover_documents_finds_multiple_supported_files(
    tmp_path, monkeypatch
):
    (tmp_path / "first.html").write_text("<p>First</p>", encoding="utf-8")
    (tmp_path / "second.txt").write_text("Second", encoding="utf-8")
    (tmp_path / "ignored.pdf").write_bytes(b"not processed yet")
    (tmp_path / "sources.json").write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        "src.services.document_loader.DOCUMENTS_DIR",
        tmp_path,
    )

    result = discover_documents()

    assert [path.name for path in result] == ["first.html", "second.txt"]


def test_discover_documents_raises_when_directory_missing(
    tmp_path, monkeypatch
):
    missing_directory = tmp_path / "missing"

    monkeypatch.setattr(
        "src.services.document_loader.DOCUMENTS_DIR",
        missing_directory,
    )

    with pytest.raises(FileNotFoundError, match="directory not found"):
        discover_documents()



def test_load_documents_metadata_matches_multiple_files(
    tmp_path, monkeypatch
):
    (tmp_path / "first.html").write_text(
        "<p>First document</p>", encoding="utf-8"
    )
    (tmp_path / "second.txt").write_text(
        "Second document", encoding="utf-8"
    )

    metadata = [
        {
            "filename": "first.html",
            "title": "First",
            "source": "Organization A",
            "url": "https://example.org/first",
        },
        {
            "filename": "second.txt",
            "title": "Second",
            "source": "Organization B",
            "url": "https://example.org/second",
        },
    ]

    metadata_path = tmp_path / "sources.json"
    metadata_path.write_text(
        json.dumps(metadata), encoding="utf-8"
    )

    monkeypatch.setattr(
        "src.services.document_loader.DOCUMENTS_DIR", tmp_path
    )
    monkeypatch.setattr(
        "src.services.document_loader.SOURCES_PATH", metadata_path
    )

    result = load_documents_metadata()

    assert len(result) == 2
    assert result[0]["filename"] == "first.html"
    assert result[0]["source"] == "Organization A"
    assert result[0]["path"] == tmp_path / "first.html"
    assert result[1]["filename"] == "second.txt"
    assert result[1]["source"] == "Organization B"
    assert result[1]["path"] == tmp_path / "second.txt"



def test_load_document_extracts_html(tmp_path):
    path = tmp_path / "example.html"
    path.write_text(
        "<html><body><main><p>Blood pressure</p></main></body></html>",
        encoding="utf-8",
    )

    result = load_document(path)

    assert "Blood pressure" in result


def test_load_document_extracts_txt(tmp_path):
    path = tmp_path / "example.txt"
    path.write_text(
        "Diabetes information\nHealthy lifestyle",
        encoding="utf-8",
    )

    result = load_document(path)

    assert "Diabetes information" in result
    assert "Healthy lifestyle" in result



def test_load_all_documents_returns_text_and_metadata(
    tmp_path, monkeypatch
):
    (tmp_path / "first.html").write_text(
        "<html><body><main><p>Blood pressure information</p></main></body></html>",
        encoding="utf-8",
    )
    (tmp_path / "second.txt").write_text(
        "Diabetes information",
        encoding="utf-8",
    )

    metadata = [
        {
            "filename": "first.html",
            "title": "Blood Pressure",
            "source": "Organization A",
            "url": "https://example.org/blood-pressure",
        },
        {
            "filename": "second.txt",
            "title": "Diabetes",
            "source": "Organization B",
            "url": "https://example.org/diabetes",
        },
    ]

    metadata_path = tmp_path / "sources.json"
    metadata_path.write_text(json.dumps(metadata), encoding="utf-8")

    monkeypatch.setattr(
        "src.services.document_loader.DOCUMENTS_DIR", tmp_path
    )
    monkeypatch.setattr(
        "src.services.document_loader.SOURCES_PATH", metadata_path
    )

    result = load_all_documents()

    assert len(result) == 2
    assert "Blood pressure information" in result[0]["text"]
    assert result[0]["title"] == "Blood Pressure"
    assert result[1]["text"] == "Diabetes information"
    assert result[1]["title"] == "Diabetes"
    assert result[1]["source"] == "Organization B"


def test_load_documents_metadata_generates_defaults_without_metadata(
    tmp_path, monkeypatch
):
    (tmp_path / "unlisted.html").write_text(
        "<p>Unlisted document</p>", encoding="utf-8"
    )

    metadata_path = tmp_path / "sources.json"
    metadata_path.write_text("[]", encoding="utf-8")

    monkeypatch.setattr(
        "src.services.document_loader.DOCUMENTS_DIR", tmp_path
    )
    monkeypatch.setattr(
        "src.services.document_loader.SOURCES_PATH", metadata_path
    )

    documents = load_documents_metadata()

    assert len(documents) == 1
    assert documents[0]["filename"] == "unlisted.html"
    assert documents[0]["title"] == "Unlisted"
    assert documents[0]["source"] == "Unknown — verify source"
    assert documents[0]["url"] == ""
    assert documents[0]["metadata_generated"] is True
