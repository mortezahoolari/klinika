"""Tests for the GDT parser against sample device result files."""

from pathlib import Path

from klinika.standards.gdt import parse_gdt

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples" / "gdt"


class TestECGParse:
    def setup_method(self):
        results = parse_gdt(SAMPLES_DIR / "gdt_6310_ekg1_00042.gdt")
        assert len(results) == 1
        self.result = results[0]

    def test_patient_id(self):
        assert self.result.patient_id == "00042"

    def test_device_id(self):
        assert self.result.device_id == "EKG1"

    def test_measurement_count(self):
        assert len(self.result.measurements) == 5

    def test_heart_rate(self):
        hr = next(m for m in self.result.measurements if m.test_id == "HF")
        assert hr.value == "78"
        assert hr.unit == "1/min"

    def test_rhythm(self):
        rhythm = next(m for m in self.result.measurements if m.test_id == "RHYTH")
        assert rhythm.value == "Sinusrhythmus"

    def test_finding(self):
        assert "Sinusrhythmus" in self.result.finding
        assert "Hypertrophiezeichen" in self.result.finding


class TestSpirometryParse:
    def setup_method(self):
        results = parse_gdt(SAMPLES_DIR / "gdt_6310_spir_00044.gdt")
        self.result = results[0]

    def test_patient_id(self):
        assert self.result.patient_id == "00044"

    def test_device_id(self):
        assert self.result.device_id == "SPIR"

    def test_measurement_count(self):
        assert len(self.result.measurements) == 5

    def test_fev1(self):
        fev1 = next(m for m in self.result.measurements if m.test_id == "FEV1")
        assert fev1.value == "1.89"
        assert fev1.unit == "L"

    def test_fev1_ratio(self):
        ratio = next(m for m in self.result.measurements if m.test_id == "FEV1P")
        assert ratio.value == "60.6"


class TestBloodPressureParse:
    def setup_method(self):
        results = parse_gdt(SAMPLES_DIR / "gdt_6310_rr01_00046.gdt")
        self.result = results[0]

    def test_patient_id(self):
        assert self.result.patient_id == "00046"

    def test_systolic(self):
        sys = next(m for m in self.result.measurements if m.test_id == "RRSYS")
        assert sys.value == "148"

    def test_diastolic(self):
        dia = next(m for m in self.result.measurements if m.test_id == "RRDIA")
        assert dia.value == "92"

    def test_spo2(self):
        spo2 = next(m for m in self.result.measurements if m.test_id == "SPO2")
        assert spo2.value == "94"

    def test_measurement_count(self):
        assert len(self.result.measurements) == 4
