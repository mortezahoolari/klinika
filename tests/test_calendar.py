"""Tests for the Doctolib calendar sync."""

import json
import sqlite3
import sys
import tempfile
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from generate_sample_doctolib import generate_calendar  # noqa: E402

from klinika.services.patients import init_patient_db, upsert_patient, get_todays_appointments
from klinika.standards.bdt import Patient
from klinika.tools import calendar

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"
TEST_DATE = "2026-04-06"


def _make_calendar_file(target_date: str) -> str:
    """Write a calendar JSON for the given date to a temp file; return its path."""
    data = generate_calendar(date.fromisoformat(target_date))
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
    json.dump(data, tmp, ensure_ascii=False)
    tmp.close()
    return tmp.name


def _setup_db_with_patients() -> sqlite3.Connection:
    """Create in-memory DB with bootstrap patients."""
    conn = sqlite3.connect(":memory:")
    init_patient_db(conn)
    # Add the 5 bootstrap patients
    for pid, last, first in [
        ("00042", "Schmidt", "Karl"),
        ("00043", "Müller", "Ursula"),
        ("00044", "Weber", "Dieter"),
        ("00045", "Fischer", "Monika"),
        ("00046", "Becker", "Hans"),
    ]:
        upsert_patient(conn, Patient(id=pid, last_name=last, first_name=first))
    return conn


def test_sync_doctolib_parses_appointments():
    conn = _setup_db_with_patients()
    calendar.set_connection(conn)

    cal_path = _make_calendar_file(TEST_DATE)
    result = calendar.sync_doctolib(cal_path)
    assert "6 appointments" in result


def test_sync_doctolib_links_patients():
    conn = _setup_db_with_patients()
    calendar.set_connection(conn)
    cal_path = _make_calendar_file(TEST_DATE)
    calendar.sync_doctolib(cal_path)

    schedule = get_todays_appointments(conn, TEST_DATE)
    assert len(schedule) == 6

    # 5 linked to known patients, 1 walk-in
    linked = [a for a in schedule if a["patient_name"] != "Neupatient"]
    walkins = [a for a in schedule if a["patient_name"] == "Neupatient"]
    assert len(linked) == 5
    assert len(walkins) == 1


def test_todays_schedule_format():
    conn = _setup_db_with_patients()
    calendar.set_connection(conn)
    # Use today's date so todays_schedule() (which uses date.today()) finds appointments
    cal_path = _make_calendar_file(date.today().isoformat())
    calendar.sync_doctolib(cal_path)

    output = calendar.todays_schedule()
    assert "No appointments" not in output
    assert "Schmidt" in output
