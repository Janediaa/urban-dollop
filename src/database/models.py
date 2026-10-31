import sqlite3

def _migrate_appointments_allow_history(
    conn: sqlite3.Connection,
) -> None:
    """Allow multiple historical appointments per slot, but only
    one confirmed appointment per slot.
    """
    conn.commit()

    foreign_keys_enabled = conn.execute(
        "PRAGMA foreign_keys"
    ).fetchone()[0]

    try:
        conn.execute("PRAGMA foreign_keys = OFF")
        conn.execute("BEGIN IMMEDIATE")

        indexes = conn.execute(
            "PRAGMA index_list(appointments)"
        ).fetchall()

        has_unique_slot_constraint = False

        for index in indexes:
            index_name = index[1]
            is_unique = index[2]
            is_partial = index[4]

            if not is_unique or is_partial:
                continue

            indexed_columns = [
                row[2]
                for row in conn.execute(
                    f'PRAGMA index_info("{index_name}")'
                ).fetchall()
            ]

            if indexed_columns == ["slot_id"]:
                has_unique_slot_constraint = True
                break

        if has_unique_slot_constraint:
            conn.execute("""
                CREATE TABLE appointments_new (
                    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    booking_reference TEXT NOT NULL UNIQUE,
                    slot_id INTEGER NOT NULL,
                    patient_name TEXT NOT NULL,
                    patient_contact TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'confirmed'
                        CHECK (status IN ('confirmed', 'cancelled')),
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    user_id INTEGER REFERENCES users(user_id),
                    FOREIGN KEY (slot_id)
                        REFERENCES appointment_slots(slot_id)
                )
            """)

            conn.execute("""
                INSERT INTO appointments_new (
                    appointment_id,
                    booking_reference,
                    slot_id,
                    patient_name,
                    patient_contact,
                    status,
                    created_at,
                    user_id
                )
                SELECT
                    appointment_id,
                    booking_reference,
                    slot_id,
                    patient_name,
                    patient_contact,
                    status,
                    created_at,
                    user_id
                FROM appointments
            """)

            conn.execute("DROP TABLE appointments")
            conn.execute(
                "ALTER TABLE appointments_new RENAME TO appointments"
            )

        conn.execute("""
            CREATE UNIQUE INDEX IF NOT EXISTS
            idx_one_confirmed_appointment_per_slot
            ON appointments(slot_id)
            WHERE status = 'confirmed'
        """)

        violations = conn.execute(
            "PRAGMA foreign_key_check"
        ).fetchall()

        if violations:
            raise sqlite3.IntegrityError(
                f"Foreign-key violations after appointment migration: "
                f"{violations}"
            )

        conn.commit()

    except Exception:
        conn.rollback()
        raise

    finally:
        if foreign_keys_enabled:
            conn.execute("PRAGMA foreign_keys = ON")

def create_tables(conn : sqlite3.Connection) -> None:
    """
    Create the necessary tables in the database.

    Args:
        conn (sqlite3.Connection): The SQLite connection object.
    """
    cursor = conn.cursor()

        # Store registered patient accounts.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Create hospitals table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS hospitals (
            hospital_id INTEGER PRIMARY KEY AUTOINCREMENT,
            hospital_name TEXT NOT NULL,
            city TEXT NOT NULL,
            UNIQUE(hospital_name, city)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS doctors (
            doctor_id INTEGER PRIMARY KEY AUTOINCREMENT,
            composite_doctor_id TEXT NOT NULL UNIQUE,
            doctor_name TEXT NOT NULL,
            doctor_type TEXT,
            experience_years INTEGER NOT NULL,
            location TEXT NOT NULL,
            fees REAL,
            city TEXT NOT NULL,
            hospital_id INTEGER,
            FOREIGN KEY (hospital_id) REFERENCES hospitals (hospital_id)
        )
    """)


    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointment_slots (
            slot_id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'available'
                CHECK (status IN ('available', 'booked')),
            FOREIGN KEY (doctor_id)
                REFERENCES doctors (doctor_id),
            UNIQUE (doctor_id, appointment_date, appointment_time)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS appointments (
            appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_reference TEXT NOT NULL UNIQUE,
            slot_id INTEGER NOT NULL,
            patient_name TEXT NOT NULL,
            patient_contact TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'confirmed'
                CHECK (status IN ('confirmed', 'cancelled')),
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (slot_id)
                REFERENCES appointment_slots (slot_id)
        )
    """)

    # Store appointment booking proposals separately from confirmed bookings.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS booking_proposals (
            proposal_id TEXT PRIMARY KEY,
            slot_id INTEGER NOT NULL,
            patient_name TEXT NOT NULL,
            patient_contact TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
                CHECK (
                    status IN (
                        'pending',
                        'confirmed',
                        'expired',
                        'cancelled'
                    )
                ),
            expires_at TEXT NOT NULL,
            booking_reference TEXT UNIQUE,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (slot_id)
                REFERENCES appointment_slots (slot_id),
            FOREIGN KEY (booking_reference)
                REFERENCES appointments (booking_reference)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS insurance_policies (
            policy_id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            policy_number TEXT NOT NULL UNIQUE,
            insurer_name TEXT NOT NULL,
            plan_name TEXT NOT NULL,
            coverage_limit REAL,
            deductible REAL,
            copay_percentage REAL,
            valid_from TEXT,
            valid_until TEXT,
            covered_services TEXT NOT NULL DEFAULT '[]',
            excluded_services TEXT NOT NULL DEFAULT '[]',
            FOREIGN KEY (user_id) REFERENCES users(user_id)
                ON DELETE CASCADE
        )
    """)

        # Safely add ownership columns to databases created by older versions.
    for table_name in ("appointments", "booking_proposals"):
        columns = {
            row[1]
            for row in conn.execute(
                f"PRAGMA table_info({table_name})"
            ).fetchall()
        }

        if "user_id" not in columns:
            conn.execute(
                f"""
                ALTER TABLE {table_name}
                ADD COLUMN user_id INTEGER REFERENCES users(user_id)
                """
            )

    _migrate_appointments_allow_history(conn)
    conn.commit()
