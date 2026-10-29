
import sqlite3

import pytest

from src.database.models import create_tables


def test_duplicate_composite_doctor_id_is_rejected():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)

        # Use no hospital association for both records.
        doctor = (
            "DOC001",
            "Dr. A",
            "Cardiology",
            10,
            "Delhi",
            1000,
            "Delhi",
            None,
        )

        insert_sql = """
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
        """

        conn.execute(insert_sql, doctor)

        # A second doctor with the same composite ID must fail.
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(insert_sql, doctor)

    finally:
        conn.close()


def test_doctor_can_have_null_hospital_id():
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
                "DOC002",
                "Dr. B",
                "Neurology",
                5,
                "Mumbai",
                800,
                "Mumbai",
                None,
            ),
        )

        row = conn.execute(
            """
            SELECT hospital_id
            FROM doctors
            WHERE composite_doctor_id = ?
            """,
            ("DOC002",),
        ).fetchone()

        assert row is not None
        assert row[0] is None

    finally:
        conn.close()


def test_booking_proposals_table_is_created():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)

        row = conn.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'booking_proposals'
            """
        ).fetchone()

        assert row is not None

        columns = {
            column[1]
            for column in conn.execute(
                "PRAGMA table_info(booking_proposals)"
            ).fetchall()
        }

        assert {
            "proposal_id",
            "slot_id",
            "patient_name",
            "patient_contact",
            "status",
            "expires_at",
            "booking_reference",
            "created_at",
        }.issubset(columns)

    finally:
        conn.close()


def test_booking_proposal_status_rejects_invalid_values():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)

        conn.execute(
            """
            INSERT INTO hospitals (hospital_name, city)
            VALUES (?, ?)
            """,
            ("Test Hospital", "Delhi"),
        )

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
                "DOC-TEST",
                "Dr. Test",
                "General Medicine",
                5,
                "Delhi",
                500,
                "Delhi",
                1,
            ),
        )

        doctor_id = conn.execute(
            "SELECT doctor_id FROM doctors WHERE composite_doctor_id = ?",
            ("DOC-TEST",),
        ).fetchone()[0]

        cursor = conn.execute(
            """
            INSERT INTO appointment_slots (
                doctor_id,
                appointment_date,
                appointment_time
            )
            VALUES (?, ?, ?)
            """,
            (doctor_id, "2099-01-01", "10:00"),
        )

        slot_id = cursor.lastrowid

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO booking_proposals (
                    proposal_id,
                    slot_id,
                    patient_name,
                    patient_contact,
                    status,
                    expires_at
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    "proposal-test",
                    slot_id,
                    "Test Patient",
                    "test-contact",
                    "invalid-status",
                    "2098-12-31T23:59:59",
                ),
            )

    finally:
        conn.close()

def test_users_table_is_created_with_required_columns():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)

        columns = {
            column[1]
            for column in conn.execute(
                "PRAGMA table_info(users)"
            ).fetchall()
        }

        assert {
            "user_id",
            "full_name",
            "email",
            "password_hash",
            "created_at",
        }.issubset(columns)

    finally:
        conn.close()


def test_user_email_must_be_unique():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)

        conn.execute(
            """
            INSERT INTO users (full_name, email, password_hash)
            VALUES (?, ?, ?)
            """,
            ("Test Patient", "patient@example.com", "test-hash"),
        )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO users (full_name, email, password_hash)
                VALUES (?, ?, ?)
                """,
                ("Another Patient", "patient@example.com", "another-hash"),
            )

    finally:
        conn.close()