"""Tests for the lab results database."""

import sqlite3
from pathlib import Path

from klinika.services.patients import init_patient_db, upsert_patient
from klinika.services.labs import init_lab_db, upsert_lab_result, get_lab_values, get_abnormal_labs
from klinika.standards.bdt import Patient, parse_bdt
from klinika.standards.ldt import parse_ldt

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"


def _setup_db() -> sqlite3.Connection:
    """Create in-memory DB with patients + lab results from sample files."""
    conn = sqlite3.connect(":memory:")
    init_patient_db(conn)
    init_lab_db(conn)

    # Bootstrap patients
    bdt_data = parse_bdt(SAMPLES_DIR / "sample_clinic_bootstrap.bdt")
    for p in bdt_data.patients:
        upsert_patient(conn, p)

    # Import lab results
    ldt_data = parse_ldt(SAMPLES_DIR / "sample_lab_results.ldt")
    for result in ldt_data.results:
        upsert_lab_result(conn, result)

    return conn


class TestLabsDB:
    def setup_method(self):
        self.conn = _setup_db()

    def test_lab_values_stored(self):
        count = self.conn.execute("SELECT COUNT(*) FROM lab_results").fetchone()[0]
        assert count == 28

    def test_get_schmidt_labs(self):
        values = get_lab_values(self.conn, "00042")
        assert len(values) == 7  # Schmidt has 7 lab values
        codes = {v["test_code"] for v in values}
        assert "HBA1C" in codes
        assert "CREA" in codes

    def test_get_schmidt_hba1c_filtered(self):
        values = get_lab_values(self.conn, "00042", "HBA1C")
        assert len(values) == 1
        assert values[0]["value"] == "8.1"
        assert values[0]["flag"] == "H"

    def test_get_abnormal_all(self):
        abnormals = get_abnormal_labs(self.conn)
        assert len(abnormals) == 14

    def test_get_abnormal_becker(self):
        abnormals = get_abnormal_labs(self.conn, "00046")
        # Becker: Kreatinin H, eGFR L, NT-proBNP H, Hb L = 4 abnormals
        assert len(abnormals) == 4
        codes = {a["test_code"] for a in abnormals}
        assert "CREA" in codes
        assert "EGFR" in codes
        assert "NTPROBNP" in codes
        assert "HB" in codes

    def test_get_abnormal_fischer(self):
        abnormals = get_abnormal_labs(self.conn, "00045")
        # Fischer: only IgE is high
        assert len(abnormals) == 1
        assert abnormals[0]["test_code"] == "IGE"

    def test_no_labs_for_nonexistent(self):
        values = get_lab_values(self.conn, "99999")
        assert values == []
