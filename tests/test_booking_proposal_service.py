
import sqlite3
from datetime import date, timedelta
from datetime import datetime, timezone, timedelta
import pytest

from src.services.appointment_service import cancel_appointment
from src.database.models import create_tables
from src.services.booking_proposal_service import (
    confirm_booking_proposal,
    create_booking_proposal,
    get_booking_proposal,
)
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from src.database.connection import get_connection
from tests.test_appointment_service import conn


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

def test_cancelled_proposal_booking_can_be_rebooked(db):
    conn, slot_id = db

    # Create valid users because booking_proposals.user_id
    # references users.user_id.
    conn.executemany(
        """
        INSERT INTO users (full_name, email, password_hash)
        VALUES (?, ?, ?)
        """,
        [
            ("Patient One", "patient1@test.com", "test-hash"),
            ("Patient Two", "patient2@test.com", "test-hash"),
        ],
    )
    conn.commit()

    user_one_id = conn.execute(
        "SELECT user_id FROM users WHERE email = ?",
        ("patient1@test.com",),
    ).fetchone()[0]

    user_two_id = conn.execute(
        "SELECT user_id FROM users WHERE email = ?",
        ("patient2@test.com",),
    ).fetchone()[0]

    # Patient A creates and confirms the first proposal.
    first_proposal = create_booking_proposal(
        conn,
        slot_id,
        "Patient One",
        "contact-one",
        user_id=user_one_id,
    )

    first_booking = confirm_booking_proposal(
        conn,
        first_proposal["proposal_id"],
        user_id=user_one_id,
    )

    # Patient A cancels the appointment.
    cancel_appointment(
        conn,
        first_booking["booking_reference"],
        user_id=user_one_id,
    )

    # Patient B creates a new proposal for the released slot.
    second_proposal = create_booking_proposal(
        conn,
        slot_id,
        "Patient Two",
        "contact-two",
        user_id=user_two_id,
    )

    # This should succeed without breaking the old proposal.
    second_booking = confirm_booking_proposal(
        conn,
        second_proposal["proposal_id"],
        user_id=user_two_id,
    )

    assert second_booking["status"] == "confirmed"
    assert second_booking["booking_reference"] != (
        first_booking["booking_reference"]
    )

    old_proposal = get_booking_proposal(
        conn,
        first_proposal["proposal_id"],
    )

    assert old_proposal["status"] == "confirmed"
    assert old_proposal["booking_reference"] == (
        first_booking["booking_reference"]
    )

def test_concurrent_proposal_confirmation_allows_only_one_booking(tmp_path):
    db_path = tmp_path / "concurrent_proposals.db"

    # Set up a file-backed database shared by both workers.
    conn = get_connection(db_path)
    create_tables(conn)

    conn.execute(
        "INSERT INTO hospitals (hospital_name, city) VALUES (?, ?)",
        ("Test Hospital", "Delhi"),
    )

    hospital_id = conn.execute(
        "SELECT hospital_id FROM hospitals WHERE hospital_name = ?",
        ("Test Hospital",),
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO doctors (
            composite_doctor_id, doctor_name, doctor_type,
            experience_years, location, fees, city, hospital_id
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "DOC-CONCURRENT",
            "Dr. Concurrent",
            "General Medicine",
            5,
            "Delhi",
            500,
            "Delhi",
            hospital_id,
        ),
    )

    doctor_id = conn.execute(
        "SELECT doctor_id FROM doctors WHERE composite_doctor_id = ?",
        ("DOC-CONCURRENT",),
    ).fetchone()[0]

    appointment_date = (
        date.today() + timedelta(days=30)
    ).isoformat()

    cursor = conn.execute(
        """
        INSERT INTO appointment_slots (
            doctor_id, appointment_date, appointment_time, status
        )
        VALUES (?, ?, ?, 'available')
        """,
        (doctor_id, appointment_date, "10:00"),
    )

    slot_id = cursor.lastrowid

    # Create two users.
    conn.executemany(
        """
        INSERT INTO users (full_name, email, password_hash)
        VALUES (?, ?, ?)
        """,
        [
            ("Patient One", "concurrent1@test.com", "test-hash"),
            ("Patient Two", "concurrent2@test.com", "test-hash"),
        ],
    )

    user_one_id = conn.execute(
        "SELECT user_id FROM users WHERE email = ?",
        ("concurrent1@test.com",),
    ).fetchone()[0]

    user_two_id = conn.execute(
        "SELECT user_id FROM users WHERE email = ?",
        ("concurrent2@test.com",),
    ).fetchone()[0]

    # Commit database setup before service methods start their own transactions.
    conn.commit()

    # Both users create proposals for the same slot.
    proposal_one = create_booking_proposal(
        conn,
        slot_id,
        "Patient One",
        "contact-one",
        user_id=user_one_id,
    )

    proposal_two = create_booking_proposal(
        conn,
        slot_id,
        "Patient Two",
        "contact-two",
        user_id=user_two_id,
    )

    conn.close()

    # Synchronize both workers so they attempt confirmation together.
    barrier = Barrier(2)

    def confirm_proposal(proposal_id, user_id):
        worker_conn = get_connection(db_path)

        try:
            barrier.wait(timeout=5)

            booking = confirm_booking_proposal(
                worker_conn,
                proposal_id,
                user_id=user_id,
            )

            return ("confirmed", booking)

        except ValueError as exc:
            return ("rejected", str(exc))

        finally:
            worker_conn.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_one = executor.submit(
            confirm_proposal,
            proposal_one["proposal_id"],
            user_one_id,
        )

        future_two = executor.submit(
            confirm_proposal,
            proposal_two["proposal_id"],
            user_two_id,
        )

        results = [
            future_one.result(timeout=10),
            future_two.result(timeout=10),
        ]

    # Exactly one confirmation must succeed.
    statuses = sorted(result[0] for result in results)

    assert statuses == ["confirmed", "rejected"]

    # Verify persistent database state.
    verification_conn = get_connection(db_path)

    try:
        appointment_count = verification_conn.execute(
            """
            SELECT COUNT(*)
            FROM appointments
            WHERE slot_id = ? AND status = 'confirmed'
            """,
            (slot_id,),
        ).fetchone()[0]

        slot_status = verification_conn.execute(
            "SELECT status FROM appointment_slots WHERE slot_id = ?",
            (slot_id,),
        ).fetchone()[0]

        proposal_statuses = verification_conn.execute(
            """
            SELECT status
            FROM booking_proposals
            WHERE proposal_id IN (?, ?)
            """,
            (
                proposal_one["proposal_id"],
                proposal_two["proposal_id"],
            ),
        ).fetchall()

        foreign_key_errors = verification_conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        assert appointment_count == 1
        assert slot_status == "booked"
        assert sorted(row[0] for row in proposal_statuses) == [
            "confirmed",
            "pending",
        ]
        assert foreign_key_errors == []

    finally:
        verification_conn.close()