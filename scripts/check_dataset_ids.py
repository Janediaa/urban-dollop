
from pathlib import Path

import pandas as pd


# Resolve paths relative to the project root.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "healthcare_professionals_clean.csv"


def main() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Cleaned dataset not found: {DATASET_PATH}\n"
            "Update DATASET_PATH to match your actual CSV location."
        )

    df = pd.read_csv(DATASET_PATH)

    id_column = "composite_doctor_id"

    if id_column not in df.columns:
        raise ValueError(
            f"Required column '{id_column}' not found. "
            f"Available columns: {list(df.columns)}"
        )

    # Exclude missing IDs from uniqueness and duplicate calculations.
    valid_ids = df[id_column].dropna()
    duplicated_mask = valid_ids.duplicated(keep="first")

    unique_ids = valid_ids.nunique()
    extra_duplicate_occurrences = int(duplicated_mask.sum())

    # Identify every ID that appears more than once.
    duplicate_id_mask = df[id_column].duplicated(keep=False) & df[id_column].notna()
    duplicate_records = df.loc[duplicate_id_mask].sort_values(
        by=id_column,
        kind="stable",
    )

    print(f"Total number of rows: {len(df)}")
    print(f"Unique {id_column} values: {unique_ids}")
    print(
        "Duplicated ID occurrences (extra occurrences only): "
        f"{extra_duplicate_occurrences}"
    )

    print("\nActual duplicated IDs:")
    if duplicate_records.empty:
        print("No duplicated IDs found.")
    else:
        print(duplicate_records[id_column].drop_duplicates().to_list())

        print("\nAssociated doctor records:")
        print(duplicate_records.to_string(index=False))


if __name__ == "__main__":
    main()
