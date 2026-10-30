
import pytest

from src.services.text_segmentation_service import split_sentences


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "I have a headache. I feel dizzy.",
            ["I have a headache.", "I feel dizzy."],
        ),
        (
            "I have a fever! My cough is getting worse.",
            ["I have a fever!", "My cough is getting worse."],
        ),
        (
            "I have a headache\nI also feel tired",
            ["I have a headache", "I also feel tired"],
        ),
        ("", []),
        ("   ", []),
    ],
)
def test_split_sentences(text, expected):
    assert split_sentences(text) == expected
