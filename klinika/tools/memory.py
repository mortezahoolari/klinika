"""Memory tools — remember and recall facts via SQLite + embeddings."""

from __future__ import annotations

import sqlite3
from typing import Any

from klinika.memory import store


# Module-level connection, initialized by stage2_agent
_conn: sqlite3.Connection | None = None


def set_connection(conn: sqlite3.Connection) -> None:
    """Set the shared DB connection for memory tools."""
    global _conn
    _conn = conn


def _get_conn() -> sqlite3.Connection:
    if _conn is None:
        raise RuntimeError("Memory store not initialized. Call set_connection() first.")
    return _conn


def remember(subject: str, predicate: str, object: str) -> str:
    """Store a fact about a subject. Example: remember('Frau Müller', 'bevorzugt', 'Morgentermine')"""
    fact_id = store.store_fact(_get_conn(), subject, predicate, object)
    return f"Stored: {subject} {predicate} {object} (ID: {fact_id})"


def recall(query: str) -> str:
    """Search stored facts by semantic similarity. Returns the most relevant matches."""
    results = store.recall(_get_conn(), query, k=5)
    if not results:
        return "No relevant facts found."
    lines = []
    for r in results:
        lines.append(f"- {r['subject']} {r['predicate']} {r['object']} (relevance: {r['score']})")
    return "\n".join(lines)


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": (
                "Persistently store a fact. Use this to remember important information "
                "about patients, preferences, or clinical facts."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "subject": {
                        "type": "string",
                        "description": "What the fact is about (e.g. 'Frau Müller', 'practice')",
                    },
                    "predicate": {
                        "type": "string",
                        "description": "The relationship or property (e.g. 'prefers', 'is allergic to')",
                    },
                    "object": {
                        "type": "string",
                        "description": "The value or object (e.g. 'morning appointments', 'Penicillin')",
                    },
                },
                "required": ["subject", "predicate", "object"],
            },
        },
        "callable": remember,
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": (
                "Search stored facts by semantic similarity. "
                "Use this to look up what is known about a patient or topic."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query (e.g. 'Frau Müller allergies')",
                    },
                },
                "required": ["query"],
            },
        },
        "callable": recall,
    },
]
