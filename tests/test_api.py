
import sqlite3
from datetime import date, timedelta

from fastapi.testclient import TestClient

import src.api.app as api
from src.database.models import create_tables


def setup_test_database(path):
    conn = sqlite3.connect(path)
    conn.execute("PRAGMA foreign_keys = ON")

    try:
        create_tables(conn)

        # Verify the shared schema includes booking proposals.
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            ).fetchall()
        }
        assert "booking_proposals" in tables

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
            (
                "DOC-API-TEST",
                "Dr. API Test",
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
            ("DOC-API-TEST",),
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
        conn.commit()
        return slot_id

    finally:
        conn.close()


def test_proposal_api_and_confirmation_flow(tmp_path, monkeypatch):
    db_path = tmp_path / "api_test.db"
    slot_id = setup_test_database(db_path)

    def override_get_db():
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    monkeypatch.setitem(
        api.app.dependency_overrides,
        api.get_db,
        override_get_db,
    )

    with TestClient(api.app) as client:
        response = client.post(
            "/appointments/proposals",
            json={
                "slot_id": slot_id,
                "patient_name": "Test Patient",
                "patient_contact": "test-contact",
            },
        )

        assert response.status_code == 200
        proposal = response.json()
        assert proposal["status"] == "pending"
        assert proposal["requires_confirmation"] is True

        conn = sqlite3.connect(db_path)
        slot_status = conn.execute(
            "SELECT status FROM appointment_slots WHERE slot_id = ?",
            (slot_id,),
        ).fetchone()[0]
        appointment_count = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE slot_id = ?",
            (slot_id,),
        ).fetchone()[0]
        conn.close()

        assert slot_status == "available"
        assert appointment_count == 0

        confirmation = client.post(
            "/appointments/proposals/confirm",
            json={"proposal_id": proposal["proposal_id"]},
        )

        assert confirmation.status_code == 200
        booking = confirmation.json()
        assert booking["status"] == "confirmed"
        assert booking["slot_id"] == slot_id

        repeated = client.post(
            "/appointments/proposals/confirm",
            json={"proposal_id": proposal["proposal_id"]},
        )
        assert repeated.status_code == 409

        conn = sqlite3.connect(db_path)
        appointment_count = conn.execute(
            "SELECT COUNT(*) FROM appointments WHERE slot_id = ?",
            (slot_id,),
        ).fetchone()[0]
        conn.close()

        assert appointment_count == 1


def test_direct_booking_endpoint_is_disabled():
    with TestClient(api.app) as client:
        response = client.post(
            "/appointments",
            json={
                "slot_id": 1,
                "patient_name": "Test Patient",
                "patient_contact": "test-contact",
            },
        )

    assert response.status_code == 409
