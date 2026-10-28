from pydoc import text

import pytest
import re
from src.services.text_chunker import (
    chunk_text,
    split_into_paragraphs,
    split_into_sentences,
    _join_paragraphs,
    _group_paragraphs,
    _group_sentences,
    _chunk_paragraph,
)


def test_chunk_text_rejects_negative_chunk_size():
    with pytest.raises(ValueError, match="chunk_size must be positive"):
        chunk_text("Some medical information", chunk_size=-10)

def test_chunk_text_returns_short_text_as_one_chunk():
    text = "Hypertension is a medical condition."

    assert chunk_text(text, chunk_size=100, overlap=0) == [text]


def test_chunk_text_chunks_overlap_correctly():
    text = (
        "Alpha sentence. Bravo sentence. "
        "Charlie sentence. Delta sentence."
    )

    result = chunk_text(text, chunk_size=35, overlap=15)

    assert len(result) > 1
    assert result[0] == "Alpha sentence."
    assert result[1] == "Alpha sentence. Bravo sentence."
    assert result[2] == "Bravo sentence. Charlie sentence."
    assert result[3] == "Charlie sentence. Delta sentence."


def test_chunk_text_returns_empty_list_for_empty_text():
    assert chunk_text("") == []


def test_chunk_text_rejects_overlap_equal_to_chunk_size():
    with pytest.raises(
        ValueError,
        match="overlap must be smaller than chunk_size",
    ):
        chunk_text("ABCDE", chunk_size=5, overlap=5)


def test_chunk_text_rejects_non_string_input():
    with pytest.raises(TypeError, match="text must be a string"):
        chunk_text(None)


def test_chunk_text_rejects_boolean_chunk_size():
    with pytest.raises(TypeError, match="chunk_size must be an integer"):
        chunk_text("Some text", chunk_size=True)

def test_chunk_text_rejects_boolean_overlap():
    with pytest.raises(TypeError, match="overlap must be an integer"):
        chunk_text("Some text", chunk_size=10, overlap=True)

def test_chunk_text_returns_short_final_chunk():
    result = chunk_text("ABCDEFGHI", chunk_size=5, overlap=1)

    assert result == ["ABCDE", "EFGHI"]

@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "First paragraph.\n\nSecond paragraph.\n\nThird paragraph.",
            [
                "First paragraph.",
                "Second paragraph.",
                "Third paragraph.",
            ],
        ),
        (
            "First paragraph.\n\n\n\nSecond paragraph.\n\n\nThird paragraph.",
            ["First paragraph.", "Second paragraph.", "Third paragraph."],
        ),
        (
            "   First paragraph.   \n\n   Second paragraph.   ",
            ["First paragraph.", "Second paragraph."],
        ),
        ("", []),
        ("   \n\t\n   ", []),
        ("A single paragraph with no separator.", [
            "A single paragraph with no separator."
        ]),
        (
            "First line of paragraph.\nSecond line of paragraph.",
            ["First line of paragraph.\nSecond line of paragraph."],
        ),
        (
            "\r\nFirst paragraph.\r\n\r\nSecond paragraph.\r\n",
            ["First paragraph.", "Second paragraph."],
        ),
    ],
)
def test_split_into_paragraphs(text, expected):
    assert split_into_paragraphs(text) == expected


def test_split_into_paragraphs_rejects_non_string_input():
    with pytest.raises(TypeError, match="text must be a string"):
        split_into_paragraphs(None)

@pytest.mark.parametrize(
    ("paragraph", "expected"),
    [
        (
            "First sentence. Second sentence! Is this the third?",
            [
                "First sentence.",
                "Second sentence!",
                "Is this the third?",
            ],
        ),
        (
            "Dr. Sharma treats patients. Mr. Kumar visits him.",
            [
                "Dr. Sharma treats patients.",
                "Mr. Kumar visits him.",
            ],
        ),
        (
            "The reading was 120.5 mmHg. It was high.",
            [
                "The reading was 120.5 mmHg.",
                "It was high.",
            ],
        ),
        (
            "For example, use a healthy diet, etc. This may help.",
            [
                "For example, use a healthy diet, etc.",
                "This may help.",
            ],
        ),
        ("One complete sentence.", ["One complete sentence."]),
        ("", []),
        ("   \t ", []),
        (
            "First sentence.\nSecond sentence.",
            ["First sentence.", "Second sentence."],
        ),
    ],
)
def test_split_into_sentences(paragraph, expected):
    assert split_into_sentences(paragraph) == expected


def test_split_into_sentences_rejects_non_string_input():
    with pytest.raises(TypeError, match="paragraph must be a string"):
        split_into_sentences(None)

@pytest.mark.parametrize(
    "paragraph",
    [
        "Dr. Sharma treats patients. He works at the hospital.",
        "Blood pressure was 120.5 mmHg. It remained elevated.",
        "Use e.g. a healthy diet. Exercise regularly.",
        "The WHO recommends prevention. Follow local guidance.",
        "First sentence.\nSecond sentence.",
    ],
)
def test_split_into_sentences_preserves_text(paragraph):
    sentences = split_into_sentences(paragraph)

    reconstructed = " ".join(sentences)
    normalized_original = re.sub(r"\s+", " ", paragraph.strip())

    assert reconstructed == normalized_original


def test_paragraph_and_sentence_splitting_regressions():
    assert split_into_paragraphs("First.\n\nSecond.") == [
        "First.",
        "Second.",
    ]

    assert split_into_sentences(
        "The reading was 120.5 mmHg. It was high."
    ) == [
        "The reading was 120.5 mmHg.",
        "It was high.",
    ]


def test_join_paragraphs_joins_with_blank_line():
    assert _join_paragraphs(
        ["First paragraph.", "Second paragraph."]
    ) == "First paragraph.\n\nSecond paragraph."


def test_join_paragraphs_returns_empty_string_for_empty_list():
    assert _join_paragraphs([]) == ""


def test_join_paragraphs_returns_single_paragraph_unchanged():
    assert _join_paragraphs(["One paragraph."]) == "One paragraph."


def test_group_paragraphs_returns_empty_list_for_empty_input():
    assert _group_paragraphs([], chunk_size=50) == []


def test_group_paragraphs_returns_single_paragraph_as_one_chunk():
    assert _group_paragraphs(
        ["First paragraph."],
        chunk_size=50,
    ) == ["First paragraph."]


def test_group_paragraphs_combines_paragraphs_that_fit():
    assert _group_paragraphs(
        ["First.", "Second."],
        chunk_size=15,
    ) == ["First.\n\nSecond."]


def test_group_paragraphs_separates_paragraphs_that_exceed_size():
    assert _group_paragraphs(
        ["First.", "Second."],
        chunk_size=14,
    ) == ["First.", "Second."]


def test_group_paragraphs_preserves_oversized_paragraph():
    paragraph = "This paragraph is longer than ten characters."

    assert _group_paragraphs(
        [paragraph],
        chunk_size=10,
    ) == [paragraph]


def test_group_paragraphs_preserves_paragraph_order():
    paragraphs = ["Alpha.", "Bravo.", "Charlie."]

    result = _group_paragraphs(paragraphs, chunk_size=8)

    assert result == paragraphs


def test_group_sentences_returns_empty_list_for_empty_input():
    assert _group_sentences([], chunk_size=25) == []


def test_group_sentences_returns_one_sentence_as_one_chunk():
    assert _group_sentences(
        ["Hello world."],
        chunk_size=25,
    ) == ["Hello world."]


def test_group_sentences_combines_sentences_that_fit():
    assert _group_sentences(
        ["Hello world.", "Goodbye world."],
        chunk_size=30,
    ) == ["Hello world. Goodbye world."]


def test_group_sentences_separates_sentences_that_exceed_size():
    assert _group_sentences(
        ["Hello world.", "Goodbye world."],
        chunk_size=20,
    ) == ["Hello world.", "Goodbye world."]


def test_group_sentences_preserves_oversized_sentence():
    sentence = "This sentence is much too long."

    assert _group_sentences(
        [sentence],
        chunk_size=10,
    ) == [sentence]


def test_group_sentences_preserves_sentence_order():
    sentences = ["Alpha.", "Bravo.", "Charlie."]

    result = _group_sentences(sentences, chunk_size=20)

    assert result == ["Alpha. Bravo.", "Charlie."]


def test_chunk_paragraph_keeps_short_paragraph_intact():
    paragraph = "First sentence. Second sentence."

    assert _chunk_paragraph(
        paragraph,
        chunk_size=50,
    ) == [paragraph]


def test_chunk_paragraph_splits_at_sentence_boundaries():
    paragraph = "First sentence. Second sentence."

    assert _chunk_paragraph(
        paragraph,
        chunk_size=30,
    ) == ["First sentence.", "Second sentence."]


def test_chunk_paragraph_preserves_oversized_sentence():
    sentence = "This sentence is much too long."

    assert _chunk_paragraph(
        sentence,
        chunk_size=10,
    ) == [sentence]


def test_chunk_paragraph_preserves_sentence_order():
    paragraph = "Alpha sentence. Bravo sentence. Charlie sentence."

    result = _chunk_paragraph(paragraph, chunk_size=25)

    assert result == [
        "Alpha sentence.",
        "Bravo sentence.",
        "Charlie sentence.",
    ]


def test_chunk_paragraph_returns_empty_list_for_empty_input():
    assert _chunk_paragraph("", chunk_size=30) == []


def test_chunk_text_combines_short_paragraphs():
    text = "First.\n\nSecond."

    assert chunk_text(
        text,
        chunk_size=20,
        overlap=0,
    ) == ["First.\n\nSecond."]


def test_chunk_text_separates_paragraphs_when_combined_size_exceeds_target():
    text = "First paragraph.\n\nSecond paragraph."

    assert chunk_text(
        text,
        chunk_size=20,
        overlap=0,
    ) == ["First paragraph.", "Second paragraph."]


def test_chunk_text_splits_oversized_paragraph_at_sentence_boundaries():
    text = "First sentence. Second sentence."

    assert chunk_text(
        text,
        chunk_size=20,
        overlap=0,
    ) == ["First sentence.", "Second sentence."]



def test_chunk_text_preserves_oversized_sentence():
    sentence = "This sentence is much too long."

    assert chunk_text(
        sentence,
        chunk_size=10,
        overlap=0,
    ) == [sentence]


def test_chunk_text_handles_exact_chunk_boundary():
    text = "ABCDEF"

    assert chunk_text(
        text,
        chunk_size=3,
        overlap=0,
    ) == ["ABC", "DEF"]

def test_chunk_text_returns_short_final_chunk():
    text = "ABCDEFGHI"

    assert chunk_text(
        text,
        chunk_size=5,
        overlap=1,
    ) == [text]


def test_chunk_text_repeats_previous_sentence_as_overlap():
    text = (
        "Alpha sentence. Bravo sentence. "
        "Charlie sentence. Delta sentence."
    )

    chunks = chunk_text(text, chunk_size=35, overlap=15)

    assert len(chunks) > 1
    assert any(
        sentence in chunks[index]
        for index in range(1, len(chunks))
        for sentence in split_into_sentences(chunks[index - 1])
        if len(sentence) <= 15
    )


def test_chunk_text_zero_overlap_does_not_duplicate_context():
    text = "First sentence. Second sentence. Third sentence."

    chunks = chunk_text(text, chunk_size=25, overlap=0)

    assert chunks == [
        "First sentence.",
        "Second sentence.",
        "Third sentence.",
    ]
