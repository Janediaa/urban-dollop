import json
from pathlib import Path

from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DOCUMENTS_DIR = PROJECT_ROOT / "data" / "medical_documents"
SOURCES_PATH = DOCUMENTS_DIR / "sources.json"

def extract_html_text(html: str) -> str:
    """Extract readable text from an HTML document."""
    soup = BeautifulSoup(html, "html.parser")

    for element in soup.select(
        "script, style, noscript, nav, footer, header"
    ):
        element.decompose()

    content = soup.find("main") or soup.find("article")

    if content is None:
        content = soup.body or soup

    extracted_text = content.get_text(separator="\n", strip=True)

    lines = [
        " ".join(line.split())
        for line in extracted_text.splitlines()
        if line.strip()
    ]

    return "\n".join(lines)



def load_source_metadata() -> list[dict]:
    """Load and validate source metadata from sources.json."""
    if not SOURCES_PATH.exists():
        return []

    with SOURCES_PATH.open("r", encoding="utf-8") as file:
        metadata = json.load(file)

    if not isinstance(metadata, list):
        raise ValueError("sources.json must contain a JSON list.")

    required_fields = {
        "filename",
        "title",
        "source",
        "url",
    }

    for index, entry in enumerate(metadata):
        if not isinstance(entry, dict):
            raise ValueError(
                f"Metadata entry at index {index} must be a JSON object."
            )

        missing_fields = required_fields - entry.keys()

        if missing_fields:
            raise ValueError(
                f"Metadata entry at index {index} is missing fields: "
                f"{', '.join(sorted(missing_fields))}"
            )

        for field in required_fields:
            if not isinstance(entry[field], str) or not entry[field].strip():
                raise ValueError(
                    f"Metadata field '{field}' at index {index} "
                    "must be a non-empty string."
                )

    return metadata


SUPPORTED_EXTENSIONS = {".html", ".htm", ".txt"}


def discover_documents() -> list[Path]:
    """Find supported medical documents in the documents directory."""
    if not DOCUMENTS_DIR.exists():
        raise FileNotFoundError(
            f"Medical documents directory not found: {DOCUMENTS_DIR}"
        )

    return sorted(
        path
        for path in DOCUMENTS_DIR.iterdir()
        if path.is_file()
        and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )



def load_documents_metadata() -> list[dict]:
    """Match discovered files with metadata, generating safe defaults if absent."""
    metadata_entries = load_source_metadata()

    metadata_by_filename = {
        entry["filename"]: entry
        for entry in metadata_entries
    }

    matched_documents = []

    for path in discover_documents():
        metadata = metadata_by_filename.get(path.name)

        if metadata is None:
            # Generate descriptive defaults without inventing provenance.
            title = path.stem.replace("_", " ").replace("-", " ").title()

            metadata = {
                "filename": path.name,
                "title": title,
                "source": "Unknown — verify source",
                "url": "",
                "document_type": path.suffix.lower().lstrip("."),
                "metadata_generated": True,
            }
        else:
            metadata = {
                **metadata,
                "metadata_generated": False,
            }

        matched_documents.append({
            **metadata,
            "path": path,
        })

    return matched_documents



def extract_txt_text(path: Path) -> str:
    """Extract readable text from a plain-text document."""
    return path.read_text(encoding="utf-8").strip()


def load_document(path: Path) -> str:
    """Extract text from a supported medical document."""
    extension = path.suffix.lower()

    if extension in {".html", ".htm"}:
        html = path.read_text(encoding="utf-8")
        return extract_html_text(html)

    if extension == ".txt":
        return extract_txt_text(path)

    raise ValueError(
        f"Unsupported document format: {extension}"
    )


def load_all_documents() -> list[dict]:
    """Load all discovered documents with their text and metadata."""
    document_records = load_documents_metadata()
    loaded_documents = []

    for record in document_records:
        text = load_document(record["path"])

        if not text.strip():
            raise ValueError(
                f"Document contains no extractable text: "
                f"{record['filename']}"
            )

        loaded_documents.append({
            **record,
            "text": text,
        })

    return loaded_documents

