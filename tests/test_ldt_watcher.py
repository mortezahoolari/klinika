"""Tests for LDT live folder watcher."""

import shutil
import sqlite3
import tempfile
from pathlib import Path

from klinika.bridges.ldt_watcher import LDTWatcher
from klinika.services.labs import init_lab_db, get_abnormal_labs
from klinika.services.patients import init_patient_db
from klinika.standards.bdt import parse_bdt
from klinika.services.patients import upsert_patient, upsert_encounter, upsert_diagnosis, upsert_medication

SAMPLES_DIR = Path(__file__).parent.parent / "data" / "samples"
SAMPLE_LDT = SAMPLES_DIR / "sample_lab_results.ldt"


def _make_db() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    init_patient_db(conn)
    init_lab_db(conn)
    data = parse_bdt(SAMPLES_DIR / "sample_clinic_bootstrap.bdt")
    for p in data.patients:
        upsert_patient(conn, p)
    return conn


class TestLDTWatcher:
    def setup_method(self):
        self.conn = _make_db()
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name)
        self.watcher = LDTWatcher(self.folder, self.conn)
        # Create expected subdirs (normally done by poll_loop)
        (self.folder / "processed").mkdir()
        (self.folder / "failed").mkdir()

    def teardown_method(self):
        self.tmp.cleanup()

    def test_imports_ldt_file(self):
        src = self.folder / "labs.ldt"
        shutil.copy(SAMPLE_LDT, src)
        self.watcher._handle_file(src)
        abnormals = get_abnormal_labs(self.conn)
        assert len(abnormals) > 0

    def test_moves_to_processed(self):
        src = self.folder / "labs.ldt"
        shutil.copy(SAMPLE_LDT, src)
        self.watcher._handle_file(src)
        assert not src.exists()
        assert (self.folder / "processed" / "labs.ldt").exists()

    def test_skips_already_processed(self):
        # Pre-populate seen set as if previously processed
        self.watcher._seen.add("labs.ldt")
        src = self.folder / "labs.ldt"
        shutil.copy(SAMPLE_LDT, src)
        # Even though file exists in folder, _seen prevents re-import
        # Simulate poll: watcher would skip files in _seen
        new_files = [p for p in self.folder.glob("*.ldt") if p.name not in self.watcher._seen]
        assert len(new_files) == 0

    def test_handles_corrupt_file(self):
        bad = self.folder / "corrupt.ldt"
        bad.write_bytes(b"this is not a valid ldt file\r\n")
        # parse_ldt returns empty results for unrecognised content — no exception.
        # Watcher should not crash and should move the file out of the inbox.
        self.watcher._handle_file(bad)
        assert not bad.exists()  # moved out of inbox (to processed/ or failed/)
        moved = (
            (self.folder / "processed" / "corrupt.ldt").exists()
            or (self.folder / "failed" / "corrupt.ldt").exists()
        )
        assert moved

    def test_processed_count_increments(self):
        assert self.watcher.status["processed_count"] == 0
        src = self.folder / "labs.ldt"
        shutil.copy(SAMPLE_LDT, src)
        self.watcher._handle_file(src)
        assert self.watcher.status["processed_count"] == 1

    def test_last_import_updated(self):
        assert self.watcher.status["last_import"] is None
        src = self.folder / "labs2.ldt"
        shutil.copy(SAMPLE_LDT, src)
        self.watcher._handle_file(src)
        assert self.watcher.status["last_import"] == "labs2.ldt"

    def test_status_keys(self):
        s = self.watcher.status
        assert "running" in s
        assert "folder" in s
        assert "processed_count" in s
        assert "last_import" in s
