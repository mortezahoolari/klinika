"""Draft context builder — fetches patient data and formats it for the agent to write.

The agent generates the actual draft text using its own active Ollama session.
This avoids a second concurrent Ollama call which causes a 500 conflict.
"""

from __future__ import annotations

import sqlite3

from klinika.drafting.templates import DRAFT_TYPE_LABELS
from klinika.services.patients import (
    get_patient,
    get_diagnoses,
    get_medications,
    get_allergies,
    get_encounters,
)
from klinika.services.labs import get_lab_values
from klinika.services.drafts import save_draft


def _format_patient_summary(patient: dict) -> str:
    sex = {"1": "männlich", "2": "weiblich"}.get(patient.get("sex", ""), "")
    return (
        f"{patient['first_name']} {patient['last_name']} "
        f"(ID: {patient['id']}, geb. {patient.get('dob', '?')}, {sex}), "
        f"Kasse: {patient.get('insurance', '?')}"
    )


def _format_list(items: list[dict], key_fields: list[str]) -> str:
    if not items:
        return "Keine Einträge."
    lines = []
    for item in items:
        parts = [str(item.get(k, "")) for k in key_fields if item.get(k)]
        lines.append("- " + " | ".join(parts))
    return "\n".join(lines)


def _format_lab_values(values: list[dict]) -> str:
    if not values:
        return "Keine Laborwerte vorhanden."
    lines = []
    for v in values:
        flag = ""
        if v.get("flag") == "H":
            flag = " (ERHOEHT)"
        elif v.get("flag") == "L":
            flag = " (ERNIEDRIGT)"
        ref = f" [Ref: {v['ref_low']}-{v['ref_high']}]" if v.get("ref_low") else ""
        lines.append(f"- {v['test_name']}: {v['value']} {v.get('unit', '')}{flag}{ref}")
    return "\n".join(lines)


def build_draft_context(
    conn: sqlite3.Connection,
    draft_type: str,
    patient_id: str,
    context: str,
) -> str:
    """Fetch patient data and return a structured context string for the agent to write from.

    No Ollama call — the agent generates the actual draft text using its own session.
    """
    patient = get_patient(conn, patient_id)
    if not patient:
        raise ValueError(f"Patient {patient_id} not found.")

    valid_types = ["ueberweisung", "arztbrief", "rezept", "au", "soap"]
    if draft_type not in valid_types:
        raise ValueError(f"Unknown draft type: {draft_type}. Available: {', '.join(valid_types)}")

    diagnoses = get_diagnoses(conn, patient_id)
    medications = get_medications(conn, patient_id)
    allergies = get_allergies(conn, patient_id)
    encounters = get_encounters(conn, patient_id, limit=5)
    lab_values = get_lab_values(conn, patient_id)

    label = DRAFT_TYPE_LABELS.get(draft_type, draft_type)

    lines = [
        f"=== PATIENT CONTEXT ({label.upper()}) ===",
        "",
        "=== PATIENT ===",
        _format_patient_summary(patient),
        "",
        "=== DIAGNOSEN ===",
        _format_list(diagnoses, ["icd_code", "description"]),
        "",
        "=== MEDIKATION ===",
        _format_list(medications, ["name", "dosage"]),
        "",
        "=== ALLERGIEN ===",
        ", ".join(allergies) if allergies else "Keine bekannt.",
        "",
        "=== LETZTE BEGEGNUNGEN ===",
        _format_list(encounters, ["date", "note"]),
        "",
        "=== LABORWERTE ===",
        _format_lab_values(lab_values),
        "",
        f"=== GRUND / KONTEXT ===",
        context,
    ]
    return "\n".join(lines)


def store_draft(
    conn: sqlite3.Connection,
    draft_type: str,
    patient_id: str,
    context: str,
    content: str,
) -> str:
    """Save a completed draft to the database. Returns draft_id."""
    return save_draft(conn, draft_type, patient_id, context, content)
