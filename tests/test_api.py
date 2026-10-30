
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
        # Register a test patient.
        registration = client.post(
            "/auth/register",
            json={
                "full_name": "Test Patient",
                "email": "patient@example.com",
                "password": "securepass123",
            },
        )
        assert registration.status_code == 201

        # Log in and obtain the JWT.
        login = client.post(
            "/auth/login",
            json={
                "email": "patient@example.com",
                "password": "securepass123",
            },
        )
        assert login.status_code == 200

        token = login.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Create a proposal as the authenticated patient.
        response = client.post(
            "/appointments/proposals",
            headers=headers,
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

        # Creating a proposal must not book the slot yet.
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

        # Confirm the proposal using the same authenticated patient.
        confirmation = client.post(
            "/appointments/proposals/confirm",
            headers=headers,
            json={"proposal_id": proposal["proposal_id"]},
        )

        assert confirmation.status_code == 200
        booking = confirmation.json()
        assert booking["status"] == "confirmed"
        assert booking["slot_id"] == slot_id

        # Confirming the same proposal again must fail.
        repeated = client.post(
            "/appointments/proposals/confirm",
            headers=headers,
            json={"proposal_id": proposal["proposal_id"]},
        )
        assert repeated.status_code == 409

        # Only one appointment should have been created.
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


def test_protected_appointment_endpoints_require_authentication(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "auth_required_test.db"
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
        proposal = client.post(
            "/appointments/proposals",
            json={
                "slot_id": slot_id,
                "patient_name": "Test Patient",
                "patient_contact": "test-contact",
            },
        )

        confirmation = client.post(
            "/appointments/proposals/confirm",
            json={"proposal_id": "unknown-proposal"},
        )

        lookup = client.get("/appointments/unknown-reference")

        cancellation = client.post(
            "/appointments/unknown-reference/cancel"
        )

    assert proposal.status_code == 401
    assert confirmation.status_code == 401
    assert lookup.status_code == 401
    assert cancellation.status_code == 401

    api.app.dependency_overrides.pop(api.get_db, None)


def test_patient_cannot_access_another_patients_appointment(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "ownership_test.db"
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

    def register_and_login(client, name, email):
        registration = client.post(
            "/auth/register",
            json={
                "full_name": name,
                "email": email,
                "password": "securepass123",
            },
        )
        assert registration.status_code == 201

        login = client.post(
            "/auth/login",
            json={
                "email": email,
                "password": "securepass123",
            },
        )
        assert login.status_code == 200

        token = login.json()["access_token"]
        return {"Authorization": f"Bearer {token}"}

    try:
        with TestClient(api.app) as client:
            patient_a = register_and_login(
                client, "Patient A", "patient-a@example.com"
            )
            patient_b = register_and_login(
                client, "Patient B", "patient-b@example.com"
            )

            # Patient A creates a proposal.
            proposal_response = client.post(
                "/appointments/proposals",
                headers=patient_a,
                json={
                    "slot_id": slot_id,
                    "patient_name": "Patient A",
                    "patient_contact": "contact-a",
                },
            )
            assert proposal_response.status_code == 200
            proposal_id = proposal_response.json()["proposal_id"]

            # Patient B must not confirm Patient A's proposal.
            other_confirmation = client.post(
                "/appointments/proposals/confirm",
                headers=patient_b,
                json={"proposal_id": proposal_id},
            )
            assert other_confirmation.status_code == 404

            # Patient A can confirm their own proposal.
            confirmation = client.post(
                "/appointments/proposals/confirm",
                headers=patient_a,
                json={"proposal_id": proposal_id},
            )
            assert confirmation.status_code == 200
            booking_reference = confirmation.json()["booking_reference"]

            # Patient B cannot retrieve Patient A's appointment.
            other_lookup = client.get(
                f"/appointments/{booking_reference}",
                headers=patient_b,
            )
            assert other_lookup.status_code == 404

            # Patient B cannot cancel Patient A's appointment.
            other_cancellation = client.post(
                f"/appointments/{booking_reference}/cancel",
                headers=patient_b,
            )
            assert other_cancellation.status_code == 404

            # Patient A's appointment must still be confirmed.
            conn = sqlite3.connect(db_path)
            try:
                appointment = conn.execute(
                    """
                    SELECT user_id, status
                    FROM appointments
                    WHERE booking_reference = ?
                    """,
                    (booking_reference,),
                ).fetchone()

                assert appointment is not None
                assert appointment[1] == "confirmed"
            finally:
                conn.close()
    finally:
        api.app.dependency_overrides.pop(api.get_db, None)


def test_create_slot_endpoint_is_disabled_outside_development(monkeypatch):
    monkeypatch.setattr(api, "APP_ENV", "production")

    with TestClient(api.app) as client:
        response = client.post(
            "/appointments/slots",
            json={
                "doctor_id": 1,
                "appointment_date": "2030-12-15",
                "appointment_time": "10:00",
            },
        )

    assert response.status_code == 404
    assert response.json()["detail"] == "Endpoint not available."


def test_medical_ask_requires_authentication():
    with TestClient(api.app) as client:
        response = client.post(
            "/medical/ask",
            json={"question": "Check my health insurance coverage"},
        )

    assert response.status_code == 401


def test_authenticated_user_can_check_insurance_coverage(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "insurance_api_test.db"
    setup_test_database(db_path)

    # Make both the API and insurance agent use the temporary database.
    monkeypatch.setattr(api, "DATABASE_PATH", db_path)

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

    try:
        with TestClient(api.app) as client:
            registration = client.post(
                "/auth/register",
                json={
                    "full_name": "Insurance Test User",
                    "email": "insurance-test@example.com",
                    "password": "securepass123",
                },
            )
            assert registration.status_code == 201

            login = client.post(
                "/auth/login",
                json={
                    "email": "insurance-test@example.com",
                    "password": "securepass123",
                },
            )
            assert login.status_code == 200

            headers = {
                "Authorization": (
                    f"Bearer {login.json()['access_token']}"
                )
            }

            conn = sqlite3.connect(db_path)
            try:
                user_id = conn.execute(
                    "SELECT user_id FROM users WHERE email = ?",
                    ("insurance-test@example.com",),
                ).fetchone()[0]

                conn.execute(
                    """
                    INSERT INTO insurance_policies (
                        user_id, policy_number, insurer_name, plan_name,
                        coverage_limit, deductible, copay_percentage,
                        valid_from, valid_until,
                        covered_services, excluded_services
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_id,
                        "POLICY-TEST-001",
                        "Test Insurer",
                        "Basic Health Plan",
                        500000,
                        5000,
                        10,
                        "2026-01-01",
                        "2026-12-31",
                        '["consultation", "blood test"]',
                        '["cosmetic surgery"]',
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            response = client.post(
                "/medical/ask",
                headers=headers,
                json={
                    "question": "Is consultation covered by my plan?"
                },
            )

        assert response.status_code == 200
        result = response.json()
        assert result["intent"] == "insurance"
        assert result["status"] == "covered"
        assert result["policy_number"] == "POLICY-TEST-001"

    finally:
        api.app.dependency_overrides.pop(api.get_db, None)


def test_user_cannot_access_another_users_insurance_policy(
    tmp_path, monkeypatch
):
    db_path = tmp_path / "insurance_isolation_test.db"
    setup_test_database(db_path)
    monkeypatch.setattr(api, "DATABASE_PATH", db_path)

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

    try:
        with TestClient(api.app) as client:
            def register_and_login(name, email):
                registration = client.post(
                    "/auth/register",
                    json={
                        "full_name": name,
                        "email": email,
                        "password": "securepass123",
                    },
                )
                assert registration.status_code == 201

                login = client.post(
                    "/auth/login",
                    json={
                        "email": email,
                        "password": "securepass123",
                    },
                )
                assert login.status_code == 200

                return {
                    "Authorization": (
                        f"Bearer {login.json()['access_token']}"
                    )
                }

            user_a_headers = register_and_login(
                "Insurance User A", "insurance-a@example.com"
            )
            user_b_headers = register_and_login(
                "Insurance User B", "insurance-b@example.com"
            )

            conn = sqlite3.connect(db_path)
            try:
                user_a_id = conn.execute(
                    "SELECT user_id FROM users WHERE email = ?",
                    ("insurance-a@example.com",),
                ).fetchone()[0]

                conn.execute(
                    """
                    INSERT INTO insurance_policies (
                        user_id, policy_number, insurer_name, plan_name,
                        covered_services, excluded_services
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        user_a_id,
                        "PRIVATE-POLICY-A",
                        "Test Insurer",
                        "Private Plan",
                        '["consultation"]',
                        "[]",
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            response = client.post(
                "/medical/ask",
                headers=user_b_headers,
                json={
                    "question": "Is consultation covered by my plan?"
                },
            )

        assert response.status_code == 200
        result = response.json()
        assert result["intent"] == "insurance"
        assert result["status"] == "unknown"
        assert result["policy_number"] is None
        assert "PRIVATE-POLICY-A" not in response.text

    finally:
        api.app.dependency_overrides.pop(api.get_db, None)

