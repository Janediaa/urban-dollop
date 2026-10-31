
"""Manage application-owned appointment slots and bookings."""

import sqlite3
import uuid
from datetime import date, datetime, time


def create_appointment_slot(
    conn: sqlite3.Connection,
    doctor_id: int,
    appointment_date: str,
    appointment_time: str,
) -> dict:
    """Create an available slot for an existing doctor."""

    try:
        parsed_date = date.fromisoformat(appointment_date)
        parsed_time = time.fromisoformat(appointment_time)
    except (TypeError, ValueError) as exc:
        raise ValueError("Use a valid date (YYYY-MM-DD) and time (HH:MM)") from exc

    if parsed_date < date.today():
        raise ValueError("Appointment date cannot be in the past")

    if not isinstance(doctor_id, int) or isinstance(doctor_id, bool) or doctor_id <= 0:
        raise ValueError("doctor_id must be a positive integer")

    normalized_time = parsed_time.strftime("%H:%M")

    try:
        cursor = conn.execute(
            """
            INSERT INTO appointment_slots (
                doctor_id, appointment_date, appointment_time
            )
            VALUES (?, ?, ?)
            """,
            (doctor_id, parsed_date.isoformat(), normalized_time),
        )
        conn.commit()
    except sqlite3.IntegrityError as exc:
        conn.rollback()
        raise ValueError(
            "Slot could not be created. Check that the doctor exists "
            "and the slot does not already exist."
        ) from exc

    return {
        "slot_id": cursor.lastrowid,
        "doctor_id": doctor_id,
        "appointment_date": parsed_date.isoformat(),
        "appointment_time": normalized_time,
        "status": "available",
    }


def get_available_slots(
    conn: sqlite3.Connection,
    doctor_id: int,
    appointment_date: str | None = None,
) -> list[dict]:
    """Return available slots, optionally filtered by date."""

    query = """
        SELECT
            slot_id,
            doctor_id,
            appointment_date,
            appointment_time,
            status
        FROM appointment_slots
        WHERE doctor_id = ? AND status = 'available'
    """
    params: list = [doctor_id]

    if appointment_date is not None:
        try:
            appointment_date = date.fromisoformat(appointment_date).isoformat()
        except (TypeError, ValueError) as exc:
            raise ValueError("appointment_date must use YYYY-MM-DD") from exc

        query += " AND appointment_date = ?"
        params.append(appointment_date)

    query += " ORDER BY appointment_date, appointment_time"

    cursor = conn.execute(query, params)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def book_appointment(
    conn: sqlite3.Connection,
    slot_id: int,
    patient_name: str,
    patient_contact: str,
    *,
    manage_transaction: bool = True,
    user_id: int | None = None,
) -> dict:
    """Book an available slot without allowing duplicate active bookings."""

    if not isinstance(slot_id, int) or isinstance(slot_id, bool) or slot_id <= 0:
        raise ValueError("slot_id must be a positive integer")

    if not isinstance(patient_name, str) or not patient_name.strip():
        raise ValueError("patient_name must not be empty")

    if not isinstance(patient_contact, str) or not patient_contact.strip():
        raise ValueError("patient_contact must not be empty")

    try:
        if manage_transaction:
            conn.execute("BEGIN IMMEDIATE")

        slot_cursor = conn.execute(
            """
            SELECT slot_id, appointment_date, appointment_time, status
            FROM appointment_slots
            WHERE slot_id = ?
            """,
            (slot_id,),
        )
        slot = slot_cursor.fetchone()

        if slot is None:
            raise ValueError("Appointment slot not found")

        _, slot_date, slot_time, slot_status = slot

        try:
            slot_datetime = datetime.combine(
                date.fromisoformat(slot_date),
                time.fromisoformat(slot_time),
            )
        except ValueError as exc:
            raise ValueError("Stored appointment slot has an invalid date or time") from exc

        if slot_datetime <= datetime.now():
            raise ValueError("Appointment slot must be in the future")

        if slot_status != "available":
            raise ValueError("Appointment slot is not available")

        booking_reference = str(uuid.uuid4()).upper()

        cursor = conn.execute(
            """
            INSERT INTO appointments (
                booking_reference,
                slot_id,
                patient_name,
                patient_contact,
                user_id
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                booking_reference,
                slot_id,
                patient_name.strip(),
                patient_contact.strip(),
                user_id,
            ),
        )

        appointment_id = cursor.lastrowid



        slot_update = conn.execute(
            """
            UPDATE appointment_slots
            SET status = 'booked'
            WHERE slot_id = ? AND status = 'available'
            """,
            (slot_id,),
        )

        if slot_update.rowcount != 1:
            raise ValueError("Appointment slot is not available")


        if manage_transaction:
            conn.commit()

        return {
            "appointment_id": appointment_id,
            "booking_reference": booking_reference,
            "slot_id": slot_id,
            "appointment_date": slot_date,
            "appointment_time": slot_time,
            "patient_name": patient_name.strip(),
            "status": "confirmed",
        }

    except Exception:
        if manage_transaction:
            conn.rollback()
        raise


def get_appointment_by_reference(
    conn: sqlite3.Connection,
    booking_reference: str,
    *,
    user_id: int | None = None,
) -> dict | None:
    """Return a booking with its doctor and hospital details."""

    cursor = conn.execute(
        """
        SELECT
            a.appointment_id,
            a.booking_reference,
            a.patient_name,
            a.patient_contact,
            a.status,
            a.created_at,
            s.slot_id,
            s.appointment_date,
            s.appointment_time,
            d.composite_doctor_id,
            d.doctor_name,
            d.doctor_type,
            d.fees,
            h.hospital_name,
            h.city AS hospital_city
        FROM appointments AS a
        JOIN appointment_slots AS s ON s.slot_id = a.slot_id
        JOIN doctors AS d ON d.doctor_id = s.doctor_id
        LEFT JOIN hospitals AS h ON h.hospital_id = d.hospital_id
        WHERE a.booking_reference = ?
            AND (? IS NULL OR a.user_id = ?)
        """,
        (booking_reference, user_id, user_id),
    )

    row = cursor.fetchone()
    if row is None:
        return None

    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def cancel_appointment(
    conn: sqlite3.Connection,
    booking_reference: str,
    *,
    user_id: int | None = None,
) -> dict:
    """Cancel a confirmed booking and release its slot."""

    try:
        conn.execute("BEGIN IMMEDIATE")

        cursor = conn.execute(
            """
            SELECT appointment_id, slot_id, status
            FROM appointments
            WHERE booking_reference = ?
                AND (? IS NULL OR user_id = ?)
            """,
            (booking_reference, user_id, user_id),
        )
        appointment = cursor.fetchone()

        if appointment is None:
            raise ValueError("Appointment not found")

        appointment_id, slot_id, status = appointment

        if status != "confirmed":
            raise ValueError("Only confirmed appointments can be cancelled")

        conn.execute(
            """
            UPDATE appointments
            SET status = 'cancelled'
            WHERE appointment_id = ?
            """,
            (appointment_id,),
        )

        conn.execute(
            """
            UPDATE appointment_slots
            SET status = 'available'
            WHERE slot_id = ?
            """,
            (slot_id,),
        )

        conn.commit()

        return {
            "appointment_id": appointment_id,
            "booking_reference": booking_reference,
            "slot_id": slot_id,
            "status": "cancelled",
        }

    except Exception:
        conn.rollback()
        raise
