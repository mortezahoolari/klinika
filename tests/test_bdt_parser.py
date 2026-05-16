"""Tests for the BDT parser against sample data files."""

from pathlib import Path

from klinika.standards.bdt import parse_bdt

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"


class TestBootstrapParse:
    """Test parsing the full bootstrap BDT file."""

    def setup_method(self):
        self.data = parse_bdt(SAMPLES_DIR / "sample_clinic_bootstrap.bdt")

    def test_patient_count(self):
        assert len(self.data.patients) == 5

    def test_patient_names(self):
        names = {p.last_name for p in self.data.patients}
        assert "Schmidt" in names
        assert "Müller" in names  # note: encoded as ISO-8859-15 in file
        assert "Weber" in names
        assert "Fischer" in names
        assert "Becker" in names

    def test_patient_ids(self):
        ids = {p.id for p in self.data.patients}
        assert ids == {"00042", "00043", "00044", "00045", "00046"}

    def test_schmidt_details(self):
        schmidt = next(p for p in self.data.patients if p.last_name == "Schmidt")
        assert schmidt.first_name == "Karl"
        assert schmidt.dob == "12031958"
        assert schmidt.sex == "1"
        assert schmidt.insurance == "AOK Rheinland/Hamburg"

    def test_schmidt_allergies(self):
        schmidt = next(p for p in self.data.patients if p.last_name == "Schmidt")
        assert "Penicillin" in schmidt.allergies
        assert "Amoxicillin" in schmidt.allergies

    def test_encounters_exist(self):
        assert len(self.data.encounters) > 0

    def test_diagnoses_exist(self):
        assert len(self.data.diagnoses) > 0
        icd_codes = {d.icd_code for d in self.data.diagnoses}
        assert "E11.9" in icd_codes  # Diabetes T2

    def test_medications_exist(self):
        assert len(self.data.medications) > 0
        med_names = {m.name for m in self.data.medications}
        assert "Metformin 1000mg" in med_names


class TestIncrementalParse:
    """Test parsing the incremental BDT file."""

    def setup_method(self):
        self.data = parse_bdt(SAMPLES_DIR / "sample_clinic_incremental.bdt")

    def test_new_patient(self):
        assert len(self.data.patients) == 1
        assert self.data.patients[0].last_name == "Wagner"
        assert self.data.patients[0].id == "00047"

    def test_new_encounters(self):
        # 1 encounter from new patient + 2 follow-ups for existing patients
        encounter_patients = {e.patient_id for e in self.data.encounters}
        assert "00047" in encounter_patients  # Wagner's encounter
        assert "00042" in encounter_patients  # Schmidt follow-up
        assert "00043" in encounter_patients  # Müller follow-up
