import sys
from pathlib import Path

# Add the project root so the script can import the src package.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import get_connection
from src.database.models import create_tables
from src.database.seed import seed_database


CSV_PATH = (
    PROJECT_ROOT
    / "data"
    / "processed"
    / "healthcare_professionals_clean.csv"
)

DB_PATH = PROJECT_ROOT / "data" / "healthcare.db"


def main() -> None:
    if not CSV_PATH.is_file():
        raise FileNotFoundError(f"Dataset not found: {CSV_PATH}")

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    conn = None
    try:
        conn = get_connection(DB_PATH)
        create_tables(conn)

        counts = seed_database(conn, CSV_PATH)

        print("Database initialized successfully.")
        print(f"Database: {DB_PATH}")
        print(f"Hospitals in database: {counts['hospitals']}")
        print(f"Doctors in database: {counts['doctors']}")

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
