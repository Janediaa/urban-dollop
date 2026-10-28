import pandas as pd
import pytest
import sqlite3

from src.database.seed import load_doctors_csv
from src.database.models import create_tables
from src.database.seed import insert_hospitals
from src.database.seed import insert_doctors
from src.database.seed import seed_database


REQUIRED_COLUMNS = [
    "doctor_name",
    "doctor_type",
    "experience_years",
    "location",
    "hospital",
    "fees",
    "city",
    "composite_doctor_id",
]


def test_load_doctors_csv_returns_dataframe(tmp_path):
    csv_path = tmp_path / "doctors.csv"

    expected_df = pd.DataFrame([
        {
            "doctor_name": "Dr. Sharma",
            "doctor_type": "Cardiologist",
            "experience_years": 10,
            "location": "Sector 18",
            "hospital": "City Hospital",
            "fees": 800,
            "city": "Noida",
            "composite_doctor_id": "DOC001",
        }
    ])

    expected_df.to_csv(csv_path, index=False)

    result = load_doctors_csv(csv_path)

    assert isinstance(result, pd.DataFrame)
    assert list(result.columns) == REQUIRED_COLUMNS
    assert len(result) == 1
    assert result.loc[0, "doctor_name"] == "Dr. Sharma"


def test_load_doctors_csv_raises_if_file_missing(tmp_path):
    csv_path = tmp_path / "missing.csv"

    with pytest.raises(FileNotFoundError):
        load_doctors_csv(csv_path)


def test_load_doctors_csv_raises_if_required_column_missing(tmp_path):
    csv_path = tmp_path / "doctors.csv"

    df = pd.DataFrame(columns=[
        column for column in REQUIRED_COLUMNS
        if column != "hospital"
    ])
    df.to_csv(csv_path, index=False)

    with pytest.raises(ValueError, match="hospital"):
        load_doctors_csv(csv_path)


def test_insert_hospitals_removes_duplicate_pairs():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)
        df = pd.DataFrame({
            "hospital": ["City Hospital", "City Hospital"],
            "city": ["Noida", "Noida"],
        })

        mapping = insert_hospitals(conn, df)

        assert len(mapping) == 1
        assert conn.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0] == 1
        assert ("city hospital", "noida") in mapping
    finally:
        conn.close()


def test_insert_hospitals_same_name_different_cities():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)
        df = pd.DataFrame({
            "hospital": ["City Hospital", "City Hospital"],
            "city": ["Noida", "Delhi"],
        })

        mapping = insert_hospitals(conn, df)

        assert len(mapping) == 2
        assert conn.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0] == 2
    finally:
        conn.close()


def test_insert_hospitals_normalizes_names_and_cities():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)
        df = pd.DataFrame({
            "hospital": ["  CITY Hospital ", "city hospital"],
            "city": [" NOIDA ", "noida"],
        })

        mapping = insert_hospitals(conn, df)

        assert len(mapping) == 1
        assert ("city hospital", "noida") in mapping
    finally:
        conn.close()



def test_insert_hospitals_skips_missing_values():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)

        df = pd.DataFrame({
            "hospital": ["City Hospital", None, "Another Hospital"],
            "city": ["Noida", "Delhi", None],
        })

        mapping = insert_hospitals(conn, df)

        assert len(mapping) == 1
        assert ("city hospital", "noida") in mapping
        assert conn.execute(
            "SELECT COUNT(*) FROM hospitals"
        ).fetchone()[0] == 1
    finally:
        conn.close()

def test_insert_hospitals_can_be_called_twice():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)
        df = pd.DataFrame({
            "hospital": ["City Hospital", "Apollo"],
            "city": ["Noida", "Delhi"],
        })

        first_mapping = insert_hospitals(conn, df)
        second_mapping = insert_hospitals(conn, df)

        assert first_mapping == second_mapping
        assert conn.execute("SELECT COUNT(*) FROM hospitals").fetchone()[0] == 2
    finally:
        conn.close()



def test_insert_doctors_links_valid_hospital():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)

        df = pd.DataFrame([{
            "composite_doctor_id": "DOC001",
            "doctor_name": "Dr. Sharma",
            "doctor_type": "Cardiologist",
            "experience_years": 10,
            "location": "Sector 18",
            "fees": 800,
            "city": "Noida",
            "hospital": "City Hospital",
        }])

        hospital_ids = insert_hospitals(conn, df)
        count = insert_doctors(conn, df, hospital_ids)

        row = conn.execute(
            "SELECT hospital_id FROM doctors "
            "WHERE composite_doctor_id = ?",
            ("DOC001",),
        ).fetchone()

        assert count == 1
        assert row is not None
        assert row[0] == hospital_ids[("city hospital", "noida")]
    finally:
        conn.close()


def test_insert_doctors_with_missing_hospital():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)

        df = pd.DataFrame([{
            "composite_doctor_id": "DOC002",
            "doctor_name": "Dr. Gupta",
            "doctor_type": "Neurologist",
            "experience_years": 5,
            "location": "Central Delhi",
            "fees": 600,
            "city": "Delhi",
            "hospital": None,
        }])

        count = insert_doctors(conn, df, {})

        row = conn.execute(
            "SELECT hospital_id FROM doctors "
            "WHERE composite_doctor_id = ?",
            ("DOC002",),
        ).fetchone()

        assert count == 1
        assert row[0] is None
    finally:
        conn.close()


def test_insert_doctors_converts_missing_optional_fields_to_null():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)

        df = pd.DataFrame([{
            "composite_doctor_id": "DOC003",
            "doctor_name": "Dr. Verma",
            "doctor_type": None,
            "experience_years": 7,
            "location": "Noida",
            "fees": None,
            "city": "Noida",
            "hospital": None,
        }])

        count = insert_doctors(conn, df, {})

        row = conn.execute(
            "SELECT doctor_type, fees FROM doctors "
            "WHERE composite_doctor_id = ?",
            ("DOC003",),
        ).fetchone()

        assert count == 1
        assert row == (None, None)
    finally:
        conn.close()


def test_insert_doctors_returns_inserted_count():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)

        df = pd.DataFrame([
            {
                "composite_doctor_id": "DOC004",
                "doctor_name": "Dr. A",
                "doctor_type": "Cardiologist",
                "experience_years": 5,
                "location": "Noida",
                "fees": 500,
                "city": "Noida",
                "hospital": None,
            },
            {
                "composite_doctor_id": "DOC005",
                "doctor_name": "Dr. B",
                "doctor_type": "Neurologist",
                "experience_years": 8,
                "location": "Delhi",
                "fees": 700,
                "city": "Delhi",
                "hospital": None,
            },
        ])

        count = insert_doctors(conn, df, {})

        assert count == 2
        assert conn.execute(
            "SELECT COUNT(*) FROM doctors"
        ).fetchone()[0] == 2
    finally:
        conn.close()


def test_insert_doctors_duplicate_id_raises_integrity_error():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)

        df = pd.DataFrame([
            {
                "composite_doctor_id": "DOC006",
                "doctor_name": "Dr. A",
                "doctor_type": "Cardiologist",
                "experience_years": 5,
                "location": "Noida",
                "fees": 500,
                "city": "Noida",
                "hospital": None,
            },
            {
                "composite_doctor_id": "DOC006",
                "doctor_name": "Dr. B",
                "doctor_type": "Neurologist",
                "experience_years": 8,
                "location": "Delhi",
                "fees": 700,
                "city": "Delhi",
                "hospital": None,
            },
        ])

        with pytest.raises(sqlite3.IntegrityError):
            insert_doctors(conn, df, {})
    finally:
        conn.close()




def test_seed_database_successful_import(tmp_path):
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)

        csv_path = tmp_path / "doctors.csv"
        df = pd.DataFrame([
            {
                "doctor_name": "Dr. Sharma",
                "doctor_type": "Cardiologist",
                "experience_years": 10,
                "location": "Sector 18",
                "hospital": "City Hospital",
                "fees": 800,
                "city": "Noida",
                "composite_doctor_id": "DOC101",
            },
            {
                "doctor_name": "Dr. Gupta",
                "doctor_type": "Neurologist",
                "experience_years": 5,
                "location": "Central Delhi",
                "hospital": None,
                "fees": 600,
                "city": "Delhi",
                "composite_doctor_id": "DOC102",
            },
        ])
        df.to_csv(csv_path, index=False)

        result = seed_database(conn, csv_path)

        assert result == {"hospitals": 1, "doctors": 2}

        rows = conn.execute(
            """
            SELECT composite_doctor_id, hospital_id
            FROM doctors
            ORDER BY composite_doctor_id
            """
        ).fetchall()

        assert len(rows) == 2
        assert rows[0][0] == "DOC101"
        assert rows[0][1] is not None
        assert rows[1] == ("DOC102", None)

    finally:
        conn.close()


def test_seed_database_rolls_back_on_duplicate_doctor_id(tmp_path):
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)

        csv_path = tmp_path / "duplicate_doctors.csv"
        df = pd.DataFrame([
            {
                "doctor_name": "Dr. Sharma",
                "doctor_type": "Cardiologist",
                "experience_years": 10,
                "location": "Sector 18",
                "hospital": "City Hospital",
                "fees": 800,
                "city": "Noida",
                "composite_doctor_id": "DOC201",
            },
            {
                "doctor_name": "Dr. Gupta",
                "doctor_type": "Neurologist",
                "experience_years": 5,
                "location": "Sector 18",
                "hospital": "City Hospital",
                "fees": 600,
                "city": "Noida",
                "composite_doctor_id": "DOC201",
            },
        ])
        df.to_csv(csv_path, index=False)

        with pytest.raises(sqlite3.IntegrityError):
            seed_database(conn, csv_path)

        assert conn.execute(
            "SELECT COUNT(*) FROM hospitals"
        ).fetchone()[0] == 0

        assert conn.execute(
            "SELECT COUNT(*) FROM doctors"
        ).fetchone()[0] == 0

    finally:
        conn.close()



def test_insert_doctors_normalizes_city_before_storing():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)

        df = pd.DataFrame([{
            "composite_doctor_id": "DOC007",
            "doctor_name": "Dr. Sharma",
            "doctor_type": "Cardiologist",
            "experience_years": 10,
            "location": "Sector 18",
            "fees": 800,
            "city": " NOIDA ",
            "hospital": None,
        }])

        count = insert_doctors(conn, df, {})

        row = conn.execute(
            "SELECT city FROM doctors WHERE composite_doctor_id = ?",
            ("DOC007",),
        ).fetchone()

        assert count == 1
        assert row == ("noida",)
    finally:
        conn.close()


def test_insert_doctors_raises_when_hospital_mapping_missing():
    conn = sqlite3.connect(":memory:")
    try:
        create_tables(conn)

        df = pd.DataFrame([{
            "composite_doctor_id": "DOC008",
            "doctor_name": "Dr. Gupta",
            "doctor_type": "Neurologist",
            "experience_years": 5,
            "location": "Sector 18",
            "fees": 600,
            "city": "Noida",
            "hospital": "City Hospital",
        }])

        with pytest.raises(ValueError, match="Hospital mapping not found"):
            insert_doctors(conn, df, {})
    finally:
        conn.close()
