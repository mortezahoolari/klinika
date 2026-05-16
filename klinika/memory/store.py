"""
SQLite-backed memory store with embedding-based recall.

Uses nomic-embed-text via Ollama for semantic search over stored facts.
Designed for MVP scale (<10K facts) — pure numpy cosine similarity.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import ollama

from klinika.config import DB_PATH, EMBED_MODEL, OLLAMA_HOST

_client = ollama.Client(host=OLLAMA_HOST)


def init_db(path: str | None = None) -> sqlite3.Connection:
    """Create the facts table if it doesn't exist. Returns connection."""
    db_path = path or DB_PATH
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS facts (
            id TEXT PRIMARY KEY,
            subject TEXT NOT NULL,
            predicate TEXT NOT NULL,
            object TEXT NOT NULL,
            embedding BLOB NOT NULL,
            source TEXT,
            created_at TEXT NOT NULL
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_facts_subject ON facts(subject)
    """)
    conn.commit()
    return conn


def embed(text: str) -> np.ndarray:
    """Generate embedding vector via Ollama nomic-embed-text."""
    response = _client.embed(model=EMBED_MODEL, input=text)
    # ollama.embed returns {"embeddings": [[...vector...]]}
    vector = response["embeddings"][0]
    return np.array(vector, dtype=np.float32)


def store_fact(
    conn: sqlite3.Connection,
    subject: str,
    predicate: str,
    obj: str,
    source: str = "user",
) -> str:
    """Store a fact with its embedding. Returns the fact ID."""
    fact_id = str(uuid.uuid4())[:8]
    text = f"{subject} {predicate} {obj}"
    vector = embed(text)
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        "INSERT INTO facts (id, subject, predicate, object, embedding, source, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (fact_id, subject, predicate, obj, vector.tobytes(), source, now),
    )
    conn.commit()
    return fact_id


def recall(
    conn: sqlite3.Connection,
    query: str,
    k: int = 5,
) -> list[dict[str, Any]]:
    """Retrieve top-k facts by cosine similarity to query."""
    query_vec = embed(query)

    rows = conn.execute(
        "SELECT id, subject, predicate, object, embedding FROM facts"
    ).fetchall()

    if not rows:
        return []

    scored = []
    for row_id, subj, pred, obj, emb_bytes in rows:
        stored_vec = np.frombuffer(emb_bytes, dtype=np.float32)
        # Cosine similarity
        dot = np.dot(query_vec, stored_vec)
        norm = np.linalg.norm(query_vec) * np.linalg.norm(stored_vec)
        score = float(dot / norm) if norm > 0 else 0.0
        scored.append({
            "id": row_id,
            "subject": subj,
            "predicate": pred,
            "object": obj,
            "score": round(score, 4),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:k]


def list_facts(
    conn: sqlite3.Connection,
    subject_filter: str | None = None,
) -> list[dict[str, str]]:
    """List all facts, optionally filtered by subject."""
    if subject_filter:
        rows = conn.execute(
            "SELECT id, subject, predicate, object FROM facts WHERE subject LIKE ?",
            (f"%{subject_filter}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, subject, predicate, object FROM facts"
        ).fetchall()

    return [
        {"id": r[0], "subject": r[1], "predicate": r[2], "object": r[3]}
        for r in rows
    ]
