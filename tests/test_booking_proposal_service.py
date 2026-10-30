
import sqlite3
from datetime import date, timedelta
from datetime import datetime, timezone, timedelta
import pytest

from src.database.models import create_tables
from src.services.booking_proposal_service import (
    confirm_booking_proposal,
    create_booking_proposal,
    get_booking_proposal,
)


@pytest.fixture
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    create_tables(conn)

    conn.execute(
        "INSERT INTO hospitals (hospital_name, city) VALUES (?, ?)",
        ("Test Hospital", "Delhi"),
    )

    conn.execute(
        """
        INSERT INTO doctors (
            composite_doctor_id, doctor_name, doctor_type,
            experience_years, location, fees, city, hospital_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("DOC-TEST", "Dr. Test", "General Medicine", 5,
         "Delhi", 500, "Delhi", 1),
    )

    doctor_id = conn.execute(
        "SELECT doctor_id FROM doctors WHERE composite_doctor_id = ?",
        ("DOC-TEST",),
    ).fetchone()[0]

    appointment_date = (date.today() + timedelta(days=30)).isoformat()

    cursor = conn.execute(
        """
        INSERT INTO appointment_slots (
            doctor_id, appointment_date, appointment_time, status
        )
        VALUES (?, ?, ?, 'available')
        """,
        (doctor_id, appointment_date, "10:00"),
    )

    conn.commit()

    yield conn, cursor.lastrowid

    conn.close()


def test_creating_proposal_does_not_book_slot(db):
    conn, slot_id = db

    proposal = create_booking_proposal(
        conn,
        slot_id=slot_id,
        patient_name="Test Patient",
        patient_contact="test-contact",
    )

    slot_status = conn.execute(
        "SELECT status FROM appointment_slots WHERE slot_id = ?",
        (slot_id,),
    ).fetchone()[0]

    appointment_count = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE slot_id = ?",
        (slot_id,),
    ).fetchone()[0]

    assert proposal["status"] == "pending"
    assert proposal["requires_confirmation"] is True
    assert slot_status == "available"
    assert appointment_count == 0


def test_proposal_can_be_retrieved(db):
    conn, slot_id = db

    created = create_booking_proposal(
        conn,
        slot_id=slot_id,
        patient_name="Test Patient",
        patient_contact="test-contact",
    )

    retrieved = get_booking_proposal(conn, created["proposal_id"])

    assert retrieved is not None
    assert retrieved["proposal_id"] == created["proposal_id"]
    assert retrieved["slot_id"] == slot_id
    assert retrieved["status"] == "pending"


def test_proposal_for_missing_slot_is_rejected(db):
    conn, _ = db

    with pytest.raises(ValueError, match="slot not found"):
        create_booking_proposal(
            conn,
            slot_id=99999,
            patient_name="Test Patient",
            patient_contact="test-contact",
        )


def test_proposal_for_unavailable_slot_is_rejected(db):
    conn, slot_id = db

    conn.execute(
        "UPDATE appointment_slots SET status = 'booked' WHERE slot_id = ?",
        (slot_id,),
    )
    conn.commit()

    with pytest.raises(ValueError, match="not available"):
        create_booking_proposal(
            conn,
            slot_id=slot_id,
            patient_name="Test Patient",
            patient_contact="test-contact",
        )


def test_empty_patient_details_are_rejected(db):
    conn, slot_id = db

    with pytest.raises(ValueError, match="patient_name"):
        create_booking_proposal(
            conn,
            slot_id=slot_id,
            patient_name=" ",
            patient_contact="test-contact",
        )

    with pytest.raises(ValueError, match="patient_contact"):
        create_booking_proposal(
            conn,
            slot_id=slot_id,
            patient_name="Test Patient",
            patient_contact=" ",
        )


def test_confirmation_books_appointment_and_confirms_proposal(db):
    conn, slot_id = db

    proposal = create_booking_proposal(
        conn, slot_id, "Test Patient", "test-contact"
    )

    booking = confirm_booking_proposal(conn, proposal["proposal_id"])

    assert booking["status"] == "confirmed"
    assert booking["slot_id"] == slot_id
    assert booking["booking_reference"]

    stored_proposal = get_booking_proposal(conn, proposal["proposal_id"])
    assert stored_proposal["status"] == "confirmed"
    assert stored_proposal["booking_reference"] == booking["booking_reference"]

    slot_status = conn.execute(
        "SELECT status FROM appointment_slots WHERE slot_id = ?",
        (slot_id,),
    ).fetchone()[0]
    appointment_count = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE slot_id = ?",
        (slot_id,),
    ).fetchone()[0]

    assert slot_status == "booked"
    assert appointment_count == 1


def test_expired_proposal_cannot_be_confirmed(db):
    conn, slot_id = db

    proposal = create_booking_proposal(
        conn, slot_id, "Test Patient", "test-contact"
    )

    expired_time = (
        datetime.now(timezone.utc) - timedelta(minutes=1)
    ).isoformat()

    conn.execute(
        "UPDATE booking_proposals SET expires_at = ? WHERE proposal_id = ?",
        (expired_time, proposal["proposal_id"]),
    )
    conn.commit()

    with pytest.raises(ValueError, match="expired"):
        confirm_booking_proposal(conn, proposal["proposal_id"])

    stored = get_booking_proposal(conn, proposal["proposal_id"])
    assert stored["status"] == "expired"

    assert conn.execute(
        "SELECT status FROM appointment_slots WHERE slot_id = ?",
        (slot_id,),
    ).fetchone()[0] == "available"

    assert conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE slot_id = ?",
        (slot_id,),
    ).fetchone()[0] == 0


def test_proposal_cannot_be_confirmed_twice(db):
    conn, slot_id = db

    proposal = create_booking_proposal(
        conn, slot_id, "Test Patient", "test-contact"
    )

    confirm_booking_proposal(conn, proposal["proposal_id"])

    with pytest.raises(ValueError, match="not pending"):
        confirm_booking_proposal(conn, proposal["proposal_id"])

    assert conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE slot_id = ?",
        (slot_id,),
    ).fetchone()[0] == 1


def test_only_one_of_two_proposals_for_same_slot_can_be_confirmed(db):
    conn, slot_id = db

    first_proposal = create_booking_proposal(
        conn,
        slot_id,
        "Patient One",
        "contact-one",
    )
    second_proposal = create_booking_proposal(
        conn,
        slot_id,
        "Patient Two",
        "contact-two",
    )

    # Both proposals may be pending, but only one can book the slot.
    first_booking = confirm_booking_proposal(
        conn, first_proposal["proposal_id"]
    )

    with pytest.raises(ValueError, match="not available"):
        confirm_booking_proposal(
            conn, second_proposal["proposal_id"]
        )

    slot_status = conn.execute(
        "SELECT status FROM appointment_slots WHERE slot_id = ?",
        (slot_id,),
    ).fetchone()[0]

    appointment_count = conn.execute(
        "SELECT COUNT(*) FROM appointments WHERE slot_id = ?",
        (slot_id,),
    ).fetchone()[0]

    second_stored_proposal = get_booking_proposal(
        conn, second_proposal["proposal_id"]
    )

    assert first_booking["status"] == "confirmed"
    assert slot_status == "booked"
    assert appointment_count == 1
    assert second_stored_proposal["status"] == "pending"


def test_failed_confirmation_rolls_back_appointment_and_keeps_proposal_pending(
    db,
):
    conn, slot_id = db

    proposal = create_booking_proposal(
        conn,
        slot_id,
        "Test Patient",
        "test-contact",
    )

    # Simulate an unavailable slot before confirmation.
    conn.execute(
        """
        UPDATE appointment_slots
        SET status = 'booked'
        WHERE slot_id = ?
        """,
        (slot_id,),
    )
    conn.commit()

    with pytest.raises(ValueError, match="not available"):
        confirm_booking_proposal(conn, proposal["proposal_id"])

    stored_proposal = get_booking_proposal(
        conn, proposal["proposal_id"]
    )

    appointment_count = conn.execute(
        """
        SELECT COUNT(*)
        FROM appointments
        WHERE slot_id = ?
        """,
        (slot_id,),
    ).fetchone()[0]

    assert stored_proposal["status"] == "pending"
    assert appointment_count == 0
