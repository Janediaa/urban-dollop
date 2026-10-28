def get_doctor_by_id(conn, doctor_id):
    """Return a doctor's record by composite ID, or None if not found."""
    cursor = conn.execute(
        """
        SELECT 
            doctor_id,
            composite_doctor_id,
            doctor_name,
            doctor_type,
            experience_years,
            location,
            fees,
            city,
            hospital_id
        FROM doctors
        WHERE composite_doctor_id = ?
        """,
        (doctor_id,),
    )

    row = cursor.fetchone()

    if row is None:
        return None

    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))




def search_doctors(
    conn,
    city=None,
    doctor_type=None,
    min_experience=None,
    max_fees=None,
    sort_by="name",
):
    """Search doctors using optional filters and a supported sorting option."""

    sort_options = {
        "name": "doctor_name ASC",
        "experience": "experience_years DESC, doctor_name ASC",
        "fees": "fees IS NULL ASC, fees ASC, doctor_name ASC",
    }

    if sort_by not in sort_options:
        raise ValueError(
            f"Unsupported sort_by value: {sort_by!r}. "
            f"Choose from: {', '.join(sort_options)}."
        )

    query = """
        SELECT
            doctor_id,
            composite_doctor_id,
            doctor_name,
            doctor_type,
            experience_years,
            location,
            fees,
            city,
            hospital_id
        FROM doctors
        WHERE 1=1
    """
    params = []

    if city is not None and city.strip():
        query += " AND LOWER(city) = LOWER(?)"
        params.append(city.strip())

    if doctor_type is not None and doctor_type.strip():
        query += " AND LOWER(doctor_type) LIKE LOWER(?)"
        params.append(f"%{doctor_type.strip()}%")

    if min_experience is not None:
        query += " AND experience_years >= ?"
        params.append(min_experience)

    if max_fees is not None:
        query += " AND fees <= ?"
        params.append(max_fees)

    # The SQL fragment comes only from our fixed mapping.
    query += f" ORDER BY {sort_options[sort_by]}"

    cursor = conn.execute(query, params)
    columns = [column[0] for column in cursor.description]

    return [
        dict(zip(columns, row))
        for row in cursor.fetchall()
    ]


def get_doctor_with_hospital(conn, composite_doctor_id):
    """Return a doctor with hospital details, or None if not found."""
    cursor = conn.execute(
        """
        SELECT
            d.doctor_id,
            d.composite_doctor_id,
            d.doctor_name,
            d.doctor_type,
            d.experience_years,
            d.location,
            d.fees,
            d.city,
            d.hospital_id,
            h.hospital_name AS hospital_name,
            h.city AS hospital_city
        FROM doctors AS d
        LEFT JOIN hospitals AS h
            ON d.hospital_id = h.hospital_id
        WHERE d.composite_doctor_id = ?
        """,
        (composite_doctor_id,),
    )

    row = cursor.fetchone()

    if row is None:
        return None

    columns = [column[0] for column in cursor.description]
    return dict(zip(columns, row))


def get_doctor_count(conn):
    """Return the total number of doctors in the database."""
    return conn.execute(
        "SELECT COUNT(*) FROM doctors"
    ).fetchone()[0]