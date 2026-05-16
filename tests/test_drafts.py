"""Tests for the drafting system (DB + templates + generator)."""

import sqlite3
from pathlib import Path
from unittest.mock import patch

from klinika.services.patients import init_patient_db, upsert_patient, upsert_diagnosis, upsert_medication
from klinika.services.labs import init_lab_db
from klinika.services.drafts import init_drafts_db, save_draft, get_draft, list_drafts, update_draft_status
from klinika.standards.bdt import Patient, Diagnosis, Medication, parse_bdt
from klinika.drafting.generator import build_draft_context as build_prompt
from klinika.drafting.templates import TEMPLATES, DRAFT_TYPE_LABELS

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"


def _setup_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    init_patient_db(conn)
    init_lab_db(conn)
    init_drafts_db(conn)
    # Bootstrap sample patient
    bdt_data = parse_bdt(SAMPLES_DIR / "sample_clinic_bootstrap.bdt")
    for p in bdt_data.patients:
        upsert_patient(conn, p)
    for d in bdt_data.diagnoses:
        upsert_diagnosis(conn, d)
    for m in bdt_data.medications:
        upsert_medication(conn, m)
    return conn


class TestDraftsDB:
    def setup_method(self):
        self.conn = _setup_db()

    def test_save_and_get(self):
        draft_id = save_draft(self.conn, "ueberweisung", "00042", "V.a. KHK", "Draft content here")
        assert draft_id
        draft = get_draft(self.conn, draft_id)
        assert draft is not None
        assert draft["type"] == "ueberweisung"
        assert draft["patient_id"] == "00042"
        assert draft["content"] == "Draft content here"
        assert draft["status"] == "pending"

    def test_list_all(self):
        save_draft(self.conn, "ueberweisung", "00042", "ctx1", "content1")
        save_draft(self.conn, "arztbrief", "00043", "ctx2", "content2")
        drafts = list_drafts(self.conn)
        assert len(drafts) == 2

    def test_list_by_patient(self):
        save_draft(self.conn, "ueberweisung", "00042", "ctx1", "content1")
        save_draft(self.conn, "arztbrief", "00043", "ctx2", "content2")
        drafts = list_drafts(self.conn, patient_id="00042")
        assert len(drafts) == 1
        assert drafts[0]["patient_id"] == "00042"

    def test_update_status(self):
        draft_id = save_draft(self.conn, "rezept", "00042", "ctx", "content")
        update_draft_status(self.conn, draft_id, "accepted")
        draft = get_draft(self.conn, draft_id)
        assert draft["status"] == "accepted"

    def test_get_nonexistent(self):
        assert get_draft(self.conn, "nonexistent") is None


class TestTemplates:
    def test_all_types_have_templates(self):
        for t in ["ueberweisung", "arztbrief", "rezept", "au", "soap"]:
            assert t in TEMPLATES
            assert t in DRAFT_TYPE_LABELS

    def test_templates_have_placeholders(self):
        for name, template in TEMPLATES.items():
            assert "{patient_summary}" in template
            assert "{context}" in template


class TestBuildPrompt:
    def setup_method(self):
        self.conn = _setup_db()

    def test_build_ueberweisung_prompt(self):
        prompt = build_prompt(self.conn, "ueberweisung", "00042", "V.a. KHK, Kardiologie")
        assert "Schmidt" in prompt
        assert "V.a. KHK" in prompt
        assert "E11.9" in prompt or "Diabetes" in prompt
        assert "Metformin" in prompt

    def test_build_soap_prompt(self):
        prompt = build_prompt(self.conn, "soap", "00042", "Routinekontrolle")
        assert "Schmidt" in prompt
        assert "Routinekontrolle" in prompt

    def test_build_unknown_type_raises(self):
        try:
            build_prompt(self.conn, "invalid_type", "00042", "ctx")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "Unknown draft type" in str(e)

    def test_build_unknown_patient_raises(self):
        try:
            build_prompt(self.conn, "ueberweisung", "99999", "ctx")
            assert False, "Should have raised ValueError"
        except ValueError as e:
            assert "not found" in str(e)
