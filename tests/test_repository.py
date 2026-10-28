import sqlite3
import pytest

from src.database.models import create_tables
from src.database.repository import get_doctor_by_id
from src.database.repository import search_doctors

from src.database.repository import (
    get_doctor_by_id,
    get_doctor_with_hospital,
    search_doctors,
)


def test_get_doctor_by_id_returns_doctor():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)

        conn.execute(
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
            (
                "DOC001",
                "Dr. Sharma",
                "Cardiologist",
                10,
                "Sector 18",
                800,
                "noida",
                None,
            ),
        )

        doctor = get_doctor_by_id(conn, "DOC001")

        assert doctor is not None
        assert doctor["composite_doctor_id"] == "DOC001"
        assert doctor["doctor_name"] == "Dr. Sharma"
        assert doctor["doctor_type"] == "Cardiologist"

    finally:
        conn.close()


def test_get_doctor_by_id_returns_none_when_not_found():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)

        doctor = get_doctor_by_id(conn, "NONEXISTENT")

        assert doctor is None

    finally:
        conn.close()




@pytest.fixture
def repository_conn():
    conn = sqlite3.connect(":memory:")
    create_tables(conn)

    doctors = [
        (
            "DOC001", "Dr. Sharma", "Cardiologist",
            10, "Sector 18", 800, "Delhi", None,
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
    conn.close()


def test_search_doctors_without_filters_returns_all(repository_conn):
    results = search_doctors(repository_conn)

    assert len(results) == 3
    assert {
        doctor["composite_doctor_id"] for doctor in results
    } == {"DOC001", "DOC002", "DOC003"}


def test_search_doctors_by_city(repository_conn):
    results = search_doctors(repository_conn, city="delhi")

    assert len(results) == 2
    assert all(doctor["city"].lower() == "delhi" for doctor in results)


def test_search_doctors_by_specialty(repository_conn):
    results = search_doctors(
        repository_conn,
        doctor_type="cardiologist",
    )

    assert len(results) == 2
    assert all(
        doctor["doctor_type"] == "Cardiologist"
        for doctor in results
    )


def test_search_doctors_by_city_and_specialty(repository_conn):
    results = search_doctors(
        repository_conn,
        city="delhi",
        doctor_type="cardiologist",
    )

    assert len(results) == 1
    assert results[0]["composite_doctor_id"] == "DOC001"


def test_search_doctors_specialty_is_case_insensitive_and_partial(
    repository_conn,
):
    results = search_doctors(
        repository_conn,
        doctor_type="CARDIO",
    )

    assert len(results) == 2
    assert all(
        "cardio" in doctor["doctor_type"].lower()
        for doctor in results
    )


def test_search_doctors_no_matches_returns_empty_list(repository_conn):
    results = search_doctors(repository_conn, city="Mumbai")

    assert results == []


def test_search_doctors_without_filters_returns_all_doctors(repository_conn):
    results = search_doctors(repository_conn)

    assert len(results) == 3


def test_search_doctors_filters_by_city(repository_conn):
    results = search_doctors(repository_conn, city="delhi")

    assert results
    assert all(row["city"].lower() == "delhi" for row in results)


def test_search_doctors_filters_by_specialty(repository_conn):
    results = search_doctors(repository_conn, doctor_type="cardio")

    assert results
    assert all(
        "cardio" in row["doctor_type"].lower()
        for row in results
    )


def test_search_doctors_combines_filters(repository_conn):
    results = search_doctors(
        repository_conn,
        city="delhi",
        doctor_type="cardio",
    )

    assert len(results) == 1
    assert all(row["city"].lower() == "delhi" for row in results)
    assert all(
        "cardio" in row["doctor_type"].lower()
        for row in results
    )


def test_get_doctor_with_hospital_returns_hospital_details(repository_conn):
    hospital_cursor = repository_conn.execute(
        """
        INSERT INTO hospitals (hospital_name, city)
        VALUES (?, ?)
        """,
        ("City Hospital", "Delhi"),
    )
    hospital_id = hospital_cursor.lastrowid

    repository_conn.execute(
        """
        UPDATE doctors
        SET hospital_id = ?
        WHERE composite_doctor_id = ?
        """,
        (hospital_id, "DOC001"),
    )

    doctor = get_doctor_with_hospital(repository_conn, "DOC001")

    assert doctor is not None
    assert doctor["doctor_name"] == "Dr. Sharma"
    assert doctor["hospital_name"] == "City Hospital"
    assert doctor["hospital_city"] == "Delhi"
    assert doctor["city"] == "Delhi"


def test_get_doctor_with_hospital_without_hospital_link(repository_conn):
    doctor = get_doctor_with_hospital(repository_conn, "DOC002")

    assert doctor is not None
    assert doctor["doctor_name"] == "Dr. Gupta"
    assert doctor["hospital_id"] is None
    assert doctor["hospital_name"] is None
    assert doctor["hospital_city"] is None


def test_get_doctor_with_hospital_returns_none_when_not_found(
    repository_conn,
):
    doctor = get_doctor_with_hospital(
        repository_conn,
        "NONEXISTENT",
    )

    assert doctor is None



def test_search_doctors_by_minimum_experience(repository_conn):
    results = search_doctors(repository_conn, min_experience=7)

    assert {
        doctor["composite_doctor_id"] for doctor in results
    } == {"DOC001", "DOC003"}


def test_search_doctors_by_maximum_fee(repository_conn):
    results = search_doctors(repository_conn, max_fees=700)

    assert {
        doctor["composite_doctor_id"] for doctor in results
    } == {"DOC002", "DOC003"}


def test_search_doctors_combines_all_filters(repository_conn):
    results = search_doctors(
        repository_conn,
        city="delhi",
        doctor_type="cardio",
        min_experience=8,
        max_fees=1000,
    )

    assert len(results) == 1
    assert results[0]["composite_doctor_id"] == "DOC001"


def test_search_doctors_excludes_unknown_fees_when_max_fee_is_set(
    repository_conn,
):
    repository_conn.execute(
        """
        UPDATE doctors
        SET fees = NULL
        WHERE composite_doctor_id = ?
        """,
        ("DOC001",),
    )

    results = search_doctors(repository_conn, max_fees=1000)

    returned_ids = {
        doctor["composite_doctor_id"] for doctor in results
    }

    assert "DOC001" not in returned_ids
    assert returned_ids == {"DOC002", "DOC003"}


def test_search_doctors_without_new_filters_preserves_old_behavior(
    repository_conn,
):
    results = search_doctors(
        repository_conn,
        city="delhi",
        doctor_type="cardio",
    )

    assert len(results) == 1
    assert results[0]["composite_doctor_id"] == "DOC001"

    all_doctors = search_doctors(repository_conn)

    assert len(all_doctors) == 3



import pytest

from src.database.repository import search_doctors


def test_search_doctors_defaults_to_alphabetical_order(repository_conn):
    results = search_doctors(repository_conn)

    names = [doctor["doctor_name"] for doctor in results]

    assert names == sorted(names)


def test_search_doctors_sorts_by_experience_descending(repository_conn):
    results = search_doctors(
        repository_conn,
        sort_by="experience",
    )

    experiences = [
        doctor["experience_years"]
        for doctor in results
    ]

    assert experiences == sorted(experiences, reverse=True)


def test_search_doctors_sorts_by_fees_ascending_with_nulls_last(
    repository_conn,
):
    # Add a doctor whose consultation fee is unknown.
    repository_conn.execute(
        """
        UPDATE doctors
        SET fees = NULL
        WHERE composite_doctor_id = ?
        """,
        ("DOC001",),
    )

    results = search_doctors(
        repository_conn,
        sort_by="fees",
    )

    fees = [doctor["fees"] for doctor in results]

    known_fees = [fee for fee in fees if fee is not None]
    unknown_fees = [fee for fee in fees if fee is None]

    assert known_fees == sorted(known_fees)
    assert unknown_fees == [None]
    assert fees[-1] is None


def test_search_doctors_rejects_unsupported_sort_option(repository_conn):
    with pytest.raises(ValueError, match="Unsupported sort_by"):
        search_doctors(
            repository_conn,
            sort_by="popularity",
        )


def test_search_doctors_combines_filters_with_sorting(repository_conn):
    results = search_doctors(
        repository_conn,
        city="delhi",
        doctor_type="cardio",
        min_experience=8,
        max_fees=1000,
        sort_by="experience",
    )

    assert len(results) == 1
    assert results[0]["composite_doctor_id"] == "DOC001"


from src.database.repository import get_doctor_count


def test_get_doctor_count_returns_number_of_doctors(repository_conn):
    count = get_doctor_count(repository_conn)

    assert count == 3


def test_get_doctor_count_returns_zero_when_no_doctors(repository_conn):
    repository_conn.execute("DELETE FROM doctors")

    count = get_doctor_count(repository_conn)

    assert count == 0
