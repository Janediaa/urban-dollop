from pathlib import Path
import pandas as pd

DATA_PATH = Path("data/processed/healthcare_professionals_clean.csv")

def main() -> None:
    df = pd.read_csv(DATA_PATH)

    print("Dataset shape:", df.shape)
    print("\nColumn names:")
    print(df.columns.tolist())

    print("\nData types:")
    print(df.dtypes)

    print("\nMissing values:")
    print(df.isna().sum())

    print("\nSample records:")
    print(df.head(5).to_string(index=False))


if __name__ == "__main__":
    main()