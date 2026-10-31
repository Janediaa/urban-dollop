
import sqlite3

import pytest

from src.database.models import create_tables


def _create_legacy_appointments_database():
    """Build a database using the old appointments schema."""
    conn = sqlite3.connect(":memory:")

    # Create all supporting tables first.
    create_tables(conn)

    # Reconstruct the old appointments table.
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE appointments")

    conn.execute("""
        CREATE TABLE appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_reference TEXT NOT NULL UNIQUE,
            slot_id INTEGER NOT NULL UNIQUE,
            patient_name TEXT NOT NULL,
            patient_contact TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed'
                CHECK (status IN ('confirmed', 'cancelled')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            user_id INTEGER REFERENCES users(user_id),
            FOREIGN KEY (slot_id)
                REFERENCES appointment_slots(slot_id)
        )
    """)

    conn.execute("PRAGMA foreign_keys = ON")

    # Create a doctor and an appointment slot.
    conn.execute("""
        INSERT INTO hospitals (hospital_name, city)
        VALUES ('Migration Hospital', 'Delhi')
    """)

    conn.execute("""
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
        VALUES ('MIG-001', 'Dr Migration', 'General Medicine',
                5, 'Delhi', 500, 'Delhi', 1)
    """)

    doctor_id = conn.execute(
        "SELECT doctor_id FROM doctors WHERE composite_doctor_id = ?",
        ("MIG-001",),
    ).fetchone()[0]

    cursor = conn.execute("""
        INSERT INTO appointment_slots (
            doctor_id, appointment_date, appointment_time, status
        )
        VALUES (?, '2099-01-01', '10:00', 'available')
    """, (doctor_id,))

    slot_id = cursor.lastrowid

    # Insert an existing cancelled appointment.
    booking_reference = "LEGACY-BOOKING-001"

    conn.execute("""
        INSERT INTO appointments (
            booking_reference,
            slot_id,
            patient_name,
            patient_contact,
            status
        )
        VALUES (?, ?, ?, ?, 'cancelled')
    """, (
        booking_reference,
        slot_id,
        "Legacy Patient",
        "legacy-contact",
    ))

    # Preserve a proposal that references the old booking.
    conn.execute("""
        INSERT INTO booking_proposals (
            proposal_id,
            slot_id,
            patient_name,
            patient_contact,
            status,
            expires_at,
            booking_reference
        )
        VALUES (?, ?, ?, ?, 'confirmed', ?, ?)
    """, (
        "legacy-proposal-001",
        slot_id,
        "Legacy Patient",
        "legacy-contact",
        "2098-12-31T23:59:59+00:00",
        booking_reference,
    ))

    conn.commit()
    return conn, slot_id, booking_reference


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


def test_insurance_policies_table_is_created_with_required_columns():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)

        columns = {
            column[1]
            for column in conn.execute(
                "PRAGMA table_info(insurance_policies)"
            ).fetchall()
        }

        assert {
            "policy_id",
            "user_id",
            "policy_number",
            "insurer_name",
            "plan_name",
            "coverage_limit",
            "deductible",
            "copay_percentage",
            "valid_from",
            "valid_until",
            "covered_services",
            "excluded_services",
        }.issubset(columns)

    finally:
        conn.close()


def test_fresh_database_uses_partial_unique_appointment_index():
    conn = sqlite3.connect(":memory:")

    try:
        create_tables(conn)

        indexes = conn.execute(
            "PRAGMA index_list(appointments)"
        ).fetchall()

        index_names = {row[1] for row in indexes}

        assert "idx_one_confirmed_appointment_per_slot" in index_names

        index = next(
            row for row in indexes
            if row[1] == "idx_one_confirmed_appointment_per_slot"
        )

        assert index[2] == 1  # Unique
        assert index[4] == 1  # Partial

        table_sql = conn.execute("""
            SELECT sql
            FROM sqlite_master
            WHERE type = 'table' AND name = 'appointments'
        """).fetchone()[0]

        assert "slot_id INTEGER NOT NULL UNIQUE" not in table_sql

    finally:
        conn.close()


def test_legacy_appointment_migration_preserves_existing_records():
    conn, slot_id, booking_reference = (
        _create_legacy_appointments_database()
    )

    try:
        # Verify that the database starts with the old constraint.
        old_indexes = conn.execute(
            "PRAGMA index_list(appointments)"
        ).fetchall()

        old_unique_columns = []

        for index in old_indexes:
            if index[2] == 1 and index[4] == 0:
                columns = [
                    row[2]
                    for row in conn.execute(
                        f'PRAGMA index_info("{index[1]}")'
                    ).fetchall()
                ]
                old_unique_columns.append(columns)

        assert ["slot_id"] in old_unique_columns

        # Run the migration.
        create_tables(conn)

        appointment = conn.execute("""
            SELECT booking_reference, slot_id, patient_name, status
            FROM appointments
            WHERE booking_reference = ?
        """, (booking_reference,)).fetchone()

        proposal = conn.execute("""
            SELECT proposal_id, booking_reference, status
            FROM booking_proposals
            WHERE proposal_id = ?
        """, ("legacy-proposal-001",)).fetchone()

        assert appointment == (
            booking_reference,
            slot_id,
            "Legacy Patient",
            "cancelled",
        )

        assert proposal == (
            "legacy-proposal-001",
            booking_reference,
            "confirmed",
        )

        assert conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []

        indexes = conn.execute(
            "PRAGMA index_list(appointments)"
        ).fetchall()

        assert any(
            row[1] == "idx_one_confirmed_appointment_per_slot"
            and row[2] == 1
            and row[4] == 1
            for row in indexes
        )

    finally:
        conn.close()


def test_appointment_migration_is_idempotent():
    conn, _, booking_reference = (
        _create_legacy_appointments_database()
    )

    try:
        create_tables(conn)

        # Running it again must not damage the migrated database.
        create_tables(conn)

        appointment_count = conn.execute(
            "SELECT COUNT(*) FROM appointments"
        ).fetchone()[0]

        proposal_count = conn.execute(
            "SELECT COUNT(*) FROM booking_proposals"
        ).fetchone()[0]

        assert appointment_count == 1
        assert proposal_count == 1

        assert conn.execute(
            """
            SELECT booking_reference
            FROM appointments
            WHERE booking_reference = ?
            """,
            (booking_reference,),
        ).fetchone() is not None

        assert conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall() == []

    finally:
        conn.close()

