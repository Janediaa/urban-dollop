
import sqlite3
from datetime import date, timedelta

import pytest

from src.database.models import create_tables
from src.services.appointment_service import (
    book_appointment,
    cancel_appointment,
    create_appointment_slot,
    get_appointment_by_reference,
    get_available_slots,
)
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from src.database.connection import get_connection


@pytest.fixture
def conn():
    connection = sqlite3.connect(":memory:")
    connection.execute("PRAGMA foreign_keys = ON")
    create_tables(connection)

    connection.execute(
        """
        INSERT INTO hospitals (hospital_name, city)
        VALUES ('Test Hospital', 'Noida')
        """
    )
    hospital_id = connection.execute(
        "SELECT hospital_id FROM hospitals"
    ).fetchone()[0]

    connection.execute(
        """
        INSERT INTO doctors (
            composite_doctor_id, doctor_name, doctor_type,
            experience_years, location, fees, city, hospital_id
        )
        VALUES ('DOC-001', 'Dr Test', 'Cardiology', 10, 'Noida', 500, 'Noida', ?)
        """,
        (hospital_id,),
    )
    connection.commit()

    yield connection
    connection.close()


@pytest.fixture
def future_slot(conn):
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    return create_appointment_slot(conn, 1, tomorrow, "10:30")


def test_create_and_list_available_slot(conn, future_slot):
    slots = get_available_slots(conn, 1)

    assert len(slots) == 1
    assert slots[0]["slot_id"] == future_slot["slot_id"]
    assert slots[0]["status"] == "available"


def test_duplicate_slot_is_rejected(conn, future_slot):
    with pytest.raises(ValueError, match="Slot could not be created"):
        create_appointment_slot(
            conn,
            1,
            future_slot["appointment_date"],
            future_slot["appointment_time"],
        )


def test_booking_and_retrieval(conn, future_slot):
    booking = book_appointment(
        conn,
        future_slot["slot_id"],
        "Test Patient",
        "test@example.com",
    )

    retrieved = get_appointment_by_reference(
        conn, booking["booking_reference"]
    )

    assert retrieved is not None
    assert retrieved["status"] == "confirmed"
    assert retrieved["doctor_name"] == "Dr Test"
    assert get_available_slots(conn, 1) == []


def test_slot_cannot_be_booked_twice(conn, future_slot):
    book_appointment(
        conn, future_slot["slot_id"], "Patient One", "one@example.com"
    )

    with pytest.raises(ValueError, match="not available"):
        book_appointment(
            conn, future_slot["slot_id"], "Patient Two", "two@example.com"
        )


def test_cancelled_slot_can_be_rebooked(conn, future_slot):
    first = book_appointment(
        conn, future_slot["slot_id"], "Patient One", "one@example.com"
    )

    cancel_appointment(conn, first["booking_reference"])

    second = book_appointment(
        conn, future_slot["slot_id"], "Patient Two", "two@example.com"
    )

    assert second["status"] == "confirmed"
    assert second["booking_reference"] != first["booking_reference"]


def test_cannot_book_nonexistent_slot(conn):
    with pytest.raises(ValueError, match="slot not found"):
        book_appointment(conn, 999, "Test Patient", "test@example.com")


def test_cannot_cancel_booking_twice(conn, future_slot):
    booking = book_appointment(
        conn, future_slot["slot_id"], "Test Patient", "test@example.com"
    )

    cancel_appointment(conn, booking["booking_reference"])

    with pytest.raises(ValueError, match="Only confirmed"):
        cancel_appointment(conn, booking["booking_reference"])


def test_cancellation_marks_appointment_cancelled_and_releases_slot(
    conn, future_slot
):
    booking = book_appointment(
        conn,
        future_slot["slot_id"],
        "Test Patient",
        "test@example.com",
    )

    result = cancel_appointment(
        conn, booking["booking_reference"]
    )

    appointment_status = conn.execute(
        """
        SELECT status FROM appointments
        WHERE booking_reference = ?
        """,
        (booking["booking_reference"],),
    ).fetchone()[0]

    slot_status = conn.execute(
        """
        SELECT status FROM appointment_slots
        WHERE slot_id = ?
        """,
        (future_slot["slot_id"],),
    ).fetchone()[0]

    assert result["status"] == "cancelled"
    assert appointment_status == "cancelled"
    assert slot_status == "available"



def test_booking_rolls_back_when_slot_update_fails(conn, future_slot):
    booking_transaction = conn.execute

    def execute_with_failed_slot_update(sql, parameters=()):
        if (
            "UPDATE appointment_slots" in sql
            and "SET status = 'booked'" in sql
        ):
            return booking_transaction(
                """
                UPDATE appointment_slots
                SET status = 'booked'
                WHERE slot_id = ? AND status = 'available'
                AND 1 = 0
                """,
                parameters,
            )

        return booking_transaction(sql, parameters)

    class ConnectionProxy:
        def execute(self, sql, parameters=()):
            return execute_with_failed_slot_update(sql, parameters)

        def __getattr__(self, name):
            return getattr(conn, name)

    with pytest.raises(ValueError, match="not available"):
        book_appointment(
            ConnectionProxy(),
            future_slot["slot_id"],
            "Test Patient",
            "test@example.com",
        )

    appointment_count = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE slot_id = ?",
        (future_slot["slot_id"],),
    ).fetchone()[0]

    slot_status = conn.execute(
        "SELECT status FROM appointment_slots WHERE slot_id = ?",
        (future_slot["slot_id"],),
    ).fetchone()[0]

    assert appointment_count == 0
    assert slot_status == "available"



def test_concurrent_booking_allows_only_one_patient(tmp_path):
    db_path = tmp_path / "concurrent_booking.db"

    # Initialize a real SQLite database.
    setup_conn = get_connection(db_path)

    try:
        create_tables(setup_conn)

        setup_conn.execute(
            """
            INSERT INTO hospitals (hospital_name, city)
            VALUES ('Concurrency Hospital', 'Noida')
            """
        )

        setup_conn.execute(
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
            VALUES (
                'CONC-001',
                'Dr Concurrency',
                'General Medicine',
                5,
                'Noida',
                500,
                'Noida',
                1
            )
            """
        )

        doctor_id = setup_conn.execute(
            """
            SELECT doctor_id
            FROM doctors
            WHERE composite_doctor_id = 'CONC-001'
            """
        ).fetchone()[0]

        future_date = (
            date.today() + timedelta(days=30)
        ).isoformat()

        slot = create_appointment_slot(
            setup_conn,
            doctor_id,
            future_date,
            "10:30",
        )

        slot_id = slot["slot_id"]

    finally:
        setup_conn.close()

    # Both workers start booking at approximately the same time.
    barrier = Barrier(2)

    def attempt_booking(patient_name):
        conn = get_connection(db_path)

        try:
            barrier.wait(timeout=5)

            try:
                booking = book_appointment(
                    conn,
                    slot_id,
                    patient_name,
                    f"{patient_name.lower()}@test.com",
                )

                return ("booked", booking)

            except ValueError as exc:
                return ("rejected", str(exc))

        finally:
            conn.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(attempt_booking, "Patient One"),
            executor.submit(attempt_booking, "Patient Two"),
        ]

        results = [future.result(timeout=10) for future in futures]

    # Exactly one booking must succeed.
    assert sorted(result[0] for result in results) == [
        "booked",
        "rejected",
    ]

    # Verify the database after both connections have closed.
    verify_conn = get_connection(db_path)

    try:
        appointments = verify_conn.execute(
            """
            SELECT COUNT(*)
            FROM appointments
            WHERE slot_id = ? AND status = 'confirmed'
            """,
            (slot_id,),
        ).fetchone()[0]

        slot_status = verify_conn.execute(
            """
            SELECT status
            FROM appointment_slots
            WHERE slot_id = ?
            """,
            (slot_id,),
        ).fetchone()[0]

        assert appointments == 1
        assert slot_status == "booked"

    finally:
        verify_conn.close()

