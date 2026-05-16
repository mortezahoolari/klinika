"""LDT tools — import lab results and query lab values."""

from __future__ import annotations

import sqlite3

from klinika.standards.ldt import parse_ldt
from klinika.services.labs import upsert_lab_result, get_lab_values, get_abnormal_labs

_conn: sqlite3.Connection | None = None


def set_connection(conn: sqlite3.Connection) -> None:
    global _conn
    _conn = conn


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Lab DB not initialized.")
    return _conn


def import_lab_results(path: str) -> str:
    """Import lab results from an LDT file into the database."""
    data = parse_ldt(path)
    total_values = 0
    for result in data.results:
        total_values += upsert_lab_result(_get_conn(), result)

    abnormals = get_abnormal_labs(_get_conn())
    return (
        f"{len(data.results)} lab reports imported with {total_values} values. "
        f"{len(abnormals)} abnormal values (H/L)."
    )


def query_lab_values(patient_id: str, test_code: str = "") -> str:
    """Get lab values for a patient, optionally filtered by test code."""
    values = get_lab_values(_get_conn(), patient_id, test_code if test_code else None)
    if not values:
        filter_text = f" ({test_code})" if test_code else ""
        return f"No lab values{filter_text} found for patient {patient_id}."
    lines = [f"Lab values for patient {patient_id}:"]
    for v in values:
        flag_marker = " (H)" if v["flag"] == "H" else " (L)" if v["flag"] == "L" else ""
        ref = f" (Ref: {v['ref_low']}-{v['ref_high']})" if v["ref_low"] else ""
        lines.append(f"  - {v['test_name']}: {v['value']} {v['unit']}{flag_marker}{ref}")
    return "\n".join(lines)


def flag_abnormals(patient_id: str = "") -> str:
    """Show all abnormal lab values, optionally filtered by patient."""
    abnormals = get_abnormal_labs(_get_conn(), patient_id if patient_id else None)
    if not abnormals:
        return "No abnormal lab values found."

    lines = ["Abnormal lab values:"]
    current_patient = ""
    for a in abnormals:
        if a["patient_name"] != current_patient:
            current_patient = a["patient_name"]
            lines.append(f"\n  **{current_patient}** (ID: {a['patient_id']}):")
        flag_marker = "(H)" if a["flag"] == "H" else "(L)"
        lines.append(
            f"    - {a['test_name']}: {a['value']} {a['unit']} {flag_marker} "
            f"(Ref: {a['ref_low']}-{a['ref_high']})"
        )
    return "\n".join(lines)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "import_lab_results",
            "description": "Import lab results from an LDT file into the database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the LDT file"},
                },
                "required": ["path"],
            },
        },
        "callable": import_lab_results,
    },
]
