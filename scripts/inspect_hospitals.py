
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATASET_PATH = PROJECT_ROOT / "data" / "processed" / "healthcare_professionals_clean.csv"


def main() -> None:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET_PATH}\n"
            "Update DATASET_PATH to the actual CSV location."
        )

    df = pd.read_csv(DATASET_PATH)

    required_columns = {"hospital", "city"}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            f"Missing required columns: {sorted(missing_columns)}"
        )

    # 1. Number of missing hospital values
    missing_count = df["hospital"].isna().sum()
    print(f"Missing hospital values: {missing_count}")

    # Exclude rows with missing hospital names
    valid_hospitals = df.loc[df["hospital"].notna()]

    # 2. Number of distinct non-missing hospital names
    distinct_count = valid_hospitals["hospital"].nunique()
    print(f"\nDistinct non-missing hospital names: {distinct_count}")

    # 3. Twenty most frequent hospital names and their counts
    print("\nTop 20 most frequent hospital names:")
    print(
        valid_hospitals["hospital"]
        .value_counts()
        .head(20)
        .to_string()
    )

    # 4. Distinct (hospital, city) pairs, excluding missing hospitals
    hospital_city_pairs = (
        valid_hospitals[["hospital", "city"]]
        .drop_duplicates()
        .sort_values(
            by=["hospital", "city"],
            na_position="last",
        )
        .reset_index(drop=True)
    )

    print("\nDistinct (hospital, city) pairs:")
    print(hospital_city_pairs.to_string(index=False))

    print(f"\nTotal distinct hospital-city pairs: {len(hospital_city_pairs)}")


if __name__ == "__main__":
    main()
