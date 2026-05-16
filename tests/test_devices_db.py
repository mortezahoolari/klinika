"""Tests for the device results database."""

import sqlite3
from pathlib import Path

from klinika.services.patients import init_patient_db, upsert_patient
from klinika.services.devices import init_device_db, upsert_device_result, get_device_results, list_recent_results
from klinika.standards.bdt import parse_bdt
from klinika.standards.gdt import parse_gdt

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"
GDT_DIR = SAMPLES_DIR / "gdt"


def _setup_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    init_patient_db(conn)
    init_device_db(conn)
    bdt_data = parse_bdt(SAMPLES_DIR / "sample_clinic_bootstrap.bdt")
    for p in bdt_data.patients:
        upsert_patient(conn, p)
    return conn


class TestDeviceDB:
    def setup_method(self):
        self.conn = _setup_db()
        # Import all 3 GDT files
        for gdt_file in GDT_DIR.glob("*.gdt"):
            for result in parse_gdt(gdt_file):
                upsert_device_result(self.conn, result)

    def test_results_stored(self):
        count = self.conn.execute("SELECT COUNT(*) FROM device_results").fetchone()[0]
        assert count == 14  # 5 (ECG) + 5 (spiro) + 4 (BP)

    def test_get_schmidt_ecg(self):
        results = get_device_results(self.conn, "00042", "EKG1")
        assert len(results) == 5
        test_ids = {r["test_id"] for r in results}
        assert "HF" in test_ids
        assert "QRS" in test_ids

    def test_get_weber_spirometry(self):
        results = get_device_results(self.conn, "00044", "SPIR")
        assert len(results) == 5
        fev1 = next(r for r in results if r["test_id"] == "FEV1")
        assert fev1["value"] == "1.89"

    def test_get_becker_bp(self):
        results = get_device_results(self.conn, "00046")
        assert len(results) == 4
        sys = next(r for r in results if r["test_id"] == "RRSYS")
        assert sys["value"] == "148"

    def test_list_recent(self):
        results = list_recent_results(self.conn)
        assert len(results) == 3  # 3 exams (one per patient)
        patient_ids = {r["patient_id"] for r in results}
        assert patient_ids == {"00042", "00044", "00046"}

    def test_no_results_for_patient(self):
        results = get_device_results(self.conn, "00043")
        assert results == []
