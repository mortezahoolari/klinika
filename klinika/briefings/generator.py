"""
Morning briefing generator — orchestrates calendar, patient data, and labs
into a prioritized daily briefing.

Directly calls service functions (not the agent loop) for reliable data
gathering, then optionally calls Gemma for AI-generated priority analysis.
"""

from __future__ import annotations

import sqlite3
from typing import Any

import ollama

from klinika.config import CHAT_MODEL, OLLAMA_HOST
from klinika.services.patients import (
    get_todays_appointments,
    get_patient,
    get_diagnoses,
    get_medications,
    get_allergies,
    get_encounters,
)
from klinika.services.labs import get_abnormal_labs, get_lab_values

_LABELS: dict[str, dict[str, str]] = {
    "de": {
        "title": "Tagesbriefing",
        "schedule": "Terminplan",
        "no_appointments": "Keine Termine fuer heute.",
        "no_abnormal": "Keine auffaelligen Werte.",
        "abnormal_labs": "Auffaellige Laborwerte",
        "patient_cards": "Patientenkarten",
        "priorities": "Prioritaeten (KI-Analyse)",
        "notes": "Notizen",
        "diagnoses": "Diagnosen",
        "medications": "Medikamente",
        "allergies": "Allergien",
        "last_encounter": "Letzte Begegnung",
        "abnormal_lab": "Labor (auffaellig)",
        "appointment_note": "Terminnotiz",
        "appointment": "Termin",
        "ai_prompt": (
            "Du bist ein erfahrener Hausarzt. Analysiere die heutigen Patienten und "
            "identifiziere die 2-3 wichtigsten Prioritaeten fuer den Tag. "
            "Begruende kurz, warum diese Patienten besondere Aufmerksamkeit benoetigen.\n\n"
            "Heutige Patienten:\n{summaries}\n\n"
            "Antworte als kurze, praegnante Prioritaetenliste (2-3 Punkte). Auf Deutsch."
        ),
        "time_col": "Zeit",
        "patient_col": "Patient",
        "reason_col": "Grund",
        "notes_col": "Hinweise",
    },
    "en": {
        "title": "Daily Briefing",
        "schedule": "Schedule",
        "no_appointments": "No appointments today.",
        "no_abnormal": "No abnormal values.",
        "abnormal_labs": "Abnormal Lab Values",
        "patient_cards": "Patient Cards",
        "priorities": "Priorities (AI Analysis)",
        "notes": "Notes",
        "diagnoses": "Diagnoses",
        "medications": "Medications",
        "allergies": "Allergies",
        "last_encounter": "Last Encounter",
        "abnormal_lab": "Labs (abnormal)",
        "appointment_note": "Appointment Note",
        "appointment": "Appointment",
        "ai_prompt": (
            "You are an experienced general practitioner. Analyse today's patients and "
            "identify the 2-3 most important priorities for the day. "
            "Briefly explain why these patients require special attention.\n\n"
            "Today's patients:\n{summaries}\n\n"
            "Respond as a short, concise priority list (2-3 points). In English."
        ),
        "time_col": "Time",
        "patient_col": "Patient",
        "reason_col": "Reason",
        "notes_col": "Notes",
    },
}


def _gather_patient_context(conn: sqlite3.Connection, patient_id: str) -> dict[str, Any]:
    """Gather full context for a patient."""
    patient = get_patient(conn, patient_id) or {}
    return {
        "patient": patient,
        "diagnoses": get_diagnoses(conn, patient_id),
        "medications": get_medications(conn, patient_id),
        "allergies": get_allergies(conn, patient_id),
        "encounters": get_encounters(conn, patient_id, limit=3),
        "abnormal_labs": get_abnormal_labs(conn, patient_id),
        "all_labs": get_lab_values(conn, patient_id),
    }


def _format_time(start_time: str) -> str:
    """Extract HH:MM from ISO datetime or raw time."""
    if len(start_time) > 11:
        return start_time[11:16]
    return start_time[:5] if len(start_time) >= 5 else start_time


def _build_schedule_table(
    appointments: list[dict], contexts: dict[str, dict], L: dict[str, str]
) -> str:
    """Build the schedule table section."""
    lines = [
        "## {} ({} {})\n".format(L["schedule"], len(appointments), "Termine" if L["title"] == "Tagesbriefing" else "appointments"),
        "| {} | {} | {} | {} |".format(L["time_col"], L["patient_col"], L["reason_col"], L["notes_col"]),
        "|------|---------|-------|----------|",
    ]
    for appt in appointments:
        time = _format_time(appt["start_time"])
        name = appt["patient_name"]
        visit = appt.get("visit_type") or L["appointment"]
        hints = []
        pid = appt.get("patient_id")
        if pid and pid in contexts:
            ctx = contexts[pid]
            for lab in ctx["abnormal_labs"]:
                flag = "(H)" if lab["flag"] == "H" else "(L)"
                hints.append(f"{lab['test_code']} {flag}")
        hint_str = ", ".join(hints[:3]) if hints else ""
        lines.append(f"| {time} | {name} | {visit} | {hint_str} |")
    return "\n".join(lines) + "\n"


def _build_lab_alerts(all_abnormals: list[dict], L: dict[str, str]) -> str:
    """Build the abnormal lab values section."""
    if not all_abnormals:
        return f"## {L['abnormal_labs']}\n\n{L['no_abnormal']}\n"

    lines = [f"## {L['abnormal_labs']} ({len(all_abnormals)})\n"]
    by_patient: dict[str, list[dict]] = {}
    for a in all_abnormals:
        key = a.get("patient_name", a["patient_id"])
        by_patient.setdefault(key, []).append(a)

    for patient_name, labs in by_patient.items():
        lab_strs = []
        for l in labs:
            flag = "(H)" if l["flag"] == "H" else "(L)"
            lab_strs.append(f"{l['test_name']} {l['value']} {l.get('unit', '')} {flag}")
        lines.append(f"- **{patient_name}:** {', '.join(lab_strs)}")
    return "\n".join(lines) + "\n"


def _build_patient_cards(
    appointments: list[dict], contexts: dict[str, dict], L: dict[str, str]
) -> str:
    """Build detailed patient cards section."""
    lines = [f"## {L['patient_cards']}\n"]
    for appt in appointments:
        pid = appt.get("patient_id")
        if not pid or pid not in contexts:
            lines.append(
                f"### {appt['patient_name']} -- "
                f"{_format_time(appt['start_time'])}, {appt.get('visit_type', L['appointment'])}"
            )
            if appt.get("notes"):
                lines.append(f"- **{L['notes']}:** {appt['notes']}")
            lines.append("")
            continue

        ctx = contexts[pid]
        p = ctx["patient"]
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}"
        lines.append(
            f"### {name} ({pid}) -- "
            f"{_format_time(appt['start_time'])}, {appt.get('visit_type', L['appointment'])}"
        )

        if ctx["diagnoses"]:
            diags = "; ".join(f"{d['icd_code']} {d['description']}" for d in ctx["diagnoses"])
            lines.append(f"- **{L['diagnoses']}:** {diags}")
        if ctx["medications"]:
            meds = "; ".join(
                f"{m['name']} ({m['dosage']})" if m["dosage"] else m["name"]
                for m in ctx["medications"]
            )
            lines.append(f"- **{L['medications']}:** {meds}")
        if ctx["allergies"]:
            lines.append(f"- **{L['allergies']}:** {', '.join(ctx['allergies'])}")
        if ctx["encounters"]:
            last = ctx["encounters"][0]
            lines.append(f"- **{L['last_encounter']}:** {last['date']} -- {last['note']}")
        if ctx["abnormal_labs"]:
            labs = ", ".join(
                f"{l['test_name']} {l['value']}{' (H)' if l['flag'] == 'H' else ' (L)'}"
                for l in ctx["abnormal_labs"]
            )
            lines.append(f"- **{L['abnormal_lab']}:** {labs}")
        if appt.get("notes"):
            lines.append(f"- **{L['appointment_note']}:** {appt['notes']}")
        lines.append("")
    return "\n".join(lines)


def _build_ai_priorities(
    contexts: dict[str, dict], appointments: list[dict], L: dict[str, str]
) -> str:
    """Call Gemma to generate AI priority analysis."""
    patient_summaries = []
    for appt in appointments:
        pid = appt.get("patient_id")
        if not pid or pid not in contexts:
            continue
        ctx = contexts[pid]
        p = ctx["patient"]
        name = f"{p.get('first_name', '')} {p.get('last_name', '')}"
        summary = f"- {name} ({_format_time(appt['start_time'])}, {appt.get('visit_type', '')}): "
        if ctx["diagnoses"]:
            summary += "Diagnosen: " + ", ".join(d["icd_code"] for d in ctx["diagnoses"]) + ". "
        if ctx["abnormal_labs"]:
            summary += (L["abnormal_labs"] if L["title"] == "Daily Briefing" else "Auffaellige Labor") + ": " + ", ".join(
                f"{l['test_name']}={l['value']}" for l in ctx["abnormal_labs"]
            ) + ". "
        if ctx["medications"]:
            count = len(ctx["medications"])
            summary += f"{count} {'medication(s)' if L['title'] == 'Daily Briefing' else 'Medikamente'}."
        patient_summaries.append(summary)

    if not patient_summaries:
        return ""

    prompt = L["ai_prompt"].format(summaries="\n".join(patient_summaries))

    try:
        client = ollama.Client(host=OLLAMA_HOST)
        response = client.chat(
            model=CHAT_MODEL,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.get("message", {}).get("content", "")
        return f"## {L['priorities']}\n\n{content}\n\n"
    except Exception:
        return ""


def stream_briefing(
    conn: sqlite3.Connection,
    date: str,
    use_ai: bool = True,
    lang: str = "de",
):
    """Generator: yield tool progress events, then a final text event with the markdown.

    Yields:
        {"type": "tool",  "name": str, "status": "calling" | "done"}
        {"type": "text",  "content": str}   — full markdown, emitted once at the end
    """
    L = _LABELS.get(lang, _LABELS["de"])

    yield {"type": "tool", "name": "todays_schedule", "status": "calling"}
    appointments = get_todays_appointments(conn, date)
    yield {"type": "tool", "name": "todays_schedule", "status": "done"}

    if not appointments:
        yield {"type": "text", "content": f"# {L['title']} {date}\n\n{L['no_appointments']}\n"}
        return

    contexts: dict[str, dict] = {}
    for appt in appointments:
        pid = appt.get("patient_id")
        if pid and pid not in contexts:
            yield {"type": "tool", "name": "get_patient", "status": "calling"}
            contexts[pid] = _gather_patient_context(conn, pid)
            yield {"type": "tool", "name": "get_patient", "status": "done"}

    yield {"type": "tool", "name": "analyze_labs", "status": "calling"}
    all_abnormals = get_abnormal_labs(conn)
    yield {"type": "tool", "name": "analyze_labs", "status": "done"}

    sections = [f"# {L['title']} {date}\n"]

    if use_ai:
        yield {"type": "tool", "name": "generate_priorities", "status": "calling"}
        ai_section = _build_ai_priorities(contexts, appointments, L)
        yield {"type": "tool", "name": "generate_priorities", "status": "done"}
        if ai_section:
            sections.append(ai_section)

    sections.append(_build_schedule_table(appointments, contexts, L))
    sections.append(_build_lab_alerts(all_abnormals, L))
    sections.append(_build_patient_cards(appointments, contexts, L))

    yield {"type": "text", "content": "\n".join(sections)}


def generate_briefing(
    conn: sqlite3.Connection,
    date: str,
    use_ai: bool = True,
    lang: str = "de",
) -> str:
    """Generate a morning briefing for the given date. Returns markdown."""
    for event in stream_briefing(conn, date, use_ai=use_ai, lang=lang):
        if event["type"] == "text":
            return event["content"]
    return ""
