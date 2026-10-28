
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.database.connection import get_connection


DB_PATH = PROJECT_ROOT / "data" / "healthcare.db"


def main() -> None:
    if not DB_PATH.is_file():
        raise FileNotFoundError(f"Database not found: {DB_PATH}")

    conn = None

    try:
        conn = get_connection(DB_PATH)

        doctor_count = conn.execute(
            "SELECT COUNT(*) FROM doctors"
        ).fetchone()[0]

        hospital_count = conn.execute(
            "SELECT COUNT(*) FROM hospitals"
        ).fetchone()[0]

        doctors_without_hospital = conn.execute(
            """
            SELECT COUNT(*)
            FROM doctors
            WHERE hospital_id IS NULL
            """
        ).fetchone()[0]

        broken_references = conn.execute(
            """
            SELECT d.composite_doctor_id, d.hospital_id
            FROM doctors AS d
            LEFT JOIN hospitals AS h
                ON d.hospital_id = h.hospital_id
            WHERE d.hospital_id IS NOT NULL
              AND h.hospital_id IS NULL
            """
        ).fetchall()

        foreign_key_violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        print("DATABASE VERIFICATION")
        print("=" * 40)
        print(f"Database: {DB_PATH}")
        print(f"Total doctors: {doctor_count}")
        print(f"Total hospitals: {hospital_count}")
        print(f"Doctors without hospital: {doctors_without_hospital}")

        print(f"\nBroken hospital references: {len(broken_references)}")
        if broken_references:
            for doctor_id, hospital_id in broken_references:
                print(
                    f"  Doctor ID: {doctor_id}, "
                    f"Hospital ID: {hospital_id}"
                )
        else:
            print("  None")

        print(f"\nForeign-key violations: {len(foreign_key_violations)}")
        if foreign_key_violations:
            for violation in foreign_key_violations:
                print(f"  {violation}")
        else:
            print("  None")

    finally:
        if conn is not None:
            conn.close()


if __name__ == "__main__":
    main()
