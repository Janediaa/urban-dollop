from pathlib import Path

import pymupdf


PROJECT_ROOT = Path(__file__).resolve().parent.parent
PDF_PATH = (
    PROJECT_ROOT
    / "data"
    / "medical_documents"
    / "who_hypertension.pdf"
)


def main() -> None:
    if not PDF_PATH.is_file():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    total_characters = 0

    with pymupdf.open(PDF_PATH) as document:
        print(f"Pages: {len(document)}")

        for page_number, page in enumerate(document, start=1):
            text = page.get_text().strip()
            character_count = len(text)
            total_characters += character_count

            print(
                f"Page {page_number}: "
                f"{character_count} extracted characters"
            )

    print(f"Total extracted characters: {total_characters}")

    if total_characters == 0:
        print("No text layer detected. OCR or an HTML source is needed.")
    else:
        print("Text extraction is available.")


if __name__ == "__main__":
    main()