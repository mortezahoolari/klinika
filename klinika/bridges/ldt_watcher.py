"""
LDT live folder watcher — automatically imports lab results as labGate drops them.

How it works:
  1. Configure KLINIKA_LDT_FOLDER to the same folder labGate (or your lab middleware)
     writes .ldt files to — the same folder your PVS already watches.
  2. This watcher polls the folder every 20 seconds for new .ldt files.
  3. On detection: waits 5 seconds (Windows race condition fix), parses via the
     existing LDT parser, upserts all lab values into the DB.
  4. Processed files are moved to {folder}/processed/ to prevent re-import.
  5. Files that fail to parse are moved to {folder}/failed/ so nothing is lost.

No doctor interaction needed — lab results appear automatically before the morning
briefing, just as they would in the PVS.
"""

from __future__ import annotations

import logging
import shutil
import sqlite3
import threading
import time
from pathlib import Path

from klinika.standards.ldt import parse_ldt
from klinika.services.labs import upsert_lab_result

logger = logging.getLogger(__name__)

_FILE_SETTLE_SECONDS = 5
_POLL_INTERVAL_SECONDS = 20


class LDTWatcher:
    """Polls a folder for new .ldt files and auto-imports them into the DB.

    Instantiate once and call start(). Runs as a daemon thread.
    """

    def __init__(self, folder: Path, conn: sqlite3.Connection) -> None:
        self.folder = Path(folder)
        self._conn = conn
        self._seen: set[str] = set()
        self._running = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._processed_count = 0
        self._last_import: str | None = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True, name="ldt-watcher")
        self._thread.start()
        logger.info("LDT watcher started — watching %s", self.folder)

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=30)

    # ------------------------------------------------------------------
    # Poll loop
    # ------------------------------------------------------------------

    def _poll_loop(self) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        processed_dir = self.folder / "processed"
        processed_dir.mkdir(exist_ok=True)
        failed_dir = self.folder / "failed"
        failed_dir.mkdir(exist_ok=True)

        # Pre-populate seen set from already-processed files (restart-safe)
        with self._lock:
            self._seen = {p.name for p in processed_dir.glob("*.ldt")}
            self._seen |= {p.name for p in failed_dir.glob("*.ldt")}

        while self._running:
            try:
                for path in sorted(self.folder.glob("*.ldt")):
                    if path.name not in self._seen:
                        # Wait for file to be fully written
                        time.sleep(_FILE_SETTLE_SECONDS)
                        self._handle_file(path)
            except Exception:
                logger.exception("LDT watcher poll error")
            time.sleep(_POLL_INTERVAL_SECONDS)

    def _handle_file(self, path: Path) -> None:
        processed_dir = self.folder / "processed"
        failed_dir = self.folder / "failed"

        try:
            data = parse_ldt(path)
            count = 0
            for result in data.results:
                count += upsert_lab_result(self._conn, result)

            dest = processed_dir / path.name
            shutil.move(str(path), str(dest))

            with self._lock:
                self._seen.add(path.name)
                self._processed_count += 1
                self._last_import = path.name

            logger.info("LDT watcher: imported %s (%d values)", path.name, count)

        except Exception:
            logger.exception("LDT watcher: failed to import %s", path.name)
            try:
                dest = failed_dir / path.name
                shutil.move(str(path), str(dest))
            except Exception:
                pass
            with self._lock:
                self._seen.add(path.name)

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._running,
                "folder": str(self.folder),
                "processed_count": self._processed_count,
                "last_import": self._last_import,
            }
