"""
Patient database — SQLite tables for structured clinical data.

Populated from BDT bootstrap/incremental exports and Doctolib calendar syncs.
Tables: patients, allergies, diagnoses, medications, encounters, appointments.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone

from klinika.standards.bdt import Patient, Encounter, Diagnosis, Medication


def init_patient_db(conn: sqlite3.Connection) -> None:
    """Create all patient-related tables if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS patients (
            id TEXT PRIMARY KEY,
            last_name TEXT NOT NULL,
            first_name TEXT NOT NULL,
            dob TEXT,
            sex TEXT,
            street TEXT,
            zip_code TEXT,
            city TEXT,
            phone TEXT,
            insurance TEXT,
            insurance_nr TEXT,
            source TEXT DEFAULT 'bdt',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS allergies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            allergen TEXT NOT NULL,
            UNIQUE(patient_id, allergen)
        );

        CREATE TABLE IF NOT EXISTS diagnoses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            icd_code TEXT,
            description TEXT,
            source TEXT DEFAULT 'bdt'
        );

        CREATE TABLE IF NOT EXISTS medications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            name TEXT NOT NULL,
            dosage TEXT,
            source TEXT DEFAULT 'bdt'
        );

        CREATE TABLE IF NOT EXISTS encounters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT NOT NULL REFERENCES patients(id),
            date TEXT,
            doctor_id TEXT,
            note TEXT,
            source TEXT DEFAULT 'bdt'
        );

        CREATE TABLE IF NOT EXISTS appointments (
            id TEXT PRIMARY KEY,
            patient_id TEXT REFERENCES patients(id),
            start_time TEXT NOT NULL,
            end_time TEXT,
            visit_type TEXT,
            notes TEXT,
            source TEXT DEFAULT 'doctolib',
            date TEXT NOT NULL
        );

        CREATE INDEX IF NOT EXISTS idx_patients_name ON patients(last_name, first_name);
        CREATE INDEX IF NOT EXISTS idx_encounters_patient ON encounters(patient_id);
        CREATE INDEX IF NOT EXISTS idx_appointments_date ON appointments(date);
    """)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def upsert_patient(conn: sqlite3.Connection, patient: Patient) -> None:
    """Insert or update a patient record."""
    now = _now()
    conn.execute(
        """INSERT INTO patients (id, last_name, first_name, dob, sex, street, zip_code,
                                 city, phone, insurance, insurance_nr, source, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'bdt', ?, ?)
           ON CONFLICT(id) DO UPDATE SET
             last_name=excluded.last_name, first_name=excluded.first_name,
             dob=excluded.dob, sex=excluded.sex, street=excluded.street,
             zip_code=excluded.zip_code, city=excluded.city, phone=excluded.phone,
             insurance=excluded.insurance, insurance_nr=excluded.insurance_nr,
             updated_at=excluded.updated_at""",
        (patient.id, patient.last_name, patient.first_name, patient.dob,
         patient.sex, patient.street, patient.zip_code, patient.city,
         patient.phone, patient.insurance, patient.insurance_nr, now, now),
    )
    for allergen in patient.allergies:
        conn.execute(
            "INSERT OR IGNORE INTO allergies (patient_id, allergen) VALUES (?, ?)",
            (patient.id, allergen),
        )
    conn.commit()


def upsert_encounter(conn: sqlite3.Connection, encounter: Encounter) -> None:
    conn.execute(
        "INSERT INTO encounters (patient_id, date, doctor_id, note) VALUES (?, ?, ?, ?)",
        (encounter.patient_id, encounter.date, encounter.doctor_id, encounter.note),
    )
    conn.commit()


def upsert_diagnosis(conn: sqlite3.Connection, diagnosis: Diagnosis) -> None:
    conn.execute(
        "INSERT INTO diagnoses (patient_id, icd_code, description) VALUES (?, ?, ?)",
        (diagnosis.patient_id, diagnosis.icd_code, diagnosis.text),
    )
    conn.commit()


def upsert_medication(conn: sqlite3.Connection, medication: Medication) -> None:
    conn.execute(
        "INSERT INTO medications (patient_id, name, dosage) VALUES (?, ?, ?)",
        (medication.patient_id, medication.name, medication.dosage),
    )
    conn.commit()


def upsert_appointment(conn: sqlite3.Connection, appt: dict) -> None:
    """Insert or update an appointment from Doctolib calendar data."""
    patient_id = appt.get("bdt_patient_id")
    if patient_id == "NEW":
        patient_id = None

    conn.execute(
        """INSERT INTO appointments (id, patient_id, start_time, end_time,
                                     visit_type, notes, source, date)
           VALUES (?, ?, ?, ?, ?, ?, 'doctolib', ?)
           ON CONFLICT(id) DO UPDATE SET
             patient_id=excluded.patient_id, start_time=excluded.start_time,
             end_time=excluded.end_time, visit_type=excluded.visit_type,
             notes=excluded.notes""",
        (appt["id"], patient_id, appt["start_datetime"], appt.get("end_datetime"),
         appt.get("visit_type"), appt.get("notes"),
         appt["start_datetime"][:10]),
    )
    conn.commit()


def get_patient_count(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COUNT(*) FROM patients").fetchone()
    return row[0] if row else 0


def get_todays_appointments(conn: sqlite3.Connection, date: str) -> list[dict]:
    """Get appointments for a date (YYYY-MM-DD), joined with patient info."""
    rows = conn.execute("""
        SELECT a.start_time, a.visit_type, a.notes,
               p.id, p.first_name, p.last_name
        FROM appointments a
        LEFT JOIN patients p ON a.patient_id = p.id
        WHERE a.date = ?
        ORDER BY a.start_time
    """, (date,)).fetchall()

    return [
        {
            "start_time": r[0],
            "visit_type": r[1],
            "notes": r[2],
            "patient_id": r[3],
            "patient_name": f"{r[4]} {r[5]}" if r[4] else "Neupatient",
        }
        for r in rows
    ]


# --- Stage 4: Precise retrieval queries ---


def get_patient(conn: sqlite3.Connection, patient_id: str) -> dict | None:
    """Exact lookup by ID. Returns full patient record + allergies."""
    row = conn.execute(
        "SELECT id, last_name, first_name, dob, sex, street, zip_code, city, "
        "phone, insurance, insurance_nr FROM patients WHERE id = ?",
        (patient_id,),
    ).fetchone()
    if not row:
        return None
    patient = {
        "id": row[0], "last_name": row[1], "first_name": row[2],
        "dob": row[3], "sex": row[4], "street": row[5], "zip_code": row[6],
        "city": row[7], "phone": row[8], "insurance": row[9], "insurance_nr": row[10],
    }
    patient["allergies"] = get_allergies(conn, patient_id)
    return patient


def find_patient(conn: sqlite3.Connection, name_query: str) -> list[dict]:
    """SQL LIKE search on last_name, first_name, or full name in either order."""
    pattern = f"%{name_query}%"
    rows = conn.execute(
        "SELECT id, last_name, first_name, dob FROM patients "
        "WHERE last_name LIKE ? OR first_name LIKE ? "
        "OR (first_name || ' ' || last_name) LIKE ? "
        "OR (last_name || ' ' || first_name) LIKE ?",
        (pattern, pattern, pattern, pattern),
    ).fetchall()
    return [
        {"id": r[0], "last_name": r[1], "first_name": r[2], "dob": r[3]}
        for r in rows
    ]


def get_medications(conn: sqlite3.Connection, patient_id: str) -> list[dict]:
    """All medications for a patient."""
    rows = conn.execute(
        "SELECT name, dosage FROM medications WHERE patient_id = ?",
        (patient_id,),
    ).fetchall()
    return [{"name": r[0], "dosage": r[1]} for r in rows]


def get_diagnoses(conn: sqlite3.Connection, patient_id: str) -> list[dict]:
    """All diagnoses (ICD + text) for a patient."""
    rows = conn.execute(
        "SELECT icd_code, description FROM diagnoses WHERE patient_id = ?",
        (patient_id,),
    ).fetchall()
    return [{"icd_code": r[0], "description": r[1]} for r in rows]


def get_allergies(conn: sqlite3.Connection, patient_id: str) -> list[str]:
    """All allergens for a patient."""
    rows = conn.execute(
        "SELECT allergen FROM allergies WHERE patient_id = ?",
        (patient_id,),
    ).fetchall()
    return [r[0] for r in rows]


def get_encounters(conn: sqlite3.Connection, patient_id: str, limit: int = 10) -> list[dict]:
    """Recent encounters for a patient, newest first."""
    rows = conn.execute(
        "SELECT date, doctor_id, note, source FROM encounters "
        "WHERE patient_id = ? ORDER BY date DESC LIMIT ?",
        (patient_id, limit),
    ).fetchall()
    return [
        {"date": r[0], "doctor_id": r[1], "note": r[2], "source": r[3]}
        for r in rows
    ]


def search_patients(
    conn: sqlite3.Connection,
    diagnosis: str | None = None,
    medication: str | None = None,
) -> list[dict]:
    """Find patients by diagnosis ICD code/text or medication name. SQL LIKE."""
    if diagnosis:
        rows = conn.execute(
            "SELECT DISTINCT p.id, p.last_name, p.first_name, d.icd_code, d.description "
            "FROM patients p JOIN diagnoses d ON p.id = d.patient_id "
            "WHERE d.icd_code LIKE ? OR d.description LIKE ?",
            (f"%{diagnosis}%", f"%{diagnosis}%"),
        ).fetchall()
        return [
            {"id": r[0], "last_name": r[1], "first_name": r[2],
             "icd_code": r[3], "description": r[4]}
            for r in rows
        ]
    elif medication:
        rows = conn.execute(
            "SELECT DISTINCT p.id, p.last_name, p.first_name, m.name, m.dosage "
            "FROM patients p JOIN medications m ON p.id = m.patient_id "
            "WHERE m.name LIKE ?",
            (f"%{medication}%",),
        ).fetchall()
        return [
            {"id": r[0], "last_name": r[1], "first_name": r[2],
             "medication": r[3], "dosage": r[4]}
            for r in rows
        ]
    return []


def resolve_patient(conn: sqlite3.Connection, name: str) -> tuple[str, str] | None:
    """Resolve a patient name to (patient_id, full_name). Returns first match or None."""
    results = find_patient(conn, name)
    if not results:
        return None
    r = results[0]
    return (r["id"], f"{r['first_name']} {r['last_name']}")


def current_patient(conn: sqlite3.Connection) -> dict | None:
    """Infer current patient from today's schedule + current time."""
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone(timedelta(hours=2)))  # CEST
    today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    appointments = get_todays_appointments(conn, today)
    if not appointments:
        return None

    # Find the appointment closest to (but not after) current time
    best = None
    for appt in appointments:
        appt_time = appt["start_time"][11:16] if len(appt["start_time"]) > 11 else appt["start_time"]
        if appt_time <= current_time and appt.get("patient_id"):
            best = appt
    return best


def add_observation(conn: sqlite3.Connection, patient_id: str, note: str) -> str:
    """Add a Klinika-originated observation to encounters."""
    from datetime import datetime, timezone
    now_str = datetime.now(timezone.utc).strftime("%d%m%Y")
    conn.execute(
        "INSERT INTO encounters (patient_id, date, note, source) VALUES (?, ?, ?, 'klinika')",
        (patient_id, now_str, note),
    )
    conn.commit()
    return f"Observation saved for patient {patient_id}."
