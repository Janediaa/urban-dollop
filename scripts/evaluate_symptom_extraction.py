
"""Evaluate symptom concept extraction against a labelled JSON dataset."""


import json
from collections import defaultdict
from pathlib import Path

from src.services.embedding_service import load_embedding_model
from src.services.symptom_extraction_service import SymptomExtractionService
from src.services.symptom_vocabulary import SYMPTOM_VOCABULARY


ROOT_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = ROOT_DIR / "data" / "evaluation" / "symptom_test_cases.json"


def calculate_metrics(true_positives, false_positives, false_negatives):
    precision = (
        true_positives / (true_positives + false_positives)
        if true_positives + false_positives
        else 0.0
    )

    recall = (
        true_positives / (true_positives + false_negatives)
        if true_positives + false_negatives
        else 0.0
    )

    f1 = (
        2 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )

    return precision, recall, f1


def validate_dataset(cases):
    seen_ids = set()
    valid_symptoms = set(SYMPTOM_VOCABULARY)

    for case in cases:
        required_fields = {
            "id",
            "text",
            "expected_symptoms",
            "category",
        }

        if not required_fields.issubset(case):
            raise ValueError(
                f"Missing fields in case: {case}"
            )

        case_id = case["id"]

        if case_id in seen_ids:
            raise ValueError(f"Duplicate ID: {case_id}")

        seen_ids.add(case_id)

        unknown_symptoms = (
            set(case["expected_symptoms"]) - valid_symptoms
        )

        if unknown_symptoms:
            raise ValueError(
                f"{case_id} contains unknown symptoms: "
                f"{sorted(unknown_symptoms)}"
            )


def main():
    with DATASET_PATH.open(encoding="utf-8") as file:
        cases = json.load(file)

    validate_dataset(cases)

    print(f"Loaded {len(cases)} evaluation cases.")
    print("Loading embedding model...")

    model = load_embedding_model()
    service = SymptomExtractionService(model=model)

    print("Model loaded. Running evaluation...\n")

    total_tp = 0
    total_fp = 0
    total_fn = 0

    category_counts = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )

    symptom_counts = defaultdict(
        lambda: {"tp": 0, "fp": 0, "fn": 0}
    )

    errors = []

    for case in cases:
        case_id = case["id"]
        text = case["text"]
        category = case["category"]

        expected = set(case["expected_symptoms"])
        predicted = set(service.extract_concepts(text))

        true_positives = expected & predicted
        false_positives = predicted - expected
        false_negatives = expected - predicted

        tp = len(true_positives)
        fp = len(false_positives)
        fn = len(false_negatives)

        total_tp += tp
        total_fp += fp
        total_fn += fn

        category_counts[category]["tp"] += tp
        category_counts[category]["fp"] += fp
        category_counts[category]["fn"] += fn

        for symptom in expected | predicted:
            if symptom in true_positives:
                symptom_counts[symptom]["tp"] += 1
            elif symptom in false_positives:
                symptom_counts[symptom]["fp"] += 1
            elif symptom in false_negatives:
                symptom_counts[symptom]["fn"] += 1

        if false_positives or false_negatives:
            semantic_scores = service._semantic_scores(text)

            top_scores = sorted(
                semantic_scores.items(),
                key=lambda item: item[1],
                reverse=True,
            )[:5]

            errors.append({
                "id": case_id,
                "text": text,
                "expected": sorted(expected),
                "predicted": sorted(predicted),
                "false_positives": sorted(false_positives),
                "false_negatives": sorted(false_negatives),
                "fuzzy_matches": sorted(service._fuzzy_match(text)),
                "top_semantic_scores": top_scores,
            })
    precision, recall, f1 = calculate_metrics(
        total_tp,
        total_fp,
        total_fn,
    )

    print("=" * 65)
    print("OVERALL SYMPTOM EXTRACTION RESULTS")
    print("=" * 65)

    print(f"Total cases:       {len(cases)}")
    print(f"True positives:    {total_tp}")
    print(f"False positives:   {total_fp}")
    print(f"False negatives:   {total_fn}")
    print(f"Precision:         {precision:.4f}")
    print(f"Recall:            {recall:.4f}")
    print(f"F1 score:          {f1:.4f}")

    print("\n" + "=" * 65)
    print("CATEGORY-WISE RESULTS")
    print("=" * 65)

    for category in sorted(category_counts):
        counts = category_counts[category]

        p, r, f = calculate_metrics(
            counts["tp"],
            counts["fp"],
            counts["fn"],
        )

        print(
            f"{category:20} "
            f"P={p:.3f} "
            f"R={r:.3f} "
            f"F1={f:.3f} "
            f"TP={counts['tp']} "
            f"FP={counts['fp']} "
            f"FN={counts['fn']}"
        )

    print("\n" + "=" * 65)
    print("PER-SYMPTOM RESULTS")
    print("=" * 65)

    for symptom in sorted(symptom_counts):
        counts = symptom_counts[symptom]

        p, r, f = calculate_metrics(
            counts["tp"],
            counts["fp"],
            counts["fn"],
        )

        print(
            f"{symptom:22} "
            f"P={p:.3f} "
            f"R={r:.3f} "
            f"F1={f:.3f}"
        )

    print("\n" + "=" * 65)
    print(f"INCORRECT PREDICTIONS ({len(errors)} cases)")
    print("=" * 65)

    for error in errors:
        print(f"\n[{error['id']}] {error['text']}")
        print(f"  Expected: {error['expected']}")
        print(f"  Predicted: {error['predicted']}")
        print(f"  False positives: {error['false_positives']}")
        print(f"  False negatives: {error['false_negatives']}")
        print(f"  Fuzzy matches: {error['fuzzy_matches']}")
        print(f"  Top semantic scores: {error['top_semantic_scores']}")

    print("\nEvaluation completed.")


if __name__ == "__main__":
    main()
