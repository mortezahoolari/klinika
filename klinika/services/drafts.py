"""Drafts database — stores generated clinical document drafts."""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone


def init_drafts_db(conn: sqlite3.Connection) -> None:
    """Create the drafts table if it doesn't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS drafts (
            id TEXT PRIMARY KEY,
            type TEXT NOT NULL,
            patient_id TEXT REFERENCES patients(id),
            context TEXT,
            content TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_drafts_patient ON drafts(patient_id);
        CREATE INDEX IF NOT EXISTS idx_drafts_type ON drafts(type);
    """)


def save_draft(
    conn: sqlite3.Connection,
    draft_type: str,
    patient_id: str,
    context: str,
    content: str,
) -> str:
    """Save a generated draft. Returns the draft ID."""
    draft_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO drafts (id, type, patient_id, context, content, status, created_at) "
        "VALUES (?, ?, ?, ?, ?, 'pending', ?)",
        (draft_id, draft_type, patient_id, context, content, now),
    )
    conn.commit()
    return draft_id


def get_draft(conn: sqlite3.Connection, draft_id: str) -> dict | None:
    """Retrieve a stored draft by ID."""
    row = conn.execute(
        "SELECT id, type, patient_id, context, content, status, created_at "
        "FROM drafts WHERE id = ?",
        (draft_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "type": row[1], "patient_id": row[2],
        "context": row[3], "content": row[4], "status": row[5],
        "created_at": row[6],
    }


def list_drafts(
    conn: sqlite3.Connection,
    patient_id: str | None = None,
    status: str | None = None,
) -> list[dict]:
    """List drafts, optionally filtered by patient and/or status."""
    query = "SELECT id, type, patient_id, context, status, created_at FROM drafts"
    conditions = []
    params = []
    if patient_id:
        conditions.append("patient_id = ?")
        params.append(patient_id)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if conditions:
        query += " WHERE " + " AND ".join(conditions)
    query += " ORDER BY created_at DESC LIMIT 20"

    rows = conn.execute(query, params).fetchall()
    return [
        {"id": r[0], "type": r[1], "patient_id": r[2],
         "context": r[3], "status": r[4], "created_at": r[5]}
        for r in rows
    ]


def update_draft_status(conn: sqlite3.Connection, draft_id: str, status: str) -> None:
    """Update draft status (pending/accepted/rejected)."""
    conn.execute("UPDATE drafts SET status = ? WHERE id = ?", (status, draft_id))
    conn.commit()
