"""Patient tools — action-oriented clinical queries.

Design: one tool per clinical thought. Patient names accepted as input;
ID resolution is handled internally by each tool.
"""

from __future__ import annotations

import sqlite3

from klinika.services import patients as svc
from klinika.services.labs import get_lab_values, get_abnormal_labs

_conn: sqlite3.Connection | None = None


def set_connection(conn: sqlite3.Connection) -> None:
    global _conn
    _conn = conn


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Patient DB not initialized.")
    return _conn


def get_patient(name: str) -> str:
    """Get the full clinical profile for a patient by name."""
    conn = _get_conn()
    resolved = svc.resolve_patient(conn, name)
    if not resolved:
        return f"No patient found matching '{name}'."
    patient_id, full_name = resolved

    p = svc.get_patient(conn, patient_id)
    sex_label = {"1": "male", "2": "female"}.get(p.get("sex", ""), p.get("sex", ""))
    lines = [
        f"Patient: {full_name} (ID: {patient_id})",
        f"  DOB: {p.get('dob', '?')} | Sex: {sex_label}",
        f"  Address: {p.get('street', '')}, {p.get('zip_code', '')} {p.get('city', '')}",
        f"  Phone: {p.get('phone', '')} | Insurance: {p.get('insurance', '')}",
    ]

    allergies = svc.get_allergies(conn, patient_id)
    lines.append(f"  Allergies: {', '.join(allergies)}" if allergies else "  Allergies: none known")

    diags = svc.get_diagnoses(conn, patient_id)
    if diags:
        lines.append("Diagnoses:")
        for d in diags:
            lines.append(f"  - {d['icd_code']}: {d['description']}")

    meds = svc.get_medications(conn, patient_id)
    if meds:
        lines.append("Medications:")
        for m in meds:
            lines.append(f"  - {m['name']} ({m['dosage']})" if m["dosage"] else f"  - {m['name']}")

    encs = svc.get_encounters(conn, patient_id, limit=3)
    if encs:
        lines.append("Recent encounters:")
        for e in encs:
            lines.append(f"  - {e['date']}: {e['note']}")

    labs = get_lab_values(conn, patient_id)
    if labs:
        lines.append("Lab values:")
        for v in labs[:10]:
            flag = " (H)" if v["flag"] == "H" else " (L)" if v["flag"] == "L" else ""
            ref = f" (Ref: {v['ref_low']}-{v['ref_high']})" if v["ref_low"] else ""
            lines.append(f"  - {v['test_name']}: {v['value']} {v['unit']}{flag}{ref}")

    return "\n".join(lines)


def search_patients(
    diagnosis: str = "",
    medication: str = "",
    abnormal_labs: bool = False,
) -> str:
    """Find patients by diagnosis, medication, or abnormal lab values."""
    conn = _get_conn()

    if abnormal_labs:
        abnormals = get_abnormal_labs(conn)
        if not abnormals:
            return "No patients with abnormal lab values."
        lines = ["Patients with abnormal lab values:"]
        current_pid = ""
        for a in abnormals:
            if a["patient_id"] != current_pid:
                current_pid = a["patient_id"]
                lines.append(f"\n  {a['patient_name']} (ID: {a['patient_id']}):")
            flag = "(H)" if a["flag"] == "H" else "(L)"
            lines.append(
                f"    - {a['test_name']}: {a['value']} {a['unit']} {flag} "
                f"(Ref: {a['ref_low']}-{a['ref_high']})"
            )
        return "\n".join(lines)

    results = svc.search_patients(
        conn,
        diagnosis=diagnosis if diagnosis else None,
        medication=medication if medication else None,
    )
    if not results:
        return "No matching patients found."
    lines = [f"Found {len(results)} patient(s):"]
    for r in results:
        detail = r.get("icd_code") or r.get("medication", "")
        lines.append(f"  {r['first_name']} {r['last_name']} (ID: {r['id']}) — {detail}")
    return "\n".join(lines)


def add_observation(patient_name: str, note: str) -> str:
    """Save a clinical observation or note for a patient (by name)."""
    conn = _get_conn()
    resolved = svc.resolve_patient(conn, patient_name)
    if not resolved:
        return f"No patient found matching '{patient_name}'."
    patient_id, full_name = resolved
    return svc.add_observation(conn, patient_id, note)


def current_patient() -> str:
    """Show the current patient based on today's schedule and current time."""
    result = svc.current_patient(_get_conn())
    if not result:
        return "No current patient in today's schedule."
    return f"Current patient: {result['patient_name']} ({result['visit_type']})"


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_patient",
            "description": (
                "Get the full clinical profile for a patient by name: demographics, "
                "diagnoses, medications, allergies, recent encounters, and lab values — "
                "all in one call. Use this for any question about a specific patient."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Patient name or partial name (e.g. 'Schmidt', 'Karl Schmidt')",
                    },
                },
                "required": ["name"],
            },
        },
        "callable": get_patient,
    },
    {
        "type": "function",
        "function": {
            "name": "search_patients",
            "description": (
                "Find patients matching a diagnosis (ICD code or text), medication name, "
                "or patients with abnormal lab values. Set abnormal_labs=true to find "
                "all patients with out-of-range lab results."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "diagnosis": {
                        "type": "string",
                        "description": "ICD code or diagnosis text (e.g. 'E11', 'Diabetes')",
                    },
                    "medication": {
                        "type": "string",
                        "description": "Medication name (e.g. 'Metformin')",
                    },
                    "abnormal_labs": {
                        "type": "boolean",
                        "description": "If true, return all patients with out-of-range (H/L) lab values",
                    },
                },
                "required": [],
            },
        },
        "callable": search_patients,
    },
    {
        "type": "function",
        "function": {
            "name": "add_observation",
            "description": "Save a clinical observation or note for a patient (by name).",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Patient name (e.g. 'Schmidt', 'Karl Schmidt')",
                    },
                    "note": {
                        "type": "string",
                        "description": "The clinical observation (e.g. 'Patient reports dizziness since yesterday')",
                    },
                },
                "required": ["patient_name", "note"],
            },
        },
        "callable": add_observation,
    },
    {
        "type": "function",
        "function": {
            "name": "current_patient",
            "description": "Show the current patient based on today's schedule and current time.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        "callable": current_patient,
    },
]
