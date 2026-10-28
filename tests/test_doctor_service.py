
import sqlite3

import pytest

from src.database.models import create_tables
from src.services.doctor_service import find_doctors


@pytest.fixture
def service_conn():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)

        cursor = conn.execute(
            """
            INSERT INTO hospitals (hospital_name, city)
            VALUES (?, ?)
            """,
            ("City Heart Hospital", "Delhi"),
        )
        hospital_id = cursor.lastrowid
        doctors = [
            (
                "DOC001", "Dr. Sharma", "Cardiologist",
                10, "Sector 18", 800, "Delhi", hospital_id,
            ),
            (
                "DOC002", "Dr. Gupta", "Neurologist",
                5, "Central Delhi", 600, "Delhi", None,
            ),
            (
                "DOC003", "Dr. Verma", "Cardiologist",
                7, "Sector 62", 700, "Noida", None,
            ),
        ]

        conn.executemany(
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

        yield conn
    finally:
        conn.close()


def test_find_doctors_returns_expected_matches(service_conn):
    results = find_doctors(
        service_conn,
        city="Delhi",
        doctor_type="cardio",
        min_experience=5,
        max_fees=1000,
    )

    assert len(results) == 1
    assert results[0]["composite_doctor_id"] == "DOC001"
    assert results[0]["doctor_name"] == "Dr. Sharma"


def test_find_doctors_rejects_negative_experience(service_conn):
    with pytest.raises(ValueError, match="min_experience cannot be negative"):
        find_doctors(service_conn, min_experience=-5)


def test_find_doctors_rejects_negative_fees(service_conn):
    with pytest.raises(ValueError, match="max_fees cannot be negative"):
        find_doctors(service_conn, max_fees=-100)


@pytest.mark.parametrize("invalid_city", [123, [], {}])
def test_find_doctors_rejects_invalid_city_type(
    service_conn,
    invalid_city,
):
    with pytest.raises(TypeError, match="city must be a string"):
        find_doctors(service_conn, city=invalid_city)


@pytest.mark.parametrize("invalid_type", [123, [], {}])
def test_find_doctors_rejects_invalid_specialty_type(
    service_conn,
    invalid_type,
):
    with pytest.raises(TypeError, match="doctor_type must be a string"):
        find_doctors(service_conn, doctor_type=invalid_type)


def test_find_doctors_returns_empty_list_when_no_matches(service_conn):
    results = find_doctors(service_conn, city="Mumbai")

    assert results == []



def test_find_doctors_rejects_fractional_experience(service_conn):
    with pytest.raises(TypeError, match="min_experience must be an integer"):
        find_doctors(service_conn, min_experience=3.5)


def test_find_doctors_rejects_boolean_experience(service_conn):
    with pytest.raises(TypeError, match="min_experience must be an integer"):
        find_doctors(service_conn, min_experience=True)


def test_find_doctors_rejects_boolean_fees(service_conn):
    with pytest.raises(TypeError, match="max_fees must be a number"):
        find_doctors(service_conn, max_fees=True)


def test_find_doctors_rejects_string_fees(service_conn):
    with pytest.raises(TypeError, match="max_fees must be a number"):
        find_doctors(service_conn, max_fees="500")


def test_find_doctors_rejects_unsupported_sort_option(service_conn):
    with pytest.raises(ValueError, match="Unsupported sort_by"):
        find_doctors(service_conn, sort_by="popularity")



def test_find_doctors_includes_hospital_details(service_conn):
    results = find_doctors(
        service_conn,
        city="Delhi",
        doctor_type="cardio",
    )

    assert len(results) == 1
    doctor = results[0]

    assert doctor["composite_doctor_id"] == "DOC001"
    assert doctor["hospital_name"] == "City Heart Hospital"
    assert doctor["hospital_city"] == "Delhi"


def test_find_doctors_keeps_doctor_without_hospital(service_conn):
    results = find_doctors(
        service_conn,
        city="Delhi",
        doctor_type="neurologist",
    )

    assert len(results) == 1
    doctor = results[0]

    assert doctor["composite_doctor_id"] == "DOC002"
    assert doctor["hospital_name"] is None
    assert doctor["hospital_city"] is None


def test_find_doctors_preserves_sorting_with_hospital_details(service_conn):
    results = find_doctors(
        service_conn,
        sort_by="experience",
    )

    ids = [doctor["composite_doctor_id"] for doctor in results]

    assert ids == ["DOC001", "DOC003", "DOC002"]

