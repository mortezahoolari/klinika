"""
GDT bidirectional bridge — connects Klinika to any German PVS as a GDT device.

How it works:
  1. Practice admin registers Klinika in PVS device settings (folder + 8-char GDT-ID).
  2. When a doctor opens a patient in the PVS, the PVS writes a SA 6302 request file
     to the shared folder.
  3. This bridge detects the file, resolves the patient in Klinika's DB, and exposes
     current_patient so the web app knows who is being seen.
  4. When the doctor is ready, write_result() writes a SA 6310 result file back to
     the same folder. The PVS auto-imports it as a document in the patient record.

No vendor cooperation needed — GDT is an open KBV-mandated standard that every
certified German PVS (TURBOMED, medatixx, MEDISTAR, T2med, …) must support.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import threading
import time
from pathlib import Path

from klinika.standards.gdt import (
    SA_EXAM_REQUEST,
    GDTRequest,
    parse_gdt_request,
    write_gdt_result,
)
from klinika.standards.xdt import read_xdt_file
from klinika.services.patients import resolve_patient

logger = logging.getLogger(__name__)

# Windows race condition: antivirus / write locks cause newly-appearing files to be
# unreadable for a few seconds after detection. 3s documented as insufficient.
_FILE_SETTLE_SECONDS = 5


class GDTBridge:
    """Polls a folder for GDT SA 6302 request files from the PVS.

    Instantiate once and call start(). The bridge runs as a daemon thread.
    Stop with stop() on server shutdown.
    """

    def __init__(self, folder: Path, device_id: str, conn: sqlite3.Connection) -> None:
        self.folder = Path(folder)
        self.device_id = device_id[:8]  # GDT-IDs are max 8 chars
        self._conn = conn
        self._seen: set[str] = set()
        self._current_patient: tuple[str, str] | None = None  # (patient_id, full_name)
        self._current_request: GDTRequest | None = None
        self._lock = threading.Lock()
        self._running = False
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="gdt-bridge")
        self._thread.start()
        logger.info("GDT bridge started — watching %s as device %s", self.folder, self.device_id)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=10)

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        processed_dir = self.folder / "processed"
        processed_dir.mkdir(exist_ok=True)
        # Pre-populate _seen from already-processed files (restart-safe)
        for p in processed_dir.glob("*.gdt"):
            self._seen.add(p.name)
        while self._running:
            try:
                for path in sorted(self.folder.glob("*.gdt")):
                    if path.name not in self._seen:
                        self._try_handle(path)
            except Exception:
                logger.exception("GDT bridge poll error")
            time.sleep(5)

    def _try_handle(self, path: Path) -> None:
        try:
            raw = read_xdt_file(path)
        except Exception:
            self._seen.add(path.name)
            return

        # Quick pre-check: skip result files we wrote ourselves
        if SA_EXAM_REQUEST not in raw[:200]:
            self._seen.add(path.name)
            return

        # Wait for the file to be fully written (Windows race condition)
        time.sleep(_FILE_SETTLE_SECONDS)
        self._handle_request(path)

    def _handle_request(self, path: Path) -> None:
        try:
            req = parse_gdt_request(path)
        except Exception:
            logger.warning("GDT bridge: failed to parse %s", path.name)
            self._seen.add(path.name)
            return

        if req is None:
            self._seen.add(path.name)
            return

        # Resolve patient by surname (+ firstname as disambiguation hint)
        query = f"{req.surname} {req.firstname}".strip()
        resolved = resolve_patient(self._conn, query)

        with self._lock:
            self._current_request = req
            self._current_patient = resolved  # None if not found
            self._seen.add(path.name)

        # Move processed 6302 to processed/ so it is not re-applied on restart
        processed_dir = path.parent / "processed"
        processed_dir.mkdir(exist_ok=True)
        try:
            shutil.move(str(path), processed_dir / path.name)
        except Exception:
            logger.warning("GDT bridge: could not move %s to processed/", path.name)

        if resolved:
            logger.info("GDT bridge: patient opened — %s (id=%s)", resolved[1], resolved[0])
        else:
            logger.warning("GDT bridge: patient '%s' not found in DB", query)

    # ------------------------------------------------------------------
    # Result write-back
    # ------------------------------------------------------------------

    def write_result(self, content: str) -> Path | None:
        """Write a SA 6310 result file for the current patient.

        Returns the path of the written file, or None if no patient is active.
        The PVS will auto-import the file from the shared folder.
        """
        with self._lock:
            req = self._current_request

        if req is None:
            return None

        timestamp = int(time.time())
        filename = f"{self.device_id}_{timestamp}.gdt"
        out_path = self.folder / filename

        write_gdt_result(out_path, req, self.device_id, content)
        logger.info("GDT bridge: wrote result → %s", out_path)
        return out_path

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def current_patient(self) -> tuple[str, str] | None:
        """(patient_id, full_name) of the patient currently open in the PVS."""
        with self._lock:
            return self._current_patient

    @property
    def status(self) -> dict:
        with self._lock:
            cp = self._current_patient
        return {
            "running": self._running,
            "folder": str(self.folder),
            "device_id": self.device_id,
            "current_patient": cp[1] if cp else None,
            "seen_count": len(self._seen),
        }
