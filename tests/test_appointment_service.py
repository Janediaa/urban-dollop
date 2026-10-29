
import sqlite3
from datetime import date, timedelta

import pytest
from unittest.mock import patch
from src.database.models import create_tables
from src.services.appointment_service import (
    book_appointment,
    cancel_appointment,
    create_appointment_slot,
    get_appointment_by_reference,
    get_available_slots,
)


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


def test_booking_fails_and_rolls_back_if_slot_update_affects_no_rows(
    conn, future_slot
):
    with patch.object(conn, "execute", wraps=conn.execute) as execute_spy:
        original_execute = conn.execute

        def execute_with_failed_slot_update(sql, parameters=()):
            if (
                "UPDATE appointment_slots" in sql
                and "SET status = 'booked'" in sql
            ):
                return original_execute(
                    """
                    UPDATE appointment_slots
                    SET status = 'booked'
                    WHERE slot_id = ? AND status = 'available'
                    AND 1 = 0
                    """,
                    parameters,
                )

            return original_execute(sql, parameters)

        execute_spy.side_effect = execute_with_failed_slot_update

        with pytest.raises(ValueError, match="not available"):
            book_appointment(
                conn,
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
