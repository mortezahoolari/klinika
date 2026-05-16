"""BDT tools — bootstrap and incremental import from PVS exports."""

from __future__ import annotations

import sqlite3

from klinika.standards.bdt import parse_bdt
from klinika.services.patients import (
    upsert_patient,
    upsert_encounter,
    upsert_diagnosis,
    upsert_medication,
    get_patient_count,
)

_conn: sqlite3.Connection | None = None


def set_connection(conn: sqlite3.Connection) -> None:
    global _conn
    _conn = conn


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Patient DB not initialized.")
    return _conn


def _import_bdt(path: str) -> dict[str, int]:
    """Parse BDT file and upsert all records. Returns counts."""
    conn = _get_conn()
    data = parse_bdt(path)

    for patient in data.patients:
        upsert_patient(conn, patient)
    for encounter in data.encounters:
        upsert_encounter(conn, encounter)
    for diagnosis in data.diagnoses:
        upsert_diagnosis(conn, diagnosis)
    for medication in data.medications:
        upsert_medication(conn, medication)

    return {
        "patients": len(data.patients),
        "encounters": len(data.encounters),
        "diagnoses": len(data.diagnoses),
        "medications": len(data.medications),
    }


def bootstrap(path: str) -> str:
    """Import full BDT export from PVS. Populates the entire patient database."""
    counts = _import_bdt(path)
    total = get_patient_count(_get_conn())
    return (
        f"Bootstrap complete: {counts['patients']} patients, "
        f"{counts['encounters']} encounters, {counts['diagnoses']} diagnoses, "
        f"{counts['medications']} medications imported. "
        f"Total patients in database: {total}."
    )


def read_incremental(path: str) -> str:
    """Import incremental BDT (weekly delta). Merges new patients/encounters."""
    counts = _import_bdt(path)
    total = get_patient_count(_get_conn())
    return (
        f"Incremental import: {counts['patients']} new/updated patients, "
        f"{counts['encounters']} new encounters, {counts['diagnoses']} diagnoses, "
        f"{counts['medications']} medications. "
        f"Total patients: {total}."
    )


def patient_count() -> str:
    """Returns the total number of patients in the database."""
    count = get_patient_count(_get_conn())
    return f"{count} patients in database."


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bootstrap",
            "description": (
                "Import a full BDT export from the PVS. "
                "One-time operation at installation — loads all patients, "
                "diagnoses, medications, and encounters."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the BDT file (e.g. data/samples/sample_clinic_bootstrap.bdt)",
                    },
                },
                "required": ["path"],
            },
        },
        "callable": bootstrap,
    },
    {
        "type": "function",
        "function": {
            "name": "read_incremental",
            "description": (
                "Import an incremental BDT export (weekly delta). "
                "Merges new patients and encounters into the database."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to the incremental BDT file",
                    },
                },
                "required": ["path"],
            },
        },
        "callable": read_incremental,
    },
    {
        "type": "function",
        "function": {
            "name": "patient_count",
            "description": "Return the total number of patients in the database.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        "callable": patient_count,
    },
]
