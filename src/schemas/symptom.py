
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedSymptom(BaseModel):
    """A symptom extracted from a patient's natural-language description."""

    symptom: str = Field(min_length=1)

    status: Literal["present", "absent", "uncertain"] = Field(
        description=(
            "Whether the symptom is affirmed, denied, or uncertain "
            "within the time period described. 'present' does not "
            "necessarily mean currently active."
        )
    )

    temporality: Literal[
        "current",
        "historical",
        "future",
        "unknown",
    ] = Field(
        description="When the symptom is or was experienced."
    )

    experiencer: Literal["self", "other", "unknown"]

    resolution_status: Literal[
        "active",
        "resolved",
        "unknown",
    ] = "unknown"

    duration: str | None = None

    evidence: str = Field(
        min_length=1,
        description="Exact text from the patient's input supporting extraction.",
    )

    confidence: float = Field(ge=0.0, le=1.0)


class SymptomExtractionResult(BaseModel):
    """Structured output from the symptom extraction service."""

    symptoms: list[ExtractedSymptom] = Field(default_factory=list)
    requires_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)
