"""Tests for GDT bidirectional bridge — SA 6302 parsing and SA 6310 result writing."""

import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from klinika.bridges.gdt_bridge import GDTBridge
from klinika.standards.bdt import parse_bdt
from klinika.standards.gdt import (
    GDTRequest,
    parse_gdt_request,
    parse_gdt,
    write_gdt_result,
)
from klinika.services.patients import (
    init_patient_db,
    upsert_patient,
    upsert_encounter,
    upsert_diagnosis,
    upsert_medication,
)

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"
GDT_SAMPLES_DIR = SAMPLES_DIR / "gdt"

_SAMPLE_6302 = GDT_SAMPLES_DIR / "gdt_6302_request_schmidt.gdt"
_SAMPLE_6310 = GDT_SAMPLES_DIR / "gdt_6310_ekg1_00042.gdt"


def _bootstrap_db() -> sqlite3.Connection:
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


# ------------------------------------------------------------------
# SA 6302 parser
# ------------------------------------------------------------------

class TestParseGDTRequest:
    def setup_method(self):
        self.req = parse_gdt_request(_SAMPLE_6302)

    def test_returns_gdt_request(self):
        assert self.req is not None
        assert isinstance(self.req, GDTRequest)

    def test_surname(self):
        assert self.req.surname == "Schmidt"

    def test_firstname(self):
        assert self.req.firstname == "Karl"

    def test_dob(self):
        assert self.req.dob == "12031958"

    def test_sender_id(self):
        assert self.req.sender_id == "TURBOMED"

    def test_receiver_id(self):
        assert self.req.receiver_id == "KLINIKA"

    def test_wrong_type_returns_none(self):
        result = parse_gdt_request(_SAMPLE_6310)
        assert result is None


# ------------------------------------------------------------------
# SA 6310 result writer
# ------------------------------------------------------------------

class TestWriteGDTResult:
    def setup_method(self):
        self.req = GDTRequest(
            surname="Schmidt",
            firstname="Karl",
            dob="12031958",
            sender_id="TURBOMED",
            receiver_id="KLINIKA",
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.out_path = Path(self.tmp.name) / "result.gdt"

    def teardown_method(self):
        self.tmp.cleanup()

    def test_file_is_created(self):
        write_gdt_result(self.out_path, self.req, "KLINIKA", "SOAP note content")
        assert self.out_path.exists()

    def test_result_is_valid_6310(self):
        write_gdt_result(self.out_path, self.req, "KLINIKA", "Test finding")
        results = parse_gdt(self.out_path)
        # The file is a 6310 with finding but no measurements — parse_gdt returns 1 result
        # with empty measurements list (finding in field 6220)
        assert len(results) == 1

    def test_finding_content(self):
        content = "SOAP: Herzinsuffizienz, Exazerbation. Furosemid erhoehen."
        write_gdt_result(self.out_path, self.req, "KLINIKA", content)
        raw = self.out_path.read_bytes().decode("iso-8859-15")
        assert content in raw

    def test_patient_fields_in_result(self):
        write_gdt_result(self.out_path, self.req, "KLINIKA", "note")
        raw = self.out_path.read_bytes().decode("iso-8859-15")
        assert "Schmidt" in raw
        assert "Karl" in raw
        assert "12031958" in raw


# ------------------------------------------------------------------
# GDTBridge class
# ------------------------------------------------------------------

class TestGDTBridge:
    def setup_method(self):
        self.conn = _bootstrap_db()
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.bridge = GDTBridge(self.folder, "KLINIKA", self.conn)

    def teardown_method(self):
        self.tmp.cleanup()

    def test_initial_current_patient_is_none(self):
        assert self.bridge.current_patient is None

    def test_handles_request_and_resolves_patient(self):
        dest = self.folder / "req_schmidt.gdt"
        shutil.copy(_SAMPLE_6302, dest)
        # Call _handle_request directly (no threading, no sleep)
        self.bridge._seen  # access to confirm state
        self.bridge._handle_request(dest)
        assert self.bridge.current_patient is not None
        _, name = self.bridge.current_patient
        assert "Schmidt" in name

    def test_handled_file_added_to_seen(self):
        dest = self.folder / "req_schmidt.gdt"
        shutil.copy(_SAMPLE_6302, dest)
        self.bridge._handle_request(dest)
        assert "req_schmidt.gdt" in self.bridge._seen

    def test_skips_non_request_gdt(self):
        dest = self.folder / "result.gdt"
        shutil.copy(_SAMPLE_6310, dest)
        # _try_handle checks for SA_EXAM_REQUEST in first 200 chars
        self.bridge._seen.clear()
        self.bridge._try_handle(dest)
        assert self.bridge.current_patient is None
        assert "result.gdt" in self.bridge._seen  # marked as seen to avoid re-processing

    def test_write_result_no_current_patient(self):
        result = self.bridge.write_result("SOAP content")
        assert result is None

    def test_write_result_creates_file(self):
        dest = self.folder / "req.gdt"
        shutil.copy(_SAMPLE_6302, dest)
        self.bridge._handle_request(dest)
        out = self.bridge.write_result("SOAP: Kein Befund.")
        assert out is not None
        assert out.exists()

    def test_write_result_file_is_valid_gdt(self):
        dest = self.folder / "req2.gdt"
        shutil.copy(_SAMPLE_6302, dest)
        self.bridge._handle_request(dest)
        out = self.bridge.write_result("Finding text here.")
        raw = out.read_bytes().decode("iso-8859-15")
        assert "6310" in raw
        assert "Finding text here." in raw

    def test_status_keys(self):
        s = self.bridge.status
        assert "running" in s
        assert "folder" in s
        assert "device_id" in s
        assert "current_patient" in s
        assert "seen_count" in s
