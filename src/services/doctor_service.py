
from src.database.repository import get_doctor_with_hospital, search_doctors


def find_doctors(
    conn,
    city=None,
    doctor_type=None,
    min_experience=None,
    max_fees=None,
    sort_by="name",
):
    """Validate search inputs and return matching doctors."""

    for field_name, value in (
        ("city", city),
        ("doctor_type", doctor_type),
    ):
        if value is not None and not isinstance(value, str):
            raise TypeError(f"{field_name} must be a string or None.")

    if min_experience is not None:
        if isinstance(min_experience, bool) or not isinstance(
            min_experience, int
        ):
            raise TypeError("min_experience must be an integer or None.")

        if min_experience < 0:
            raise ValueError("min_experience cannot be negative.")

    if max_fees is not None:
        if isinstance(max_fees, bool) or not isinstance(
            max_fees, (int, float)
        ):
            raise TypeError("max_fees must be a number or None.")

        if max_fees < 0:
            raise ValueError("max_fees cannot be negative.")

    matching_doctors = search_doctors(
        conn,
        city=city,
        doctor_type=doctor_type,
        min_experience=min_experience,
        max_fees=max_fees,
        sort_by=sort_by,
    )

    enriched_doctors = []

    for doctor in matching_doctors:
        enriched_doctor = get_doctor_with_hospital(
            conn,
            doctor["composite_doctor_id"],
        )
        enriched_doctors.append(enriched_doctor)

    return enriched_doctors
