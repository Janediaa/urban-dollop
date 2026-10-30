
import sqlite3

import pytest

from src.database.models import create_tables
from src.services.hospital_service import find_hospitals


@pytest.fixture
def hospital_conn():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)
        conn.executemany(
            """
            INSERT INTO hospitals (hospital_name, city)
            VALUES (?, ?)
            """,
            [
                ("City Hospital", "Delhi"),
                ("Metro Hospital", "Noida"),
            ],
        )
        yield conn
    finally:
        conn.close()


def test_find_hospitals_returns_all_hospitals(hospital_conn):
    results = find_hospitals(hospital_conn)

    assert len(results) == 2


def test_find_hospitals_filters_by_city(hospital_conn):
    results = find_hospitals(hospital_conn, city="Noida")

    assert len(results) == 1
    assert results[0]["hospital_name"] == "Metro Hospital"


def test_find_hospitals_treats_blank_city_as_no_filter(hospital_conn):
    results = find_hospitals(hospital_conn, city="   ")

    assert len(results) == 2


def test_find_hospitals_rejects_non_string_city(hospital_conn):
    with pytest.raises(TypeError, match="city must be a string or None"):
        find_hospitals(hospital_conn, city=123)
