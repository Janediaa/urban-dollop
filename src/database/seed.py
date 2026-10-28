import sqlite3
from pathlib import Path

import pandas as pd


REQUIRED_COLUMNS = {
    "doctor_name",
    "doctor_type",
    "experience_years",
    "location",
    "hospital",
    "fees",
    "city",
    "composite_doctor_id",
}



def load_doctors_csv(csv_path: str | Path) -> pd.DataFrame:
    """
    Load the doctors' data from a CSV file and validate the required columns.

    Args:
        csv_path (str | Path): Path to the CSV file containing the doctors' data.
    
    Raises:
        ValueError: If the CSV file is missing required columns.

    Returns:
        pd.DataFrame: A pandas DataFrame containing the doctors' data.
    """
    csv_path = Path(csv_path)

    if not csv_path.is_file():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")
    
    df = pd.read_csv(csv_path)

    missing_columns = REQUIRED_COLUMNS - set(df.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Missing required columns in CSV: {missing}")
    return df



def insert_hospitals(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
) -> dict[tuple[str, str], int]:
    """Insert unique hospitals and return their IDs keyed by (name, city)."""

    hospitals = df[["hospital", "city"]].copy()

    hospitals["hospital"] = hospitals["hospital"].map(normalize_text)
    hospitals["city"] = hospitals["city"].map(normalize_text)

    hospitals = hospitals.dropna(subset=["hospital", "city"]).drop_duplicates()

    conn.executemany(
        """
        INSERT OR IGNORE INTO hospitals (hospital_name, city)
        VALUES (?, ?)
        """,
        hospitals[["hospital", "city"]].itertuples(
            index=False, name=None
        ),
    )

    rows = conn.execute(
        "SELECT hospital_id, hospital_name, city FROM hospitals"
    ).fetchall()

    return {
        (hospital_name, city): hospital_id
        for hospital_id, hospital_name, city in rows
    }

def normalize_text(value):
    """Normalize a non-missing text value for matching and storage."""
    if pd.isna(value):
        return None

    normalized = str(value).strip().lower()
    return normalized if normalized else None

def insert_doctors(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    hospital_ids: dict[tuple[str, str], int],
) -> int:
    """Insert doctors and link them to hospitals when a match exists."""

    def clean_value(value):
        return None if pd.isna(value) else value

    doctors = []

    for _, row in df.iterrows():
        hospital = normalize_text(row["hospital"])
        city = normalize_text(row["city"])

        hospital_id = None

        if hospital is not None and city is not None:
            hospital_key = (hospital, city)
            if hospital_key not in hospital_ids:
                raise ValueError(
                    f"Hospital mapping not found for {hospital!r} in {city!r}"
                )
            hospital_id = hospital_ids[hospital_key]

        doctors.append((
            clean_value(row["composite_doctor_id"]),
            clean_value(row["doctor_name"]),
            clean_value(row["doctor_type"]),
            clean_value(row["experience_years"]),
            clean_value(row["location"]),
            clean_value(row["fees"]),
            city,
            hospital_id,
        ))

    cursor = conn.executemany(
        """
        INSERT INTO doctors (
            composite_doctor_id,
            doctor_name,
            doctor_type,
            experience_years,
            location,
            fees,
            city,
            hospital_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        doctors,
    )

    return cursor.rowcount


def seed_database(
    conn: sqlite3.Connection,
    csv_path: str | Path,
) -> dict[str, int]:
    """Import doctors and hospitals in a single transaction."""

    df = load_doctors_csv(csv_path)

    with conn:
        hospital_ids = insert_hospitals(conn, df)
        insert_doctors(conn, df, hospital_ids)

        hospital_count = conn.execute(
            "SELECT COUNT(*) FROM hospitals"
        ).fetchone()[0]

        doctor_count = conn.execute(
            "SELECT COUNT(*) FROM doctors"
        ).fetchone()[0]

    return {
        "hospitals": hospital_count,
        "doctors": doctor_count,
    }