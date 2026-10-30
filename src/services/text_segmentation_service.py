
"""Sentence segmentation for patient symptom descriptions."""

import re


def split_sentences(text: str) -> list[str]:
    """Split patient text into non-empty sentence segments."""

    if not text or not text.strip():
        return []

    segments = re.split(
        r"(?<=[.!?])\s+|\n+",
        text.strip(),
    )

    return [
        segment.strip()
        for segment in segments
        if segment.strip()
    ]
