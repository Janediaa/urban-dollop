import sqlite3
from pathlib import Path
from typing import Literal

import time
import traceback

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

from contextlib import asynccontextmanager

from src.services.medical_qa_service import MedicalQAService

from src.database.connection import get_connection
from src.database.repository import get_doctor_with_hospital
from src.services.doctor_service import find_doctors
from src.services.appointment_service import (
    create_appointment_slot,
    get_available_slots,
    book_appointment,
    get_appointment_by_reference,
    cancel_appointment,
)
from src.agents.orchestrator import build_healthcare_graph

from src.services.booking_proposal_service import (
    create_booking_proposal,
    confirm_booking_proposal,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATABASE_PATH = PROJECT_ROOT / "data" / "healthcare.db"

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize shared AI resources once when the API starts."""
    app.state.medical_qa_service = MedicalQAService()
    app.state.healthcare_graph = build_healthcare_graph()

    yield

    app.state.medical_qa_service = None
    app.state.healthcare_graph = None

app = FastAPI(
    title="Healthcare Navigator API",
    description=(
        "Backend API for medical information, doctor discovery, "
        "and appointment management."
    ),
    version="0.1.0",
    lifespan=lifespan,
)


def get_db():
    """Provide a database connection for one request."""
    conn = get_connection(DATABASE_PATH)
    try:
        yield conn
    finally:
        conn.close()


class AppointmentSlotRequest(BaseModel):
    doctor_id: int = Field(gt=0)
    appointment_date: str
    appointment_time: str

class MedicalQuestionRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    top_k: int = Field(default=3, ge=1, le=10)

class AppointmentBookingRequest(BaseModel):
    slot_id: int = Field(gt=0)
    patient_name: str = Field(min_length=1, max_length=100)
    patient_contact: str = Field(min_length=1, max_length=30)


class BookingProposalRequest(BaseModel):
    slot_id: int = Field(gt=0)
    patient_name: str = Field(min_length=1, max_length=100)
    patient_contact: str = Field(min_length=1, max_length=30)


class BookingConfirmationRequest(BaseModel):
    proposal_id: str = Field(min_length=1, max_length=100)


@app.get("/health", tags=["Health"])
def health_check():
    return {
        "status": "ok",
        "service": "Healthcare Navigator API",
    }


@app.get("/doctors", tags=["Doctors"])
def search_doctors_endpoint(
    city: str | None = None,
    doctor_type: str | None = None,
    min_experience: int | None = Query(default=None, ge=0),
    max_fees: float | None = Query(default=None, ge=0),
    sort_by: Literal["name", "experience", "fees"] = "name",
    conn: sqlite3.Connection = Depends(get_db),
):
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
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {"count": len(doctors), "doctors": doctors}


@app.get("/doctors/{composite_doctor_id}", tags=["Doctors"])
def get_doctor_endpoint(
    composite_doctor_id: str,
    conn: sqlite3.Connection = Depends(get_db),
):
    doctor = get_doctor_with_hospital(conn, composite_doctor_id)

    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")

    return doctor


@app.post("/appointments/slots", tags=["Appointments"])
def create_slot_endpoint(
    request: AppointmentSlotRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    """Create an application-managed appointment slot for development."""
    try:
        return create_appointment_slot(
            conn,
            doctor_id=request.doctor_id,
            appointment_date=request.appointment_date,
            appointment_time=request.appointment_time,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/appointments/slots", tags=["Appointments"])
def list_slots_endpoint(
    doctor_id: int = Query(gt=0),
    appointment_date: str | None = None,
    conn: sqlite3.Connection = Depends(get_db),
):
    """List available slots for a doctor, optionally for one date."""
    try:
        slots = get_available_slots(
            conn,
            doctor_id=doctor_id,
            appointment_date=appointment_date,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"count": len(slots), "slots": slots}



@app.post("/appointments", tags=["Appointments"], deprecated=True)
def book_appointment_endpoint():
    """Direct booking is disabled; use proposal and confirmation."""
    raise HTTPException(
        status_code=409,
        detail=(
            "Direct booking is disabled. Create a booking proposal "
            "and explicitly confirm it."
        ),
    )



@app.post("/appointments/proposals", tags=["Appointments"])
def create_booking_proposal_endpoint(
    request: BookingProposalRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return create_booking_proposal(
            conn,
            slot_id=request.slot_id,
            patient_name=request.patient_name,
            patient_contact=request.patient_contact,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc



@app.post("/appointments/proposals/confirm", tags=["Appointments"])
def confirm_booking_proposal_endpoint(
    request: BookingConfirmationRequest,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return confirm_booking_proposal(
            conn,
            proposal_id=request.proposal_id,
        )
    except ValueError as exc:
        message = str(exc)
        status_code = 404 if message == "Booking proposal not found" else 409
        raise HTTPException(
            status_code=status_code,
            detail=message,
        ) from exc


@app.get("/appointments/{booking_reference}", tags=["Appointments"])
def get_appointment_endpoint(
    booking_reference: str,
    conn: sqlite3.Connection = Depends(get_db),
):
    appointment = get_appointment_by_reference(conn, booking_reference)

    if appointment is None:
        raise HTTPException(
            status_code=404,
            detail="Appointment not found",
        )

    return appointment


@app.post(
    "/appointments/{booking_reference}/cancel",
    tags=["Appointments"],
)
def cancel_appointment_endpoint(
    booking_reference: str,
    conn: sqlite3.Connection = Depends(get_db),
):
    try:
        return cancel_appointment(conn, booking_reference)
    except ValueError as exc:
        status_code = (
            404 if str(exc) == "Appointment not found" else 400
        )
        raise HTTPException(
            status_code=status_code,
            detail=str(exc),
        ) from exc

@app.post("/medical/ask", tags=["Medical Q&A"])
def ask_medical_question(request: MedicalQuestionRequest):
    """Answer a health-information question and measure processing time."""
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Question must not be empty.",
        )

    start_time = time.perf_counter()

    try:
        print(f"\n[Medical AI] Question received: {question[:100]}")

        graph = app.state.healthcare_graph

        graph_result = graph.invoke(
            {
                "question": question,
                "top_k": request.top_k,
                "medical_qa_service": app.state.medical_qa_service,
                "db_path": str(DATABASE_PATH),
            }
        )

        if "error" in graph_result:
            raise HTTPException(
                status_code=422,
                detail=graph_result["error"],
            )

        result = graph_result["result"]

        elapsed = time.perf_counter() - start_time
        print(f"[Medical AI] Total processing time: {elapsed:.2f} seconds")

        return result

    except HTTPException:
        raise

    except Exception:
        elapsed = time.perf_counter() - start_time
        print(f"[Medical AI] Failed after {elapsed:.2f} seconds")
        traceback.print_exc()

        raise HTTPException(
            status_code=502,
            detail="Medical answer generation failed. Check backend logs.",
        ) from None