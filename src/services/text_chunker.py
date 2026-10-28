"""Split extracted medical documents into overlapping text chunks."""

import re


def _join_paragraphs(paragraphs: list[str]) -> str:
    """Join paragraphs with a blank line between them."""
    return "\n\n".join(paragraphs)


def _group_paragraphs(
    paragraphs: list[str],
    chunk_size: int,
) -> list[str]:
    """Group paragraphs into chunks near the target size."""
    chunks = []
    current_group = []

    for paragraph in paragraphs:
        if not current_group:
            current_group.append(paragraph)
            continue

        candidate = _join_paragraphs(current_group + [paragraph])

        if len(candidate) <= chunk_size:
            current_group.append(paragraph)
        else:
            chunks.append(_join_paragraphs(current_group))
            current_group = [paragraph]

    if current_group:
        chunks.append(_join_paragraphs(current_group))

    return chunks




def _group_sentences(
    sentences: list[str],
    chunk_size: int,
) -> list[str]:
    """Group sentences into chunks near the target size."""
    chunks = []
    current_group = []

    for sentence in sentences:
        if not current_group:
            current_group.append(sentence)
            continue

        candidate = " ".join(current_group + [sentence])

        if len(candidate) <= chunk_size:
            current_group.append(sentence)
        else:
            chunks.append(" ".join(current_group))
            current_group = [sentence]

    if current_group:
        chunks.append(" ".join(current_group))

    return chunks



def _chunk_paragraph(
    paragraph: str,
    chunk_size: int,
) -> list[str]:
    """Split a paragraph into chunks without breaking sentences unnecessarily."""
    if not paragraph:
        return []

    if len(paragraph) <= chunk_size:
        return [paragraph]

    sentences = split_into_sentences(paragraph)
    return _group_sentences(sentences, chunk_size)


def _apply_sentence_overlap(
    chunks: list[str],
    overlap: int,
) -> list[str]:
    """Add sentence-boundary-aware overlap to consecutive chunks."""
    if overlap == 0 or len(chunks) < 2:
        return chunks

    result = [chunks[0]]

    for index in range(1, len(chunks)):
        previous_sentences = split_into_sentences(chunks[index - 1])
        overlap_sentences = []
        overlap_length = 0

        for sentence in reversed(previous_sentences):
            separator_length = 1 if overlap_sentences else 0
            candidate_length = (
                overlap_length + separator_length + len(sentence)
            )

            if candidate_length > overlap:
                if not overlap_sentences:
                    overlap_sentences.append(sentence)
                break

            overlap_sentences.insert(0, sentence)
            overlap_length = candidate_length

        if overlap_sentences:
            prefix = " ".join(overlap_sentences)
            result.append(f"{prefix} {chunks[index]}")
        else:
            result.append(chunks[index])

    return result




def chunk_text(
    text: str,
    chunk_size: int = 800,
    overlap: int = 120,
) -> list[str]:
    """Split text into sentence-aware chunks with overlapping context."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool):
        raise TypeError("chunk_size must be an integer")

    if not isinstance(overlap, int) or isinstance(overlap, bool):
        raise TypeError("overlap must be an integer")

    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive")

    if overlap < 0:
        raise ValueError("overlap cannot be negative")

    if overlap >= chunk_size:
        raise ValueError("overlap must be smaller than chunk_size")
    


    
    text = text.strip()
    if not text:
        return []

    # Preserve existing behavior for short inputs, but split
    # substantially longer strings that contain no whitespace.
    if len(text) <= chunk_size:
        return [text]

    if not any(character.isspace() for character in text):
        if overlap == 0:
            return [
                text[start:start + chunk_size]
                for start in range(0, len(text), chunk_size)
            ]

    # Reserve space for context carried over from the previous chunk.
    content_size = chunk_size - overlap

    paragraphs = split_into_paragraphs(text)
    chunks = []
    pending_paragraphs = []

    for paragraph in paragraphs:
        if len(paragraph) > content_size:
            if pending_paragraphs:
                chunks.extend(
                    _group_paragraphs(pending_paragraphs, content_size)
                )
                pending_paragraphs = []

            chunks.extend(_chunk_paragraph(paragraph, content_size))
        else:
            candidate = _join_paragraphs(
                pending_paragraphs + [paragraph]
            )

            if len(candidate) <= content_size:
                pending_paragraphs.append(paragraph)
            else:
                if pending_paragraphs:
                    chunks.append(_join_paragraphs(pending_paragraphs))
                pending_paragraphs = [paragraph]

    if pending_paragraphs:
        chunks.append(_join_paragraphs(pending_paragraphs))

    return _apply_sentence_overlap(chunks, overlap)


def split_into_paragraphs(text: str) -> list[str]:
    """Split text into non-empty paragraphs."""
    if not isinstance(text, str):
        raise TypeError("text must be a string")

    paragraphs = re.split(r"\n\s*\n", text.strip())

    return [
        paragraph.strip()
        for paragraph in paragraphs
        if paragraph.strip()
    ]

def split_into_sentences(paragraph: str) -> list[str]:
    """Split a paragraph into sentences."""
    if not isinstance(paragraph, str):
        raise TypeError("paragraph must be a string")

    paragraph = paragraph.strip()
    if not paragraph:
        return []

    abbreviations = [
        "Mr.", "Mrs.", "Ms.", "Dr.", "Prof.", "Sr.", "Jr.",
        "vs.", "e.g.", "i.e.", "Fig.", "No.", "St.",
        "U.S.", "a.m.", "p.m.",
    ]

    # Protect abbreviation periods temporarily.
    protected = paragraph
    placeholder_map = {}

    for index, abbreviation in enumerate(
        sorted(abbreviations, key=len, reverse=True)
    ):
        placeholder = f"ABBREVPLACEHOLDER{index}TOKEN"
        pattern = re.escape(abbreviation)

        protected, count = re.subn(
            pattern,
            lambda match, p=placeholder: match.group().replace(".", p),
            protected,
            flags=re.IGNORECASE,
        )

        if count:
            placeholder_map[placeholder] = "."

    # Protect decimal points, such as 120.5.
    protected = re.sub(
        r"(?<=\d)\.(?=\d)",
        "DECIMALPOINTTOKEN",
        protected,
    )

    # Split on sentence-ending punctuation followed by whitespace.
    parts = re.split(r"(?<=[.!?])\s+", protected)

    sentences = []

    for part in parts:
        sentence = part.strip()

        if not sentence:
            continue

        # Restore punctuation in each sentence.
        sentence = sentence.replace("DECIMALPOINTTOKEN", ".")

        for placeholder, original in placeholder_map.items():
            sentence = sentence.replace(placeholder, original)

        sentences.append(sentence)

    return sentences