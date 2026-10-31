
import sqlite3

from datetime import date, timedelta

from src.agents.orchestrator import build_healthcare_graph
from src.database.models import create_tables


class FakeIntentClassificationService:
    """Test double for contextual intent classification."""

    def __init__(self, classification):
        self.classification = classification
        self.called_with = []

    def classify(self, question):
        self.called_with.append(question)
        return self.classification

class FakeMedicalQAService:
    """Test double that avoids model loading and external API calls."""

    def ask(self, query: str, top_k: int = 3) -> dict:
        return {
            "answer": f"Test answer for: {query}",
            "top_k": top_k,
        }

class FakeSymptomPipelineService:
    """Test double for symptom extraction."""

    def __init__(self, return_empty: bool = False):
        self.called_with = []
        self.return_empty = return_empty

    def extract_symptoms(self, text: str) -> list[dict]:
        self.called_with.append(text)

        if self.return_empty:
            return []

        return [
            {
                "symptom": "headache",
                "status": "present",
                "temporality": "current",
                "experiencer": "self",
                "resolution_status": "unknown",
                "duration": None,
                "evidence": text,
            }
        ]    

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
            "DOC001",
            "Dr. Test Sharma",
            "Cardiologist",
            12,
            "Sector 18",
            800,
            "Delhi",
            hospital_id,
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

    assert result["intent"] == "medical_question"

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
    assert "error" in result
    assert "authenticated user" in result["error"].lower()


def test_graph_routes_chest_pain_to_emergency_triage():
    result = build_healthcare_graph().invoke({
        "question": "I have chest pain",
    })

    assert result["intent"] == "triage"
    assert "result" in result
    assert result["result"]["urgency_level"] == "emergency"
    assert result["result"]["requires_emergency_care"] is True
    assert result["result"]["recommended_doctors"] == []



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


def test_graph_searches_hospitals_in_requested_city(tmp_path):
    db_path = tmp_path / "healthcare_test.db"
    make_test_database(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO hospitals (hospital_name, city) VALUES (?, ?)",
        ("Metro Hospital", "Noida"),
    )
    conn.commit()
    conn.close()

    result = build_healthcare_graph().invoke({
        "question": "Find hospitals in Delhi",
        "db_path": str(db_path),
    })

    assert result["intent"] == "hospital_search"
    assert result["result"]["count"] == 1
    assert result["result"]["hospitals"][0]["hospital_name"] == (
        "City Heart Hospital"
    )
    assert result["result"]["filters"]["city"] == "Delhi"


def test_graph_returns_zero_when_no_hospital_matches_city(tmp_path):
    db_path = tmp_path / "healthcare_test.db"
    make_test_database(db_path)

    result = build_healthcare_graph().invoke({
        "question": "Find hospitals in Mumbai",
        "db_path": str(db_path),
    })

    assert result["intent"] == "hospital_search"
    assert result["result"]["count"] == 0
    assert result["result"]["hospitals"] == []
    assert "No hospitals matched" in result["result"]["message"]


def test_graph_returns_all_hospitals_when_city_is_not_specified(
    tmp_path,
):
    db_path = tmp_path / "healthcare_test.db"
    make_test_database(db_path)

    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT INTO hospitals (hospital_name, city) VALUES (?, ?)",
        ("Metro Hospital", "Noida"),
    )
    conn.commit()
    conn.close()

    result = build_healthcare_graph().invoke({
        "question": "Show all hospitals",
        "db_path": str(db_path),
    })

    assert result["intent"] == "hospital_search"
    assert result["result"]["count"] == 2
    assert {
        hospital["hospital_name"]
        for hospital in result["result"]["hospitals"]
    } == {"City Heart Hospital", "Metro Hospital"}

def test_graph_triages_fever_with_general_physician_guidance():
    result = build_healthcare_graph().invoke({
        "question": "I have had a fever and cough",
    })

    assert result["intent"] == "triage"
    assert "result" in result

    triage = result["result"]
    assert triage["urgency_level"] == "undetermined"
    assert triage["requires_emergency_care"] is False
    assert triage["possible_specialty"] == "general physician"
    assert triage["requires_human_review"] is True
    assert "not a diagnosis" in triage["message"]


def test_triage_recommends_matching_doctors_in_user_city(tmp_path):
    db_path = tmp_path / "triage_test.db"
    make_test_database(db_path)

    conn = sqlite3.connect(db_path)

    hospital_id = conn.execute(
        "SELECT hospital_id FROM hospitals LIMIT 1"
    ).fetchone()[0]

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
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "DOC002",
            "Dr. General Physician",
            "General Physician",
            8,
            "Central Delhi",
            500,
            "Delhi",
            hospital_id,
        ),
    )

    conn.commit()
    conn.close()

    result = build_healthcare_graph().invoke({
        "question": "I have a fever and cough in Delhi",
        "db_path": str(db_path),
    })

    assert result["intent"] == "triage"
    triage = result["result"]

    assert triage["possible_specialty"] == "general physician"
    assert triage["location"] == "Delhi"
    assert len(triage["recommended_doctors"]) == 1
    assert (
        triage["recommended_doctors"][0]["doctor_name"]
        == "Dr. General Physician"
    )


def test_triage_does_not_recommend_unmatched_specialty(tmp_path):
    db_path = tmp_path / "triage_test.db"
    make_test_database(db_path)

    result = build_healthcare_graph().invoke({
        "question": "I have a fever and cough in Delhi",
        "db_path": str(db_path),
    })

    assert result["intent"] == "triage"

    triage = result["result"]

    assert triage["possible_specialty"] == "general physician"
    assert triage["location"] == "Delhi"
    assert triage["recommended_doctors"] == []


def test_triage_asks_follow_up_questions_for_fever():
    result = build_healthcare_graph().invoke({
        "question": "I have had a fever and cough",
    })

    assert result["intent"] == "triage"
    triage = result["result"]

    assert triage["urgency_level"] == "undetermined"
    assert triage["follow_up_questions"]
    assert any(
        "long" in question.lower()
        or "duration" in question.lower()
        for question in triage["follow_up_questions"]
    )
    assert any(
        "temperature" in question.lower()
        or "severe" in question.lower()
        for question in triage["follow_up_questions"]
    )
    assert triage["summary"]["reported_symptoms"] == [
        "fever",
        "cough",
    ]


def test_triage_records_follow_up_answers():
    result = build_healthcare_graph().invoke({
        "question": "I have a fever and cough",
        "triage_answers": {
            "duration": "3 days",
            "severity": "moderate",
            "progression": "getting worse",
        },
    })

    triage = result["result"]

    assert triage["summary"]["duration"] == "3 days"
    assert triage["summary"]["severity"] == "moderate"
    assert triage["summary"]["progression"] == "getting worse"


def test_triage_marks_answered_questions_as_resolved():
    result = build_healthcare_graph().invoke({
        "question": "I have a fever and cough",
        "triage_answers": {
            "duration": "3 days",
            "severity": "moderate",
            "progression": "stable",
        },
    })

    summary = result["result"]["summary"]

    assert summary["duration"] == "3 days"
    assert summary["severity"] == "moderate"
    assert summary["progression"] == "stable"
    assert summary["unanswered_questions"] == []


def test_triage_warns_when_severity_is_severe():
    result = build_healthcare_graph().invoke({
        "question": "I have a fever and cough",
        "triage_answers": {
            "duration": "3 days",
            "severity": "severe",
            "progression": "stable",
        },
    })

    triage = result["result"]

    assert triage["urgency_level"] == "undetermined"
    assert triage["requires_emergency_care"] is False
    assert "prompt medical assessment" in triage["message"]


def test_triage_warns_when_symptoms_are_worsening():
    result = build_healthcare_graph().invoke({
        "question": "I have a fever and cough",
        "triage_answers": {
            "duration": "3 days",
            "severity": "moderate",
            "progression": "worsening",
        },
    })

    triage = result["result"]

    assert triage["urgency_level"] == "undetermined"
    assert triage["requires_emergency_care"] is False
    assert "prompt medical assessment" in triage["message"]

def test_triage_includes_extracted_symptoms():
    symptom_service = FakeSymptomPipelineService()

    result = build_healthcare_graph().invoke({
        "question": "I have symptoms. My head has been pounding",
        "symptom_pipeline_service": symptom_service,
    })

    triage = result["result"]

    assert symptom_service.called_with == [
        "I have symptoms. My head has been pounding"
    ]
    assert triage["summary"]["extracted_symptoms"] == [
        {
            "symptom": "headache",
            "status": "present",
            "temporality": "current",
            "experiencer": "self",
            "resolution_status": "unknown",
            "duration": None,
            "evidence": "I have symptoms. My head has been pounding",
        }
    ]

def test_emergency_triage_skips_symptom_extraction():
    symptom_service = FakeSymptomPipelineService()

    result = build_healthcare_graph().invoke({
        "question": "I have severe chest pain",
        "symptom_pipeline_service": symptom_service,
    })

    triage = result["result"]
    assert result["intent"] == "triage"

    assert triage["urgency_level"] == "emergency"
    assert triage["requires_emergency_care"] is True
    assert symptom_service.called_with == []

def test_graph_routes_semantic_symptom_to_triage():
    symptom_service = FakeSymptomPipelineService()

    result = build_healthcare_graph().invoke({
        "question": "My head has been pounding",
        "symptom_pipeline_service": symptom_service,
    })

    assert result["intent"] == "triage"
    assert symptom_service.called_with == [
        "My head has been pounding"
    ]
    assert result["result"]["summary"]["extracted_symptoms"][0][
        "symptom"
    ] == "headache"

def test_graph_keeps_general_symptom_question_in_medical_rag():
    symptom_service = FakeSymptomPipelineService()
    medical_service = FakeMedicalQAService()

    result = build_healthcare_graph().invoke({
        "question": "Why do people experience dizziness?",
        "symptom_pipeline_service": symptom_service,
        "medical_qa_service": medical_service,
    })

    assert result["intent"] == "medical_question"
    assert result["result"]["answer"] == (
        "Test answer for: Why do people experience dizziness?"
    )
    assert symptom_service.called_with == []

def test_general_question_about_frequent_headaches_routes_to_medical_rag():
    result = build_healthcare_graph().invoke({
        "question": "What causes frequent headaches?",
    })

    assert result["intent"] == "medical_question"


def test_general_question_about_symptoms_routes_to_medical_rag():
    result = build_healthcare_graph().invoke({
        "question": "What are the symptoms of diabetes?",
    })

    assert result["intent"] == "medical_question"


def test_personal_fever_report_routes_to_triage():
    result = build_healthcare_graph().invoke({
        "question": "I have had a fever and cough",
    })

    assert result["intent"] == "triage"


def test_personal_headache_report_routes_to_triage():
    result = build_healthcare_graph().invoke({
        "question": "I've been experiencing frequent headaches",
    })

    assert result["intent"] == "triage"


def test_hypothetical_chest_pain_question_does_not_trigger_emergency_triage():
    result = build_healthcare_graph().invoke({
        "question": "What happens when someone experiences chest pain?",
    })

    assert result["intent"] == "medical_question"



def test_hypothetical_chest_pain_question_routes_to_medical_rag():
    result = build_healthcare_graph().invoke({
        "question": "What happens when someone experiences chest pain?",
        "medical_qa_service": FakeMedicalQAService(),
    })

    assert result["intent"] == "medical_question"


def test_stroke_warning_signs_question_routes_to_medical_rag():
    result = build_healthcare_graph().invoke({
        "question": "What are the warning signs of a stroke?",
        "medical_qa_service": FakeMedicalQAService(),
    })

    assert result["intent"] == "medical_question"


def test_other_person_current_emergency_routes_to_emergency_triage():
    result = build_healthcare_graph().invoke({
        "question": "My father has chest pain",
    })

    assert result["intent"] == "triage"
    assert result["result"]["urgency_level"] == "emergency"
    assert result["result"]["requires_emergency_care"] is True


def test_person_nearby_with_breathing_difficulty_routes_to_emergency():
    result = build_healthcare_graph().invoke({
        "question": "Someone near me is having difficulty breathing",
    })

    assert result["intent"] == "triage"
    assert result["result"]["requires_emergency_care"] is True


def test_historical_chest_pain_is_not_automatically_emergency():
    classifier = FakeIntentClassificationService({
        "intent": "symptom_report",
        "subject": "self",
        "temporality": "historical",
        "emergency_signal": False,
        "confidence": 0.98,
    })

    result = build_healthcare_graph().invoke({
        "question": "I had severe chest pain yesterday",
        "intent_classification_service": classifier,
    })

    assert result["intent"] == "triage"
    assert result["result"]["requires_emergency_care"] is False


def test_ambiguous_other_person_symptom_uses_classifier():
    classifier = FakeIntentClassificationService({
        "intent": "symptom_report",
        "subject": "other_person",
        "temporality": "current",
        "emergency_signal": False,
        "confidence": 0.95,
    })

    result = build_healthcare_graph().invoke({
        "question": "My mother has been experiencing dizziness",
        "intent_classification_service": classifier,
    })

    assert result["intent"] == "triage"
    assert result["subject"] == "other_person"
    assert result["temporality"] == "current"
    assert result["result"]["requires_emergency_care"] is False


def test_ambiguous_general_question_uses_classifier():
    classifier = FakeIntentClassificationService({
        "intent": "medical_question",
        "subject": "general",
        "temporality": "unknown",
        "emergency_signal": False,
        "confidence": 0.97,
    })

    result = build_healthcare_graph().invoke({
        "question": "Can recurring headaches have different causes?",
        "medical_qa_service": FakeMedicalQAService(),
        "intent_classification_service": classifier,
    })

    assert result["intent"] == "medical_question"
    assert len(classifier.called_with) == 1


def test_hypothetical_emergency_classification_is_not_accepted():
    classifier = FakeIntentClassificationService({
        "intent": "medical_question",
        "subject": "hypothetical",
        "temporality": "unknown",
        "emergency_signal": False,
        "confidence": 0.99,
    })

    result = build_healthcare_graph().invoke({
        "question": "What should someone do if they have chest pain?",
        "medical_qa_service": FakeMedicalQAService(),
        "intent_classification_service": classifier,
    })

    assert result["intent"] == "medical_question"

def test_classifier_failure_routes_to_clarification():
    classifier = FakeIntentClassificationService(None)

    result = build_healthcare_graph().invoke({
        "question": "Something has been feeling unusual lately.",
        "intent_classification_service": classifier,
    })

    assert result["intent"] == "needs_clarification"
    assert result["result"]["intent"] == "needs_clarification"
    assert "clarification_question" in result["result"]
    assert len(classifier.called_with) == 1


def test_clarification_does_not_trigger_emergency():
    classifier = FakeIntentClassificationService(None)

    result = build_healthcare_graph().invoke({
        "question": "I have been feeling strange recently.",
        "intent_classification_service": classifier,
    })

    assert result["intent"] == "needs_clarification"
    assert result["result"].get("requires_emergency_care") is not True

def test_clarification_agent_returns_structured_response():
    from src.agents.orchestrator import clarification_agent

    result = clarification_agent({
        "question": "Something feels wrong.",
        "intent": "needs_clarification",
    })

    assert result["result"]["intent"] == "needs_clarification"
    assert result["result"]["requires_human_review"] is True
    assert result["result"]["clarification_question"]

