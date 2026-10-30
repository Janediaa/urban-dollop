from src.services.symptom_vocabulary import SYMPTOM_VOCABULARY


def test_vocabulary_contains_expected_symptoms():
    expected = {
        "fever",
        "cough",
        "headache",
        "fatigue",
        "dizziness",
        "nausea",
    }

    assert expected.issubset(SYMPTOM_VOCABULARY)


def test_every_symptom_has_aliases_and_examples():
    for symptom, definition in SYMPTOM_VOCABULARY.items():
        assert definition["aliases"], symptom
        assert definition["semantic_examples"], symptom


def test_aliases_are_unique_within_each_symptom():
    for symptom, definition in SYMPTOM_VOCABULARY.items():
        aliases = definition["aliases"]

        assert len(aliases) == len(set(aliases)), symptom