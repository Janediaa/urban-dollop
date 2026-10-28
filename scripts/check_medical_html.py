
from pathlib import Path

from bs4 import BeautifulSoup


PROJECT_ROOT = Path(__file__).resolve().parent.parent

HTML_PATH = (
    PROJECT_ROOT
    / "data"
    / "medical_documents"
    / "who_hypertension.html"
)


def extract_article_text(html: str) -> str:
    """Extract readable article text from a saved HTML page."""
    soup = BeautifulSoup(html, "html.parser")

    # Remove elements that aren't useful medical content.
    for element in soup.select(
        "script, style, noscript, nav, footer, header"
    ):
        element.decompose()

    # Prefer the main content area, then fall back if unavailable.
    content = soup.find("main") or soup.find("article")

    if content is None:
        content = soup.body or soup

    # Preserve paragraph and heading boundaries.
    for element in content.find_all(
        ["p", "h1", "h2", "h3", "li"]
    ):
        element.insert_before("\n")

    extracted_text = content.get_text(separator="\n", strip=True)

    # Normalize whitespace while retaining separate content blocks.
    lines = [
        " ".join(line.split())
        for line in extracted_text.splitlines()
        if line.strip()
    ]

    return "\n".join(lines)


def main() -> None:
    if not HTML_PATH.is_file():
        raise FileNotFoundError(
            f"HTML file not found: {HTML_PATH}\n"
            "Check the filename and extension."
        )

    html = HTML_PATH.read_text(encoding="utf-8", errors="replace")
    extracted_text = extract_article_text(html)
    character_count = len(extracted_text)

    print(f"HTML file: {HTML_PATH.name}")
    print(f"HTML file size: {len(html)} characters")
    print(f"Extracted text: {character_count} characters")

    if character_count == 0:
        print("RESULT: No text extracted. Try another source.")
        return

    print("\n--- Extracted text preview (first 1500 characters) ---")
    print(extracted_text[:1500])

    print("\n--- Article-content checks ---")

    for phrase in (
        "Key facts",
        "Risk factors",
        "Symptoms",
        "Treatment",
        "Prevention",
        "Complications of uncontrolled hypertension",
    ):
        found = phrase.casefold() in extracted_text.casefold()
        print(f"{phrase}: {found}")

    article_start = extracted_text.casefold().find("key facts".casefold())

    if article_start >= 0:
        print("\n--- Preview starting at 'Key facts' ---")
        print(extracted_text[article_start:article_start + 2500])
    else:
        print("\nCould not find the article's 'Key facts' section.")

    if character_count < 500:
        print("\nRESULT: Very little text extracted; inspect the output.")
    elif all(
        phrase.casefold() in extracted_text.casefold()
        for phrase in ("Key facts", "Risk factors", "Symptoms")
    ):
        print("\nRESULT: Article extraction looks promising.")
    else:
        print("\nRESULT: Text was extracted, but article content needs review.")


if __name__ == "__main__":
    main()
