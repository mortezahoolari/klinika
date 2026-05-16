"""Drafting tools — create, list, and retrieve clinical document drafts."""

from __future__ import annotations

import sqlite3

from klinika.drafting.generator import build_draft_context, store_draft
from klinika.drafting.templates import DRAFT_TYPE_LABELS
from klinika.services.drafts import get_draft as db_get_draft, list_drafts as db_list_drafts
from klinika.services.patients import resolve_patient

_conn: sqlite3.Connection | None = None


def set_connection(conn: sqlite3.Connection) -> None:
    global _conn
    _conn = conn


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Drafts DB not initialized.")
    return _conn


def create_draft(type: str, patient_name: str, context: str) -> str:
    """Fetch patient context for a clinical document draft.

    Returns structured patient data. The agent writes the actual draft text
    in German as its response — no second Ollama call needed.
    """
    conn = _get_conn()
    resolved = resolve_patient(conn, patient_name)
    if not resolved:
        return f"No patient found matching '{patient_name}'."
    patient_id, full_name = resolved
    try:
        return build_draft_context(conn, type, patient_id, context)
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error building draft context: {e}"


def save_draft(type: str, patient_id: str, content: str, context: str = "") -> str:
    """Save a completed draft text to the database."""
    try:
        draft_id = store_draft(_get_conn(), type, patient_id, context, content)
        label = DRAFT_TYPE_LABELS.get(type, type)
        return f"{label} saved as Draft {draft_id}."
    except Exception as e:
        return f"Error saving draft: {e}"


def list_drafts(patient_id: str = "") -> str:
    """List recent drafts, optionally filtered by patient."""
    drafts = db_list_drafts(
        _get_conn(),
        patient_id=patient_id if patient_id else None,
    )
    if not drafts:
        return "No drafts available."
    lines = ["Recent drafts:"]
    for d in drafts:
        label = DRAFT_TYPE_LABELS.get(d["type"], d["type"])
        lines.append(
            f"  - [{d['id']}] {label} for patient {d['patient_id']} "
            f"({d['status']}) — {d['created_at'][:16]}"
        )
    return "\n".join(lines)


def get_draft(draft_id: str) -> str:
    """Retrieve a stored draft by ID."""
    draft = db_get_draft(_get_conn(), draft_id)
    if not draft:
        return f"No draft found with ID {draft_id}."
    label = DRAFT_TYPE_LABELS.get(draft["type"], draft["type"])
    return (
        f"--- {label} (Draft {draft['id']}) ---\n\n"
        f"{draft['content']}\n\n"
        f"--- End of draft ---\n"
        f"Patient: {draft['patient_id']} | Status: {draft['status']} | "
        f"Created: {draft['created_at'][:16]}"
    )


TOOLS: list = []

_TOOLS_UNUSED = [
    {
        "type": "function",
        "function": {
            "name": "create_draft",
            "description": (
                "Fetch patient context for a clinical document draft (referral, doctor's letter, "
                "prescription, sick note, SOAP). Returns structured patient data — the agent then "
                "writes the actual draft text in German as its response. "
                "Document content is always in German (required for German clinical software)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "Document type: 'ueberweisung' (referral), 'arztbrief' (doctor's letter), 'rezept' (prescription), 'au' (sick note), 'soap'",
                        "enum": ["ueberweisung", "arztbrief", "rezept", "au", "soap"],
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Patient name (e.g. 'Becker', 'Hans Becker')",
                    },
                    "context": {
                        "type": "string",
                        "description": "Context/reason for the draft (e.g. 'suspected CHD, referral to cardiology')",
                    },
                },
                "required": ["type", "patient_id", "context"],
            },
        },
        "callable": create_draft,
    },
    {
        "type": "function",
        "function": {
            "name": "save_draft",
            "description": "Save a completed draft text to the database after writing it.",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "enum": ["ueberweisung", "arztbrief", "rezept", "au", "soap"],
                    },
                    "patient_id": {"type": "string"},
                    "content": {"type": "string", "description": "The full draft text in German"},
                    "context": {"type": "string", "description": "Original request context"},
                },
                "required": ["type", "patient_id", "content"],
            },
        },
        "callable": save_draft,
    },
    {
        "type": "function",
        "function": {
            "name": "list_drafts",
            "description": "List recent document drafts, optionally filtered by patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patient_id": {"type": "string", "description": "Optional: only drafts for this patient"},
                },
                "required": [],
            },
        },
        "callable": list_drafts,
    },
    {
        "type": "function",
        "function": {
            "name": "get_draft",
            "description": "Retrieve a stored draft by its ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "draft_id": {"type": "string", "description": "Draft ID"},
                },
                "required": ["draft_id"],
            },
        },
        "callable": get_draft,
    },
]
