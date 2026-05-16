"""Calendar tools — sync today's appointments from Doctolib or PVS export."""

from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from klinika.services.patients import upsert_appointment, get_todays_appointments

_conn: sqlite3.Connection | None = None


def set_connection(conn: sqlite3.Connection) -> None:
    global _conn
    _conn = conn


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Patient DB not initialized.")
    return _conn


def sync_doctolib(path: str) -> str:
    """Read Doctolib calendar JSON and sync appointments into SQLite."""
    content = Path(path).read_text(encoding="utf-8")
    data = json.loads(content)
    appointments = data.get("appointments", [])

    for appt in appointments:
        upsert_appointment(_get_conn(), appt)

    date_range = data.get("date_range", {})
    return (
        f"{len(appointments)} appointments synced "
        f"({date_range.get('start', '?')} to {date_range.get('end', '?')})."
    )


def todays_schedule() -> str:
    """Show today's appointments with patient context."""
    today = date.today().isoformat()
    appointments = get_todays_appointments(_get_conn(), today)

    if not appointments:
        return f"No appointments today ({today})."

    lines = [f"Schedule for {today} ({len(appointments)} total):"]
    for appt in appointments:
        time_str = appt["start_time"][11:16] if len(appt["start_time"]) > 11 else appt["start_time"]
        lines.append(
            f"  {time_str} — {appt['patient_name']} "
            f"({appt['visit_type'] or 'Appointment'})"
            f"{' — ' + appt['notes'] if appt.get('notes') else ''}"
        )
    return "\n".join(lines)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "sync_doctolib",
            "description": (
                "Sync appointments from a Doctolib calendar JSON file. "
                "Links appointments to existing patients from the BDT import."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the Doctolib calendar JSON file",
                    },
                },
                "required": ["path"],
            },
        },
        "callable": sync_doctolib,
    },
    {
        "type": "function",
        "function": {
            "name": "todays_schedule",
            "description": "Show today's appointment schedule with patient context.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        "callable": todays_schedule,
    },
]
