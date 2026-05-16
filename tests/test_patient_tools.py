"""Tests for Stage 4 patient retrieval tools — tested against real BDT sample data."""

import sqlite3
from pathlib import Path

from klinika.standards.bdt import parse_bdt
from klinika.services.patients import (
    init_patient_db,
    upsert_patient,
    upsert_encounter,
    upsert_diagnosis,
    upsert_medication,
    get_patient,
    find_patient,
    get_medications,
    get_diagnoses,
    get_allergies,
    get_encounters,
    search_patients,
    add_observation,
)

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"


def _bootstrap_db() -> sqlite3.Connection:
    """Create in-memory DB bootstrapped with sample BDT data."""
    conn = sqlite3.connect(":memory:")
    init_patient_db(conn)
    data = parse_bdt(SAMPLES_DIR / "sample_clinic_bootstrap.bdt")
    for p in data.patients:
        upsert_patient(conn, p)
    for e in data.encounters:
        upsert_encounter(conn, e)
    for d in data.diagnoses:
        upsert_diagnosis(conn, d)
    for m in data.medications:
        upsert_medication(conn, m)
    return conn


class TestGetPatient:
    def setup_method(self):
        self.conn = _bootstrap_db()

    def test_get_existing(self):
        p = get_patient(self.conn, "00042")
        assert p is not None
        assert p["last_name"] == "Schmidt"
        assert p["first_name"] == "Karl"
        assert p["dob"] == "12031958"
        assert "Penicillin" in p["allergies"]

    def test_get_nonexistent(self):
        assert get_patient(self.conn, "99999") is None


class TestFindPatient:
    def setup_method(self):
        self.conn = _bootstrap_db()

    def test_find_by_last_name(self):
        results = find_patient(self.conn, "Schmidt")
        assert len(results) == 1
        assert results[0]["last_name"] == "Schmidt"

    def test_find_partial(self):
        results = find_patient(self.conn, "Mül")
        assert len(results) == 1
        assert results[0]["first_name"] == "Ursula"

    def test_find_no_match(self):
        results = find_patient(self.conn, "Nonexistent")
        assert len(results) == 0


class TestGetMedications:
    def setup_method(self):
        self.conn = _bootstrap_db()

    def test_schmidt_medications(self):
        meds = get_medications(self.conn, "00042")
        names = {m["name"] for m in meds}
        assert "Metformin 1000mg" in names
        assert "Ramipril 5mg" in names
        assert "Atorvastatin 20mg" in names


class TestGetDiagnoses:
    def setup_method(self):
        self.conn = _bootstrap_db()

    def test_schmidt_diagnoses(self):
        diags = get_diagnoses(self.conn, "00042")
        codes = {d["icd_code"] for d in diags}
        assert "E11.9" in codes
        assert "I10.90" in codes
        assert "E78.0" in codes


class TestGetAllergies:
    def setup_method(self):
        self.conn = _bootstrap_db()

    def test_schmidt_allergies(self):
        allergies = get_allergies(self.conn, "00042")
        assert "Penicillin" in allergies
        assert "Amoxicillin" in allergies

    def test_no_allergies(self):
        allergies = get_allergies(self.conn, "00044")  # Weber has none
        assert len(allergies) == 0


class TestGetEncounters:
    def setup_method(self):
        self.conn = _bootstrap_db()

    def test_schmidt_encounters(self):
        encs = get_encounters(self.conn, "00042")
        assert len(encs) == 3
        notes = {e["note"] for e in encs}
        assert any("Routinekontrolle" in n for n in notes)


class TestSearchPatients:
    def setup_method(self):
        self.conn = _bootstrap_db()

    def test_search_by_diagnosis_icd(self):
        results = search_patients(self.conn, diagnosis="E11")
        patient_ids = {r["id"] for r in results}
        assert "00042" in patient_ids  # Schmidt
        assert "00043" in patient_ids  # Müller

    def test_search_by_medication(self):
        results = search_patients(self.conn, medication="Metformin")
        patient_ids = {r["id"] for r in results}
        assert "00042" in patient_ids
        assert "00043" in patient_ids

    def test_search_no_match(self):
        results = search_patients(self.conn, diagnosis="Z99.99")
        assert len(results) == 0


class TestAddObservation:
    def setup_method(self):
        self.conn = _bootstrap_db()

    def test_add_observation(self):
        result = add_observation(self.conn, "00042", "Patient klagt über Schwindel")
        assert "saved" in result

        encs = get_encounters(self.conn, "00042")
        klinika_notes = [e for e in encs if e.get("source") == "klinika"]
        assert len(klinika_notes) == 1
        assert "Schwindel" in klinika_notes[0]["note"]
