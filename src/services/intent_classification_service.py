
"""Contextual medical intent classification using Google Gemini."""

import json
import logging
import os
import re
from typing import Any

from dotenv import load_dotenv
from google import genai

load_dotenv()

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.8-flash"

VALID_INTENTS = {"medical_question", "symptom_report"}
VALID_SUBJECTS = {"self", "other_person", "hypothetical", "general"}
VALID_TEMPORALITIES = {"current", "historical", "future", "unknown"}


class IntentClassificationService:
    """Classify ambiguous medical messages using contextual language analysis."""

    def __init__(self, model_name: str = DEFAULT_MODEL):
        self.model_name = model_name

    def classify(self, question: str) -> dict[str, Any] | None:
        """Return a validated classification, or None if classification fails."""

        if not isinstance(question, str) or not question.strip():
            raise ValueError("question must not be empty")

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.warning(
                "GEMINI_API_KEY is unavailable; contextual classification skipped."
            )
            return None

        prompt = f"""
You classify messages for a healthcare navigation application.

Determine whether the user is asking a general medical question or
reporting symptoms experienced by a real person.

Pay careful attention to:
- WHO is experiencing the symptoms: the user, another real person,
  a hypothetical person, or nobody in particular.
- WHEN the symptoms are happening: currently, historically,
  in the future, or unclear.
- Whether the message describes a possible emergency happening now.

Rules:
1. A question about causes, symptoms, warning signs, diseases, or
   medical mechanisms is normally a medical_question.
2. A first-person report of symptoms is a symptom_report.
3. A report about a family member or another real person is a
   symptom_report.
4. Hypothetical examples and educational questions are not symptom reports.
5. Historical symptoms remain symptom reports but are not automatically
   current emergencies.
6. Emergency signals include chest pain, severe breathing difficulty,
   unconsciousness, severe bleeding, and stroke warning signs.
7. An emergency signal is true ONLY when the message describes a
   potentially emergency-level symptom currently happening to a real person.
8. Never infer an emergency merely because an emergency symptom is
   mentioned in a hypothetical or educational question.
9. Do not diagnose or estimate clinical risk.

Return ONLY valid JSON with exactly these fields:
{{
  "intent": "medical_question or symptom_report",
  "subject": "self, other_person, hypothetical, or general",
  "temporality": "current, historical, future, or unknown",
  "emergency_signal": true,
  "confidence": 0.0
}}

The confidence field is a classification confidence score, NOT a
medical risk score.

Message:
{question}
"""

        try:
            client = genai.Client(api_key=api_key)

            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                },
            )

            if not response.text:
                raise ValueError("Gemini returned an empty response")

            raw = response.text.strip()

            # Defensive handling if the model returns fenced JSON.
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)

            data = json.loads(raw)

            return self._validate(data)

        except Exception:
            logger.exception("Contextual intent classification failed.")
            return None

    @staticmethod
    def _validate(data: Any) -> dict[str, Any]:
        """Validate the model output before allowing it to affect routing."""

        if not isinstance(data, dict):
            raise ValueError("Classification output must be a JSON object")

        intent = data.get("intent")
        subject = data.get("subject")
        temporality = data.get("temporality")
        emergency_signal = data.get("emergency_signal")
        confidence = data.get("confidence")

        if intent not in VALID_INTENTS:
            raise ValueError("Invalid intent")

        if subject not in VALID_SUBJECTS:
            raise ValueError("Invalid subject")

        if temporality not in VALID_TEMPORALITIES:
            raise ValueError("Invalid temporality")

        if not isinstance(emergency_signal, bool):
            raise ValueError("emergency_signal must be a boolean")

        if (
            isinstance(confidence, bool)
            or not isinstance(confidence, (int, float))
            or not 0.0 <= confidence <= 1.0
        ):
            raise ValueError("confidence must be between 0 and 1")

        # An emergency must describe a current symptom report involving
        # an actual person, never a hypothetical or general question.
        if emergency_signal and (
            intent != "symptom_report"
            or subject not in {"self", "other_person"}
            or temporality != "current"
        ):
            raise ValueError("Inconsistent emergency classification")

        return {
            "intent": intent,
            "subject": subject,
            "temporality": temporality,
            "emergency_signal": emergency_signal,
            "confidence": float(confidence),
        }
