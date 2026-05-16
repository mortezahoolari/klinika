"""Tests for the patient database (SQLite tables + CRUD)."""

import tempfile
import sqlite3

from klinika.services.patients import (
    init_patient_db,
    upsert_patient,
    upsert_encounter,
    upsert_diagnosis,
    upsert_medication,
    upsert_appointment,
    get_patient_count,
    get_todays_appointments,
)
from klinika.standards.bdt import Patient, Encounter, Diagnosis, Medication


def _tmp_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    init_patient_db(conn)
    return conn


def test_init_creates_tables():
    conn = _tmp_conn()
    tables = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()
    table_names = {t[0] for t in tables}
    assert "patients" in table_names
    assert "allergies" in table_names
    assert "diagnoses" in table_names
    assert "medications" in table_names
    assert "encounters" in table_names
    assert "appointments" in table_names


def test_upsert_patient():
    conn = _tmp_conn()
    p = Patient(id="001", last_name="Schmidt", first_name="Karl",
                dob="12031958", sex="1", allergies=["Penicillin"])
    upsert_patient(conn, p)

    assert get_patient_count(conn) == 1
    row = conn.execute("SELECT last_name FROM patients WHERE id='001'").fetchone()
    assert row[0] == "Schmidt"

    # Check allergy
    allergies = conn.execute("SELECT allergen FROM allergies WHERE patient_id='001'").fetchall()
    assert len(allergies) == 1
    assert allergies[0][0] == "Penicillin"


def test_upsert_patient_update():
    conn = _tmp_conn()
    p = Patient(id="001", last_name="Schmidt", first_name="Karl")
    upsert_patient(conn, p)
    p.phone = "040-123456"
    upsert_patient(conn, p)

    assert get_patient_count(conn) == 1  # still 1, not duplicated


def test_upsert_encounter():
    conn = _tmp_conn()
    upsert_patient(conn, Patient(id="001", last_name="Test", first_name="T"))
    upsert_encounter(conn, Encounter(patient_id="001", date="01042026", note="Routine"))

    rows = conn.execute("SELECT note FROM encounters WHERE patient_id='001'").fetchall()
    assert len(rows) == 1
    assert rows[0][0] == "Routine"


def test_upsert_appointment_and_schedule():
    conn = _tmp_conn()
    upsert_patient(conn, Patient(id="001", last_name="Schmidt", first_name="Karl"))
    upsert_appointment(conn, {
        "id": "appt1",
        "bdt_patient_id": "001",
        "start_datetime": "2026-04-06T08:30:00+02:00",
        "end_datetime": "2026-04-06T08:50:00+02:00",
        "visit_type": "DMP-Kontrolle",
        "notes": "Diabetes check",
    })

    schedule = get_todays_appointments(conn, "2026-04-06")
    assert len(schedule) == 1
    assert schedule[0]["patient_name"] == "Karl Schmidt"
    assert schedule[0]["visit_type"] == "DMP-Kontrolle"


def test_walkin_appointment_unlinked():
    conn = _tmp_conn()
    upsert_appointment(conn, {
        "id": "appt_new",
        "bdt_patient_id": "NEW",
        "start_datetime": "2026-04-06T14:30:00+02:00",
        "visit_type": "Erstuntersuchung",
        "notes": None,
    })

    schedule = get_todays_appointments(conn, "2026-04-06")
    assert len(schedule) == 1
    assert schedule[0]["patient_name"] == "Neupatient"
