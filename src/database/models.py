import sqlite3


def create_tables(conn : sqlite3.Connection) -> None:
    """
    Create the necessary tables in the database.

    Args:
        conn (sqlite3.Connection): The SQLite connection object.
    """
    cursor = conn.cursor()

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
            slot_id INTEGER NOT NULL UNIQUE,
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
    

    conn.commit()