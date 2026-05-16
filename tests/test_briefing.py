"""Tests for the morning briefing generator."""

import sqlite3
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
from generate_sample_doctolib import generate_calendar  # noqa: E402

from klinika.services.patients import init_patient_db, upsert_patient, upsert_appointment
from klinika.services.labs import init_lab_db, upsert_lab_result
from klinika.standards.bdt import parse_bdt
from klinika.standards.ldt import parse_ldt
from klinika.services.patients import upsert_encounter, upsert_diagnosis, upsert_medication
from klinika.briefings.generator import generate_briefing

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"
TEST_DATE = "2026-04-06"


def _setup_full_db() -> sqlite3.Connection:
    """Create in-memory DB with all sample data: BDT + calendar + labs."""
    conn = sqlite3.connect(":memory:")
    init_patient_db(conn)
    init_lab_db(conn)

    # BDT bootstrap
    bdt_data = parse_bdt(SAMPLES_DIR / "sample_clinic_bootstrap.bdt")
    for p in bdt_data.patients:
        upsert_patient(conn, p)
    for e in bdt_data.encounters:
        upsert_encounter(conn, e)
    for d in bdt_data.diagnoses:
        upsert_diagnosis(conn, d)
    for m in bdt_data.medications:
        upsert_medication(conn, m)

    # Calendar — always generate for the fixed test date, independent of shared sample file
    cal_data = generate_calendar(date.fromisoformat(TEST_DATE))
    for appt in cal_data["appointments"]:
        upsert_appointment(conn, appt)

    # Lab results
    ldt_data = parse_ldt(SAMPLES_DIR / "sample_lab_results.ldt")
    for result in ldt_data.results:
        upsert_lab_result(conn, result)

    return conn


class TestBriefingGenerator:
    def setup_method(self):
        self.conn = _setup_full_db()

    def test_generates_markdown(self):
        md = generate_briefing(self.conn, TEST_DATE, use_ai=False)
        assert "# Tagesbriefing 2026-04-06" in md

    def test_contains_schedule_table(self):
        md = generate_briefing(self.conn, TEST_DATE, use_ai=False)
        assert "Terminplan" in md
        assert "6 Termine" in md
        assert "Schmidt" in md
        assert "08:30" in md

    def test_contains_all_patients(self):
        md = generate_briefing(self.conn, TEST_DATE, use_ai=False)
        for name in ["Schmidt", "Becker", "Weber", "Fischer"]:
            assert name in md

    def test_contains_walkin(self):
        md = generate_briefing(self.conn, TEST_DATE, use_ai=False)
        assert "Neupatient" in md

    def test_contains_abnormal_labs(self):
        md = generate_briefing(self.conn, TEST_DATE, use_ai=False)
        assert "Auffaellige Laborwerte" in md
        assert "(H)" in md or "(L)" in md

    def test_contains_patient_cards(self):
        md = generate_briefing(self.conn, TEST_DATE, use_ai=False)
        assert "Patientenkarten" in md
        assert "Diagnosen" in md
        assert "Medikamente" in md

    def test_contains_diagnoses_in_cards(self):
        md = generate_briefing(self.conn, TEST_DATE, use_ai=False)
        assert "E11.9" in md  # Diabetes
        assert "I10.90" in md  # Hypertonie

    def test_no_appointments_date(self):
        md = generate_briefing(self.conn, "2099-01-01", use_ai=False)
        assert "Keine Termine" in md

    def test_without_ai(self):
        md = generate_briefing(self.conn, TEST_DATE, use_ai=False)
        assert "KI-Analyse" not in md
