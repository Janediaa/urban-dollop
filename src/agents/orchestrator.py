
"""LangGraph orchestration for Healthcare Navigator."""

import re
import sqlite3
from typing import Any, TypedDict
from datetime import date, datetime
import uuid
from langgraph.graph import END, START, StateGraph

from src.services.doctor_service import find_doctors
from src.services.hospital_service import find_hospitals
from src.services.appointment_service import (
    get_available_slots,
    book_appointment,
)
from src.services.insurance_service import assess_service_coverage
from src.database.connection import get_connection


class HealthcareState(TypedDict, total=False):
    """State passed between nodes in a healthcare workflow."""

    question: str
    top_k: int
    medical_qa_service: Any
    symptom_pipeline_service: Any
    db_path: str
    intent: str
    result: dict[str, Any]
    triage_answers: dict[str, str]
    error: str

    # Appointment workflow
    action: str
    slot_id: int
    patient_name: str
    patient_contact: str
    confirmed: bool
    proposal_id: str
    user_id: int


def classify_intent(state: HealthcareState) -> dict:
    """Classify a request using deterministic rules."""

    question = state.get("question", "").strip().lower()

    if not question:
        return {
            "intent": "invalid",
            "error": "Question must not be empty.",
        }

    # Explicit symptom/urgency requests take priority over general Q&A.
    triage_terms = (
        "symptom",
        "symptoms",
        "chest pain",
        "chest pressure",
        "difficulty breathing",
        "shortness of breath",
        "can't breathe",
        "cannot breathe",
        "severe bleeding",
        "unconscious",
        "not breathing",
        "signs of stroke",
        "face drooping",
        "sudden weakness",
        "fever",
        "cough",
        "cold",
        "sore throat",
        "fatigue",
        "rash",
        "itchy skin",
        "skin irritation",
        "palpitations",
        "heart racing",
        "irregular heartbeat",
        "frequent headaches",
        "recurring headaches",
        "numbness",
        "tingling",
    )

    if any(term in question for term in triage_terms):
        return {"intent": "triage"}

    if any(term in question for term in (
        "insurance", "coverage", "covered by my plan",
        "insurance plan", "health policy",
    )):
        return {"intent": "insurance"}

    if any(term in question for term in (
        "appointment", "available slot", "available slots",
        "book a slot", "cancel my booking", "cancel appointment",
        "booking reference",
    )):
        return {"intent": "appointment"}

    if any(term in question for term in (
        "hospital", "hospitals",
    )):
        return {"intent": "hospital_search"}

    if any(term in question for term in (
        "doctor", "doctors", "cardiologist", "dermatologist",
        "neurologist", "dentist", "orthopedic", "orthopaedic",
        "gynecologist", "gynaecologist", "pediatrician",
        "paediatrician", "physician", "surgeon",
    )):
        return {"intent": "doctor_search"}

    return {"intent": "medical_question"}


def medical_rag_agent(state: HealthcareState) -> dict:
    """Answer a medical question using the existing RAG service."""

    question = state.get("question", "").strip()
    if not question:
        return {"error": "Question must not be empty."}

    service = state.get("medical_qa_service")
    if service is None:
        return {"error": "Medical Q&A service is unavailable."}

    result = service.ask(
        query=question,
        top_k=state.get("top_k", 3),
    )
    return {"result": result}


def doctor_search_agent(state: HealthcareState) -> dict:
    """Search real doctor records using the existing service."""

    question = state.get("question", "").strip()
    if not question:
        return {"error": "Question must not be empty."}

    db_path = state.get("db_path")
    if not db_path:
        return {"error": "Database path is unavailable."}

    # Extract simple filters from natural-language requests.
    city_match = re.search(
        r"\b(?:in|at|near)\s+([a-zA-Z][a-zA-Z .'-]*?)(?="
        r"\s+(?:with|under|below|less than|over|above|more than|"
        r"and|who|having)\b|[,?.!]|$)",
        question,
        re.IGNORECASE,
    )
    city = city_match.group(1).strip() if city_match else None

    fees_match = re.search(
        r"\b(?:under|below|less than|at most|maximum|max)\s+"
        r"(?:₹|rs\.?\s*)?(\d+(?:\.\d+)?)",
        question,
        re.IGNORECASE,
    )
    max_fees = float(fees_match.group(1)) if fees_match else None

    experience_match = re.search(
        r"\b(?:at least|minimum|min|over|more than)\s+"
        r"(\d+)\s+years?\s+(?:of\s+)?experience\b",
        question,
        re.IGNORECASE,
    )
    min_experience = (
        int(experience_match.group(1)) if experience_match else None
    )

    specialties = (
        "cardiologist", "dermatologist", "neurologist", "dentist",
        "orthopedic", "orthopaedic", "gynecologist", "gynaecologist",
        "pediatrician", "paediatrician", "physician", "surgeon",
    )
    doctor_type = next(
        (specialty for specialty in specialties if specialty in question.lower()),
        None,
    )

    sort_by = "name"
    if any(term in question.lower() for term in (
        "lowest fee", "lowest fees", "cheapest", "least expensive",
    )):
        sort_by = "fees"
    elif any(term in question.lower() for term in (
        "most experienced", "highest experience", "most experience",
    )):
        sort_by = "experience"

    # Open a fresh connection for this graph invocation.
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        doctors = find_doctors(
            conn,
            city=city,
            doctor_type=doctor_type,
            min_experience=min_experience,
            max_fees=max_fees,
            sort_by=sort_by,
        )
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    finally:
        conn.close()

    return {
        "result": {
            "intent": "doctor_search",
            "count": len(doctors),
            "filters": {
                "city": city,
                "doctor_type": doctor_type,
                "min_experience": min_experience,
                "max_fees": max_fees,
                "sort_by": sort_by,
            },
            "doctors": doctors,
            "message": (
                f"Found {len(doctors)} matching doctor(s)."
                if doctors
                else "No doctors matched those filters. Try broadening your search."
            ),
        }
    }


def hospital_search_agent(state: HealthcareState) -> dict:
    """Search hospitals using an optional city filter."""

    question = state.get("question", "").strip()
    if not question:
        return {"error": "Question must not be empty."}

    db_path = state.get("db_path")
    if not db_path:
        return {"error": "Database path is unavailable."}

    city_match = re.search(
        r"\b(?:in|at|near)\s+([a-zA-Z][a-zA-Z .'-]*?)(?="
        r"\s+(?:with|under|below|less than|over|above|more than|"
        r"and|who|having)\b|[,?.!]|$)",
        question,
        re.IGNORECASE,
    )
    city = city_match.group(1).strip() if city_match else None

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        hospitals = find_hospitals(conn, city=city)
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    finally:
        conn.close()

    return {
        "result": {
            "intent": "hospital_search",
            "count": len(hospitals),
            "filters": {"city": city},
            "hospitals": hospitals,
            "message": (
                f"Found {len(hospitals)} matching hospital(s)."
                if hospitals
                else (
                    "No hospitals matched those filters. "
                    "Try another city or broaden your search."
                )
            ),
        }
    }




def appointment_agent(state: HealthcareState) -> dict:
    """Look up slots or prepare a booking proposal without booking."""

    question = state.get("question", "").strip()
    db_path = state.get("db_path")

    if not question:
        return {"error": "Question must not be empty."}

    if not db_path:
        return {"error": "Database path is unavailable."}

    question_lower = question.lower()

    # Booking is proposal-only in this stage. No database writes occur.
    booking_terms = ("book an appointment", "book appointment", "book a slot")
    is_booking_request = any(term in question_lower for term in booking_terms)

    lookup_terms = (
        "available slot",
        "available slots",
        "available appointment slot",
        "appointment slot",
        "appointment availability",
        "availability",
        "appointment times",
        "when can i book",
        "show slots",
    )

    if not is_booking_request and not any(
        term in question_lower for term in lookup_terms
    ):
        return {
            "error": (
                "Please ask to view available slots or request to book an appointment."
            )
        }

    doctor_match = re.search(
        r"\bdoctor\s+(?:id\s*)?(?:#\s*)?(\d+)\b",
        question,
        re.IGNORECASE,
    )
    composite_match = re.search(
        r"\bDOC[-_][A-Z0-9_-]+\b",
        question,
        re.IGNORECASE,
    )

    slot_match = re.search(
        r"\bslot\s+(?:id\s*)?(?:#\s*)?(\d+)\b",
        question,
        re.IGNORECASE,
    )

    date_match = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", question)
    appointment_date = date_match.group(1) if date_match else None

    if appointment_date:
        try:
            date.fromisoformat(appointment_date)
        except ValueError:
            return {"error": "Please provide a valid date in YYYY-MM-DD format."}

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    try:
        if slot_match and is_booking_request:
            slot = conn.execute(
                """
                SELECT s.slot_id, s.doctor_id, s.appointment_date,
                       s.appointment_time, s.status, d.doctor_name
                FROM appointment_slots AS s
                JOIN doctors AS d ON d.doctor_id = s.doctor_id
                WHERE s.slot_id = ?
                """,
                (int(slot_match.group(1)),),
            ).fetchone()

            if slot is None:
                return {"error": "Appointment slot not found."}

            if slot["status"] != "available":
                return {"error": "Appointment slot is not available."}

            patient_name = state.get("patient_name", "").strip()
            patient_contact = state.get("patient_contact", "").strip()

            if not patient_name or not patient_contact:
                return {
                    "result": {
                        "intent": "appointment",
                        "action": "booking_details_required",
                        "slot": dict(slot),
                        "message": (
                            "Please provide the patient's name and contact details "
                            "to prepare the booking proposal. No booking has been made."
                        ),
                    }
                }

            proposal_id = str(uuid.uuid4())

            return {
                "result": {
                    "intent": "appointment",
                    "action": "booking_proposal",
                    "proposal_id": proposal_id,
                    "slot": dict(slot),
                    "patient_name": patient_name,
                    "patient_contact": patient_contact,
                    "requires_confirmation": True,
                    "message": (
                        "Booking proposal prepared. Review the details and explicitly "
                        "confirm before the appointment is booked. No booking has been made."
                    ),
                }
            }

        if not doctor_match and not composite_match:
            return {
                "error": (
                    "Please provide a doctor ID, such as "
                    "'Show available slots for doctor ID 12'."
                )
            }

        if composite_match:
            doctor = conn.execute(
                """
                SELECT doctor_id, composite_doctor_id, doctor_name
                FROM doctors
                WHERE composite_doctor_id = ?
                """,
                (composite_match.group(0),),
            ).fetchone()
        else:
            doctor = conn.execute(
                """
                SELECT doctor_id, composite_doctor_id, doctor_name
                FROM doctors
                WHERE doctor_id = ?
                """,
                (int(doctor_match.group(1)),),
            ).fetchone()

        if doctor is None:
            return {"error": "Doctor not found."}

        slots = get_available_slots(
            conn,
            doctor_id=doctor["doctor_id"],
            appointment_date=appointment_date,
        )

        return {
            "result": {
                "intent": "appointment",
                "action": "list_available_slots",
                "doctor": {
                    "doctor_id": doctor["doctor_id"],
                    "composite_doctor_id": doctor["composite_doctor_id"],
                    "doctor_name": doctor["doctor_name"],
                },
                "appointment_date": appointment_date,
                "count": len(slots),
                "slots": slots,
                "message": (
                    f"Found {len(slots)} available slot(s)."
                    if slots
                    else "No available slots found for this doctor and date."
                ),
                "availability_source": "application_managed_database",
            }
        }

    except ValueError as exc:
        return {"error": str(exc)}
    finally:
        conn.close()


def triage_agent(state: HealthcareState) -> dict:
    """Provide cautious symptom guidance and optional doctor recommendations."""

    question = state.get("question", "").strip()
    question_lower = question.lower()

    if not question:
        return {"error": "Question must not be empty."}

    emergency_terms = (
        "chest pain",
        "chest pressure",
        "difficulty breathing",
        "shortness of breath",
        "can't breathe",
        "cannot breathe",
        "severe bleeding",
        "unconscious",
        "not breathing",
        "signs of stroke",
        "face drooping",
        "sudden weakness",
    )

    if any(term in question_lower for term in emergency_terms):
        return {
            "result": {
                "intent": "triage",
                "urgency_level": "emergency",
                "requires_emergency_care": True,
                "possible_specialty": None,
                "location": None,
                "recommended_doctors": [],
                "message": (
                    "Your symptoms may indicate a medical emergency. "
                    "Call your local emergency number or seek emergency "
                    "medical care now. Do not delay care while searching "
                    "for a doctor. This system cannot diagnose your condition."
                ),
                "requires_human_review": True,
            }
        }

    symptom_pipeline_service = state.get("symptom_pipeline_service")

    extracted_symptoms = (
        symptom_pipeline_service.extract_symptoms(question)
        if symptom_pipeline_service is not None
        else []
    )

    specialty_rules = {
        "cardiologist": (
            "palpitations",
            "heart racing",
            "irregular heartbeat",
        ),
        "dermatologist": (
            "rash",
            "itchy skin",
            "skin irritation",
        ),
        "neurologist": (
            "frequent headaches",
            "recurring headaches",
            "numbness",
            "tingling",
        ),
        "general physician": (
            "fever",
            "cough",
            "cold",
            "sore throat",
            "fatigue",
        ),
    }

    possible_specialty = next(
        (
            specialty
            for specialty, terms in specialty_rules.items()
            if any(term in question_lower for term in terms)
        ),
        None,
    )

    city_match = re.search(
        r"\b(?:in|at|near)\s+([a-zA-Z][a-zA-Z .'-]*?)(?="
        r"\s+(?:with|under|below|less than|over|above|more than|"
        r"and|who|having)\b|[,?.!]|$)",
        question,
        re.IGNORECASE,
    )
    city = city_match.group(1).strip() if city_match else None

    recommended_doctors = []

    db_path = state.get("db_path")

    if possible_specialty and city and db_path:
        doctor_type = (
            "physician"
            if possible_specialty == "general physician"
            else possible_specialty
        )

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row

        try:
            recommended_doctors = find_doctors(
                conn,
                city=city,
                doctor_type=doctor_type,
            )[:3]
        finally:
            conn.close()

    
    follow_up_questions = []

    if possible_specialty == "general physician":
        if "fever" in question_lower:
            follow_up_questions.extend([
                "How long have you had the fever?",
                "Have you measured your temperature? If yes, what was it?",
            ])

        if "cough" in question_lower:
            follow_up_questions.append(
                "How long have you had the cough, and is it getting worse?"
            )

        follow_up_questions.append(
            "Are you experiencing any severe or rapidly worsening symptoms?"
        )

    elif possible_specialty == "dermatologist":
        follow_up_questions = [
            "When did the skin symptoms start?",
            "Is the rash spreading, painful, or accompanied by fever?",
        ]

    elif possible_specialty == "neurologist":
        follow_up_questions = [
            "When did the symptoms start, and how often do they occur?",
            "Are the symptoms sudden, severe, or getting worse?",
        ]

    elif possible_specialty == "cardiologist":
        follow_up_questions = [
            "When did the symptoms start, and how long do they last?",
            "Are you experiencing chest pain, difficulty breathing, "
            "fainting, or sudden weakness?",
        ]

    reported_symptoms = [
        symptom
        for symptom in (
            "fever",
            "cough",
            "cold",
            "sore throat",
            "fatigue",
            "rash",
            "itchy skin",
            "skin irritation",
            "palpitations",
            "heart racing",
            "irregular heartbeat",
            "frequent headaches",
            "recurring headaches",
            "numbness",
            "tingling",
        )
        if symptom in question_lower
    ]

    
    
    triage_answers = state.get("triage_answers") or {}

    duration = str(triage_answers.get("duration") or "").strip()
    severity = str(triage_answers.get("severity") or "").strip()
    progression = str(triage_answers.get("progression") or "").strip()

    worsening_warning = progression.lower() in {
        "worsening",
        "getting worse",
        "rapidly worsening",
    }

    severe_warning = severity.lower() in {
        "severe",
        "very severe",
    }

    answered_fields = {
        "duration": duration,
        "severity": severity,
        "progression": progression,
    }

    unanswered_fields = [
        field
        for field, value in answered_fields.items()
        if not value
    ]


    return {
        "result": {
            "intent": "triage",
            "urgency_level": "undetermined",
            "requires_emergency_care": False,
            "possible_specialty": possible_specialty,
            "location": city,
            "recommended_doctors": recommended_doctors,
            "follow_up_questions": follow_up_questions,
                        
            "summary": {
                "reported_symptoms": reported_symptoms,
                "extracted_symptoms": extracted_symptoms,
                "duration": duration or None,
                "severity": severity or None,
                "progression": progression or None,
                "unanswered_fields": unanswered_fields,
                "unanswered_questions": [
                    question
                    for field, question in (
                        (
                            "duration",
                            "How long have you had these symptoms?",
                        ),
                        (
                            "severity",
                            "How severe are the symptoms?",
                        ),
                        (
                            "progression",
                            "Are the symptoms getting better, staying the same, or getting worse?",
                        ),
                    )
                    if field in unanswered_fields
                ],
            },

            
            
            
            "message": (
                "You reported severe or worsening symptoms. Seek prompt "
                "medical assessment. If symptoms are rapidly worsening, "
                "you have trouble breathing, chest pain, fainting, or "
                "another potentially life-threatening symptom, seek "
                "emergency care now. Do not wait for this tool."
                if worsening_warning or severe_warning
                else
                "This is initial guidance, not a diagnosis. The available "
                "information is insufficient to reliably determine "
                "urgency. Seek professional medical advice, and seek "
                "emergency care immediately if severe or rapidly "
                "worsening symptoms occur."
            ),



            "requires_human_review": True,
        }
    }


def insurance_agent(state: HealthcareState) -> dict:
    """Assess a service against the authenticated user's stored policy."""

    question = state.get("question", "").strip()
    user_id = state.get("user_id")
    db_path = state.get("db_path")

    if not question:
        return {"error": "Question must not be empty."}

    if isinstance(user_id, bool) or not isinstance(user_id, int) or user_id <= 0:
        return {"error": "A valid authenticated user is required for insurance queries."}

    if not db_path:
        return {"error": "Database path is unavailable."}

    # Extract the service being asked about from common question patterns.
    import re

    patterns = (
        r"\bis\s+(.+?)\s+covered\b",
        r"\bdoes\s+my\s+(?:insurance|plan|policy)\s+cover\s+(.+?)[?.!]*$",
        r"\bcoverage\s+for\s+(.+?)[?.!]*$",
        r"\bwill\s+my\s+(?:insurance|plan|policy)\s+cover\s+(.+?)[?.!]*$",
    )

    service_name = None
    for pattern in patterns:
        match = re.search(pattern, question, re.IGNORECASE)
        if match:
            service_name = match.group(1).strip(" ?.!").strip()
            break

    if not service_name:
        return {
            "result": {
                "intent": "insurance",
                "status": "unknown",
                "message": (
                    "Please name the medical service you want to check, "
                    "for example: 'Is consultation covered by my plan?'"
                ),
            }
        }

    conn = get_connection(db_path)
    try:
        assessment = assess_service_coverage(
            conn,
            user_id=user_id,
            service_name=service_name,
        )
    except (TypeError, ValueError) as exc:
        return {"error": str(exc)}
    finally:
        conn.close()

    return {
        "result": {
            "intent": "insurance",
            "service_name": service_name,
            **assessment,
        }
    }



def not_implemented_agent(state: HealthcareState) -> dict:
    """Clearly report workflows that have not been implemented yet."""

    intent = state.get("intent", "unknown")
    return {
        "error": (
            f"The '{intent}' workflow is not implemented yet."
            if intent != "unknown"
            else "This workflow is not implemented yet."
        )
    }


def build_healthcare_graph():
    """Build and compile the healthcare intent-routing graph."""

    graph = StateGraph(HealthcareState)

    graph.add_node("classify_intent", classify_intent)
    graph.add_node("medical_rag_agent", medical_rag_agent)
    graph.add_node("doctor_search_agent", doctor_search_agent)
    graph.add_node("not_implemented_agent", not_implemented_agent)
    graph.add_node("appointment_agent", appointment_agent)
    graph.add_node("hospital_search_agent", hospital_search_agent)
    graph.add_node("triage_agent", triage_agent)
    graph.add_node("insurance_agent", insurance_agent)

    graph.add_edge(START, "classify_intent")

    def route_by_intent(state: HealthcareState) -> str:
        if state.get("error"):
            return "end"
        intent = state.get("intent")
        if intent == "medical_question":
            return "medical"
        if intent == "doctor_search":
            return "doctor"
        if intent == "hospital_search":
            return "hospital"
        if intent == "appointment":
            return "appointment"
        if intent == "triage":
            return "triage"
        if intent == "insurance":
            return "insurance"
        return "other"

    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "medical": "medical_rag_agent",
            "doctor": "doctor_search_agent",
            "hospital": "hospital_search_agent",
            "appointment": "appointment_agent",
            "triage": "triage_agent",
            "insurance": "insurance_agent",
            "other": "not_implemented_agent",
            "end": END,
        },
    )

    graph.add_edge("medical_rag_agent", END)
    graph.add_edge("doctor_search_agent", END)
    graph.add_edge("hospital_search_agent", END)
    graph.add_edge("not_implemented_agent", END)
    graph.add_edge("appointment_agent", END)
    graph.add_edge("triage_agent", END)
    graph.add_edge("insurance_agent", END)
    

    return graph.compile()
