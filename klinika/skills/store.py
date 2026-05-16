"""Skills database — stores reusable named workflows."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone


def init_skills_db(conn: sqlite3.Connection) -> None:
    """Create the skills table if it doesn't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS skills (
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            description TEXT,
            tool_sequence TEXT NOT NULL,
            usage_count INTEGER DEFAULT 0,
            last_used TEXT,
            created_at TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_skills_name ON skills(name);
    """)


def save_skill(
    conn: sqlite3.Connection,
    name: str,
    description: str,
    tool_sequence: list[dict],
) -> str:
    """Save a named skill. Returns skill ID. Raises if name exists."""
    skill_id = str(uuid.uuid4())[:8]
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO skills (id, name, description, tool_sequence, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (skill_id, name, description, json.dumps(tool_sequence, ensure_ascii=False), now),
    )
    conn.commit()
    return skill_id


def get_skill(conn: sqlite3.Connection, name: str) -> dict | None:
    """Get a skill by name."""
    row = conn.execute(
        "SELECT id, name, description, tool_sequence, usage_count, last_used, created_at "
        "FROM skills WHERE name = ?",
        (name,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0], "name": row[1], "description": row[2],
        "tool_sequence": json.loads(row[3]), "usage_count": row[4],
        "last_used": row[5], "created_at": row[6],
    }


def list_skills(conn: sqlite3.Connection) -> list[dict]:
    """List all saved skills."""
    rows = conn.execute(
        "SELECT id, name, description, usage_count, last_used, created_at "
        "FROM skills ORDER BY usage_count DESC, created_at DESC"
    ).fetchall()
    return [
        {"id": r[0], "name": r[1], "description": r[2],
         "usage_count": r[3], "last_used": r[4], "created_at": r[5]}
        for r in rows
    ]


def delete_skill(conn: sqlite3.Connection, name: str) -> bool:
    """Delete a skill by name. Returns True if deleted."""
    cursor = conn.execute("DELETE FROM skills WHERE name = ?", (name,))
    conn.commit()
    return cursor.rowcount > 0


def increment_usage(conn: sqlite3.Connection, name: str) -> None:
    """Increment usage count and update last_used timestamp."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "UPDATE skills SET usage_count = usage_count + 1, last_used = ? WHERE name = ?",
        (now, name),
    )
    conn.commit()
