"""Tests for the memory store (SQLite + mocked embeddings)."""

import tempfile
from pathlib import Path
from unittest.mock import patch

import numpy as np

from klinika.memory.store import init_db, store_fact, recall, list_facts


def _mock_embed(text: str) -> np.ndarray:
    """Deterministic mock embedding: hash text into a 10-dim vector."""
    h = hash(text) % (2**32)
    rng = np.random.RandomState(h)
    vec = rng.randn(10).astype(np.float32)
    return vec / np.linalg.norm(vec)  # unit normalize


@patch("klinika.memory.store.embed", side_effect=_mock_embed)
class TestMemoryStore:

    def _tmp_db(self):
        """Create a temp DB for testing."""
        tmp = tempfile.mktemp(suffix=".db")
        return init_db(tmp)

    def test_init_creates_table(self, mock_embed):
        conn = self._tmp_db()
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        table_names = [t[0] for t in tables]
        assert "facts" in table_names
        conn.close()

    def test_store_and_list(self, mock_embed):
        conn = self._tmp_db()
        fact_id = store_fact(conn, "Frau Müller", "bevorzugt", "Morgentermine")
        assert fact_id  # non-empty

        facts = list_facts(conn)
        assert len(facts) == 1
        assert facts[0]["subject"] == "Frau Müller"
        assert facts[0]["predicate"] == "bevorzugt"
        assert facts[0]["object"] == "Morgentermine"
        conn.close()

    def test_store_multiple_and_list_filtered(self, mock_embed):
        conn = self._tmp_db()
        store_fact(conn, "Frau Müller", "bevorzugt", "Morgentermine")
        store_fact(conn, "Herr Schmidt", "allergisch gegen", "Penicillin")
        store_fact(conn, "Frau Müller", "ist", "Diabetikerin")

        all_facts = list_facts(conn)
        assert len(all_facts) == 3

        mueller_facts = list_facts(conn, subject_filter="Müller")
        assert len(mueller_facts) == 2
        conn.close()

    def test_recall_returns_relevant(self, mock_embed):
        conn = self._tmp_db()
        store_fact(conn, "Frau Müller", "bevorzugt", "Morgentermine")
        store_fact(conn, "Herr Schmidt", "allergisch gegen", "Penicillin")
        store_fact(conn, "Praxis", "öffnet um", "08:00")

        results = recall(conn, "Müller Termine", k=2)
        assert len(results) <= 2
        # All results should have a score
        for r in results:
            assert "score" in r
            assert isinstance(r["score"], float)
        conn.close()

    def test_recall_empty_db(self, mock_embed):
        conn = self._tmp_db()
        results = recall(conn, "anything")
        assert results == []
        conn.close()

    def test_recall_ordering(self, mock_embed):
        conn = self._tmp_db()
        store_fact(conn, "A", "is", "alpha")
        store_fact(conn, "B", "is", "beta")
        store_fact(conn, "C", "is", "gamma")

        results = recall(conn, "test query", k=3)
        # Results should be sorted by score descending
        scores = [r["score"] for r in results]
        assert scores == sorted(scores, reverse=True)
        conn.close()
