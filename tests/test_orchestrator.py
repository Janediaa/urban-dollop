
import sqlite3

from datetime import date, timedelta

from src.agents.orchestrator import build_healthcare_graph
from src.database.models import create_tables


class FakeMedicalQAService:
    """Test double that avoids model loading and external API calls."""

    def ask(self, query: str, top_k: int = 3) -> dict:
        return {
            "answer": f"Test answer for: {query}",
            "top_k": top_k,
        }


def make_test_database(path):
    conn = sqlite3.connect(path)
    create_tables(conn)

    conn.execute(
        "INSERT INTO hospitals (hospital_name, city) VALUES (?, ?)",
        ("City Heart Hospital", "Delhi"),
    )
    hospital_id = conn.execute(
        "SELECT hospital_id FROM hospitals"
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO doctors (
            composite_doctor_id, doctor_name, doctor_type,
            experience_years, location, fees, city, hospital_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "DOC001", "Dr. Test Sharma", "Cardiologist",
            12, "Sector 18", 800, "Delhi", hospital_id,
        ),
    )
    conn.commit()
    conn.close()


def test_graph_routes_question_to_medical_service():
    graph = build_healthcare_graph()

    result = graph.invoke({
        "question": "What is hypertension?",
        "top_k": 5,
        "medical_qa_service": FakeMedicalQAService(),
    })

    assert result["result"]["answer"] == (
        "Test answer for: What is hypertension?"
    )
    assert result["result"]["top_k"] == 5


def test_graph_handles_empty_question():
    result = build_healthcare_graph().invoke({
        "question": "   ",
        "medical_qa_service": FakeMedicalQAService(),
    })

    assert result["error"] == "Question must not be empty."
    assert "result" not in result


def test_graph_handles_missing_medical_service():
    result = build_healthcare_graph().invoke({
        "question": "What is hypertension?",
    })

    assert result["error"] == "Medical Q&A service is unavailable."


def test_graph_searches_real_doctor_service(tmp_path):
    db_path = tmp_path / "healthcare_test.db"
    make_test_database(db_path)

    result = build_healthcare_graph().invoke({
        "question": "Find a cardiologist in Delhi under 1000",
        "db_path": str(db_path),
    })

    assert result["intent"] == "doctor_search"
    assert result["result"]["count"] == 1
    doctor = result["result"]["doctors"][0]
    assert doctor["doctor_name"] == "Dr. Test Sharma"
    assert doctor["hospital_name"] == "City Heart Hospital"
    assert result["result"]["filters"]["city"] == "Delhi"
    assert result["result"]["filters"]["max_fees"] == 1000.0


def test_graph_returns_zero_when_no_doctor_matches(tmp_path):
    db_path = tmp_path / "healthcare_test.db"
    make_test_database(db_path)

    result = build_healthcare_graph().invoke({
        "question": "Find a cardiologist in Mumbai",
        "db_path": str(db_path),
    })

    assert result["result"]["count"] == 0


def test_appointment_request_requires_database_path():
    result = build_healthcare_graph().invoke({
        "question": "Show available appointment slots",
    })

    assert result["intent"] == "appointment"
    assert result["error"] == "Database path is unavailable."


def test_graph_classifies_insurance_request():
    result = build_healthcare_graph().invoke({
        "question": "Check my health insurance coverage",
    })

    assert result["intent"] == "insurance"
    assert "not implemented yet" in result["error"]


def test_graph_classifies_triage_request():
    result = build_healthcare_graph().invoke({
        "question": "I have chest pain",
    })

    assert result["intent"] == "triage"
    assert "not implemented yet" in result["error"]



def test_appointment_agent_lists_available_slots(tmp_path):
    from src.database.models import create_tables

    db_path = tmp_path / "appointment_test.db"
    conn = sqlite3.connect(db_path)
    create_tables(conn)

    conn.execute(
        "INSERT INTO hospitals (hospital_name, city) VALUES (?, ?)",
        ("Test Hospital", "Delhi"),
    )
    hospital_id = conn.execute(
        "SELECT hospital_id FROM hospitals"
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO doctors (
            composite_doctor_id, doctor_name, doctor_type,
            experience_years, location, fees, city, hospital_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "DOC-001", "Dr Test", "Cardiology",
            10, "Delhi", 500, "Delhi", hospital_id,
        ),
    )

    doctor_id = conn.execute(
        "SELECT doctor_id FROM doctors WHERE composite_doctor_id = ?",
        ("DOC-001",),
    ).fetchone()[0]

    conn.execute(
        """
        INSERT INTO appointment_slots (
            doctor_id, appointment_date, appointment_time, status
        ) VALUES (?, ?, ?, 'available')
        """,
        (
            doctor_id,
            (date.today() + timedelta(days=1)).isoformat(),
            "10:30",
        ),
    )
    conn.commit()
    conn.close()

    result = build_healthcare_graph().invoke({
        "question": f"Show available slots for doctor ID {doctor_id}",
        "db_path": str(db_path),
    })

    assert result["intent"] == "appointment"
    assert result["result"]["count"] == 1
    assert result["result"]["slots"][0]["appointment_time"] == "10:30"
    assert (
        result["result"]["availability_source"]
        == "application_managed_database"
    )


def test_booking_proposal_does_not_modify_database(tmp_path):
    db_path = tmp_path / "booking_proposal_test.db"
    make_test_database(db_path)

    conn = sqlite3.connect(db_path)
    doctor_id = conn.execute(
        "SELECT doctor_id FROM doctors WHERE composite_doctor_id = ?",
        ("DOC001",),
    ).fetchone()[0]

    appointment_date = (date.today() + timedelta(days=1)).isoformat()
    cursor = conn.execute(
        """
        INSERT INTO appointment_slots (
            doctor_id, appointment_date, appointment_time, status
        ) VALUES (?, ?, ?, 'available')
        """,
        (doctor_id, appointment_date, "10:30"),
    )
    slot_id = cursor.lastrowid
    conn.commit()
    conn.close()

    result = build_healthcare_graph().invoke({
        "question": f"Book an appointment for slot ID {slot_id}",
        "db_path": str(db_path),
        "patient_name": "Test Patient",
        "patient_contact": "test-contact",
    })

    assert result["result"]["action"] == "booking_proposal"
    assert result["result"]["requires_confirmation"] is True

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
