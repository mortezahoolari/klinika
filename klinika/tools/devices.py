"""Device tools — import and query GDT exam results from medical devices."""

from __future__ import annotations

import sqlite3

from klinika.standards.gdt import parse_gdt
from klinika.services.devices import upsert_device_result, get_device_results, list_recent_results
from klinika.services.patients import resolve_patient

_conn: sqlite3.Connection | None = None


def set_connection(conn: sqlite3.Connection) -> None:
    global _conn
    _conn = conn


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Device DB not initialized.")
    return _conn


def import_device_result(path: str) -> str:
    """Import a GDT device result file into the database."""
    results = parse_gdt(path)
    total = 0
    summaries = []
    for result in results:
        count = upsert_device_result(_get_conn(), result)
        total += count
        finding_text = result.finding[:80] + "..." if len(result.finding) > 80 else result.finding
        summaries.append(
            f"Device {result.device_id}, patient {result.patient_id}: "
            f"{count} measurements. Finding: {finding_text}"
        )
    return (
        f"{len(results)} exam(s) imported with {total} measurements.\n"
        + "\n".join(summaries)
    )


def query_device_results(patient_name: str, device_type: str = "") -> str:
    """Get device results (ECG, spirometry, blood pressure) for a patient by name."""
    conn = _get_conn()
    resolved = resolve_patient(conn, patient_name)
    if not resolved:
        return f"No patient found matching '{patient_name}'."
    patient_id, full_name = resolved

    results = get_device_results(conn, patient_id, device_id=device_type if device_type else None)
    if not results:
        filter_text = f" (device: {device_type})" if device_type else ""
        return f"No device results{filter_text} found for {full_name}."

    lines = [f"Device results for {full_name}:"]
    current_exam = ""
    for r in results:
        exam_key = f"{r['device_id']}_{r['exam_date']}"
        if exam_key != current_exam:
            current_exam = exam_key
            lines.append(f"\n  Device: {r['device_id']} | Date: {r['exam_date']} | Time: {r['exam_time']}")
            if r["finding"]:
                lines.append(f"  Finding: {r['finding']}")
        ref = f" (Ref: {r['ref_low']}-{r['ref_high']})" if r["ref_low"] else ""
        unit = f" {r['unit']}" if r["unit"] else ""
        lines.append(f"    - {r['test_name']}: {r['value']}{unit}{ref}")
    return "\n".join(lines)


def list_device_results() -> str:
    """Show all recent device exam results across patients."""
    results = list_recent_results(_get_conn())
    if not results:
        return "No device results available."
    lines = ["Recent device results:"]
    for r in results:
        finding_short = r["finding"][:60] + "..." if len(r.get("finding", "") or "") > 60 else r.get("finding", "")
        lines.append(
            f"  - {r['patient_name']} ({r['patient_id']}): "
            f"{r['device_id']} on {r['exam_date']} - {finding_short}"
        )
    return "\n".join(lines)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "import_device_result",
            "description": "Import device exam results from a GDT file (e.g. ECG, spirometry, blood pressure).",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to the GDT file"},
                },
                "required": ["path"],
            },
        },
        "callable": import_device_result,
    },
    {
        "type": "function",
        "function": {
            "name": "query_device_results",
            "description": "Show device results (ECG, spirometry, blood pressure etc.) for a patient by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_name": {
                        "type": "string",
                        "description": "Patient name (e.g. 'Becker', 'Hans Becker')",
                    },
                    "device_type": {
                        "type": "string",
                        "description": "Optional: device type filter (e.g. 'EKG1', 'SPIR', 'RR01')",
                    },
                },
                "required": ["patient_name"],
            },
        },
        "callable": query_device_results,
    },
    {
        "type": "function",
        "function": {
            "name": "list_device_results",
            "description": "Show all recent device exam results across all patients.",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
        "callable": list_device_results,
    },
]
