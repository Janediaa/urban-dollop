
"""Rule-based context analysis for extracted symptoms."""

import re


NEGATION_PATTERNS = (
    r"\bdo not have\b",
    r"\bdon't have\b",
    r"\bdoes not have\b",
    r"\bdoesn't have\b",
    r"\bno\b",
    r"\bwithout\b",
    r"\bnever experienced\b",
    r"\bnot experiencing\b",
)

HISTORICAL_PATTERNS = (
    r"\bhad\b",
    r"\bused to have\b",
    r"\bexperienced\b",
    r"\blast week\b",
    r"\byesterday\b",
    r"\blast month\b",
    r"\bin the past\b",
)

RESOLVED_PATTERNS = (
    r"\bwent away\b",
    r"\bhas gone away\b",
    r"\bresolved\b",
    r"\bdisappeared\b",
    r"\bno longer\b",
    r"\bhas stopped\b",
)

UNCERTAINTY_PATTERNS = (
    r"\bmight have\b",
    r"\bmay have\b",
    r"\bpossibly\b",
    r"\bperhaps\b",
    r"\bnot sure\b",
    r"\bthink i have\b",
    r"\bfeel like i might\b",
)

FUTURE_PATTERNS = (
    r"\bwill have\b",
    r"\bgoing to develop\b",
    r"\bexpect to have\b",
)

OTHER_PERSON_PATTERNS = (
    r"\bmy mother\b",
    r"\bmy father\b",
    r"\bmy brother\b",
    r"\bmy sister\b",
    r"\bmy friend\b",
    r"\bmy child\b",
    r"\bmy son\b",
    r"\bmy daughter\b",
    r"\bmy husband\b",
    r"\bmy wife\b",
    r"\bmy partner\b",
)


def _contains_pattern(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text) for pattern in patterns)


def analyze_symptom_context(text: str) -> dict:
    """Determine assertion, temporality, experiencer and resolution."""

    normalized = " ".join(text.lower().split())

    experiencer = (
        "other"
        if _contains_pattern(normalized, OTHER_PERSON_PATTERNS)
        else "self"
    )

    resolved = _contains_pattern(normalized, RESOLVED_PATTERNS)
    uncertain = _contains_pattern(normalized, UNCERTAINTY_PATTERNS)
    historical = _contains_pattern(normalized, HISTORICAL_PATTERNS)
    future = _contains_pattern(normalized, FUTURE_PATTERNS)
    negated = _contains_pattern(normalized, NEGATION_PATTERNS)

    if uncertain:
        status = "uncertain"
        temporality = "unknown"
        resolution_status = "unknown"

    elif future:
        status = "uncertain"
        temporality = "future"
        resolution_status = "unknown"

    elif negated:
        status = "absent"
        temporality = "current"
        resolution_status = "unknown"

    elif historical:
        status = "present"
        temporality = "historical"
        resolution_status = "resolved" if resolved else "unknown"

    elif resolved:
        status = "present"
        temporality = "historical"
        resolution_status = "resolved"

    else:
        status = "present"
        temporality = "current"
        resolution_status = "active"

    return {
        "status": status,
        "temporality": temporality,
        "experiencer": experiencer,
        "resolution_status": resolution_status,
    }
