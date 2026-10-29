
"""Manage pending appointment booking proposals."""

import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from src.services.appointment_service import book_appointment

PROPOSAL_TTL_MINUTES = 10


def create_booking_proposal(
    conn: sqlite3.Connection,
    slot_id: int,
    patient_name: str,
    patient_contact: str,
        *,
    user_id: int | None = None,
) -> dict:
    """Create a pending proposal without booking the appointment."""

    if not isinstance(slot_id, int) or isinstance(slot_id, bool) or slot_id <= 0:
        raise ValueError("slot_id must be a positive integer")

    if not isinstance(patient_name, str) or not patient_name.strip():
        raise ValueError("patient_name must not be empty")

    if not isinstance(patient_contact, str) or not patient_contact.strip():
        raise ValueError("patient_contact must not be empty")

    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=PROPOSAL_TTL_MINUTES)
    proposal_id = str(uuid.uuid4())

    try:
        conn.execute("BEGIN IMMEDIATE")

        slot = conn.execute(
            """
            SELECT slot_id, appointment_date, appointment_time, status
            FROM appointment_slots
            WHERE slot_id = ?
            """,
            (slot_id,),
        ).fetchone()

        if slot is None:
            raise ValueError("Appointment slot not found")

        slot_datetime = datetime.fromisoformat(
            f"{slot[1]}T{slot[2]}"
        )

        if slot_datetime <= datetime.now():
            raise ValueError("Appointment slot must be in the future")

        if slot[3] != "available":
            raise ValueError("Appointment slot is not available")

        conn.execute(
            """
            INSERT INTO booking_proposals (
                proposal_id,
                slot_id,
                patient_name,
                patient_contact,
                status,
                expires_at,
                user_id
            )
            VALUES (?, ?, ?, ?, 'pending', ?, ?)
            """,
            (
                proposal_id,
                slot_id,
                patient_name.strip(),
                patient_contact.strip(),
                expires_at.isoformat(),
                user_id,
            )
        )

        conn.commit()

        return {
            "proposal_id": proposal_id,
            "slot_id": slot_id,
            "appointment_date": slot[1],
            "appointment_time": slot[2],
            "status": "pending",
            "expires_at": expires_at.isoformat(),
            "requires_confirmation": True,
            "message": (
                "Proposal created. No appointment has been booked. "
                "Confirm within 10 minutes to proceed."
            ),
        }

    except Exception:
        conn.rollback()
        raise



def get_booking_proposal(
    conn: sqlite3.Connection,
    proposal_id: str,
    *,
    user_id: int | None = None,
) -> dict | None:
    """Retrieve a proposal, optionally restricted to its owner."""

    row = conn.execute(
        """
        SELECT proposal_id, slot_id, patient_name, patient_contact,
               status, expires_at, booking_reference, created_at, user_id
        FROM booking_proposals
        WHERE proposal_id = ?
          AND (? IS NULL OR user_id = ?)
        """,
        (proposal_id, user_id, user_id),
    ).fetchone()

    if row is None:
        return None

    return {
        "proposal_id": row[0],
        "slot_id": row[1],
        "patient_name": row[2],
        "patient_contact": row[3],
        "status": row[4],
        "expires_at": row[5],
        "booking_reference": row[6],
        "created_at": row[7],
        "user_id": row[8],
    }


def confirm_booking_proposal(
    conn: sqlite3.Connection,
    proposal_id: str,
        *,
    user_id: int | None = None,
) -> dict:
    """Confirm a pending proposal and book its slot atomically."""

    if not isinstance(proposal_id, str) or not proposal_id.strip():
        raise ValueError("proposal_id must not be empty")

    try:
        # Own the transaction so the appointment and proposal status
        # are committed or rolled back together.
        conn.execute("BEGIN IMMEDIATE")

        proposal = conn.execute(
            """
            SELECT slot_id, patient_name, patient_contact,
                status, expires_at, user_id
            FROM booking_proposals
            WHERE proposal_id = ?
            AND (? IS NULL OR user_id = ?)
            """,
            (proposal_id, user_id, user_id),
        ).fetchone()

        if proposal is None:
            raise ValueError("Booking proposal not found")

        slot_id, patient_name, patient_contact, status, expires_at, proposal_user_id = proposal

        if status != "pending":
            raise ValueError(
                f"Booking proposal is not pending (status: {status})"
            )

        expiry = datetime.fromisoformat(expires_at)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)

        if datetime.now(timezone.utc) >= expiry:
            conn.execute(
                """
                UPDATE booking_proposals
                SET status = 'expired'
                WHERE proposal_id = ? AND status = 'pending'
                """,
                (proposal_id,),
            )
            conn.commit()
            raise ValueError("Booking proposal has expired")

        appointment = book_appointment(
            conn,
            slot_id=slot_id,
            patient_name=patient_name,
            patient_contact=patient_contact,
            manage_transaction=False,
            user_id=proposal_user_id,
        )

        conn.execute(
            """
            UPDATE booking_proposals
            SET status = 'confirmed',
                booking_reference = ?
            WHERE proposal_id = ? AND status = 'pending'
            """,
            (appointment["booking_reference"], proposal_id),
        )

        if conn.execute("SELECT changes()").fetchone()[0] != 1:
            raise ValueError("Booking proposal could not be confirmed")

        conn.commit()

        return {
            "proposal_id": proposal_id,
            "booking_reference": appointment["booking_reference"],
            "appointment_id": appointment["appointment_id"],
            "slot_id": appointment["slot_id"],
            "appointment_date": appointment["appointment_date"],
            "appointment_time": appointment["appointment_time"],
            "status": "confirmed",
            "message": "Appointment successfully booked.",
        }

    except Exception:
        if conn.in_transaction:
            conn.rollback()
        raise
