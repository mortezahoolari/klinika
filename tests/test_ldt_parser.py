"""Tests for the LDT parser against sample data."""

from pathlib import Path

from klinika.standards.ldt import parse_ldt

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"


class TestLDTParse:
    def setup_method(self):
        self.data = parse_ldt(SAMPLES_DIR / "sample_lab_results.ldt")

    def test_result_count(self):
        assert len(self.data.results) == 5  # 5 patients

    def test_patient_ids(self):
        ids = {r.patient_id for r in self.data.results}
        assert ids == {"00042", "00043", "00044", "00045", "00046"}

    def test_total_values(self):
        total = sum(len(r.values) for r in self.data.results)
        assert total == 28

    def test_abnormal_count(self):
        abnormals = [
            v for r in self.data.results for v in r.values
            if v.flag in ("H", "L")
        ]
        assert len(abnormals) == 14

    def test_schmidt_hba1c(self):
        schmidt = next(r for r in self.data.results if r.patient_id == "00042")
        hba1c = next(v for v in schmidt.values if v.test_code == "HBA1C")
        assert hba1c.value == "8.1"
        assert hba1c.flag == "H"
        assert hba1c.unit == "%"

    def test_becker_egfr(self):
        becker = next(r for r in self.data.results if r.patient_id == "00046")
        egfr = next(v for v in becker.values if v.test_code == "EGFR")
        assert egfr.value == "38"
        assert egfr.flag == "L"

    def test_fischer_hp_negative(self):
        fischer = next(r for r in self.data.results if r.patient_id == "00045")
        hp = next(v for v in fischer.values if v.test_code == "HP")
        assert hp.value == "negativ"
        assert hp.flag == "N"
