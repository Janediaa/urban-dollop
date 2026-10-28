
"""LangGraph orchestration for Healthcare Navigator."""

import re
import sqlite3
from typing import Any, TypedDict
from datetime import date, datetime
import uuid
from langgraph.graph import END, START, StateGraph

from src.services.doctor_service import find_doctors
from src.services.appointment_service import (
    get_available_slots,
    book_appointment,
)


class HealthcareState(TypedDict, total=False):
    """State passed between nodes in a healthcare workflow."""

    question: str
    top_k: int
    medical_qa_service: Any
    db_path: str
    intent: str
    result: dict[str, Any]
    error: str

    # Appointment workflow
    action: str
    slot_id: int
    patient_name: str
    patient_contact: str
    confirmed: bool
    proposal_id: str
    user_id: str


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
        "symptom", "symptoms", "chest pain", "difficulty breathing",
        "can't breathe", "cannot breathe", "emergency", "urgent medical",
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

    graph.add_edge(START, "classify_intent")

    def route_by_intent(state: HealthcareState) -> str:
        if state.get("error"):
            return "end"
        intent = state.get("intent")
        if intent == "medical_question":
            return "medical"
        if intent == "doctor_search":
            return "doctor"
        if intent == "appointment":
            return "appointment"
        return "other"

    graph.add_conditional_edges(
        "classify_intent",
        route_by_intent,
        {
            "medical": "medical_rag_agent",
            "doctor": "doctor_search_agent",
            "appointment": "appointment_agent",
            "other": "not_implemented_agent",
            "end": END,
        },
    )

    graph.add_edge("medical_rag_agent", END)
    graph.add_edge("doctor_search_agent", END)
    graph.add_edge("not_implemented_agent", END)
    graph.add_edge("appointment_agent", END)

    return graph.compile()
