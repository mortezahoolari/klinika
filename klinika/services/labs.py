"""Lab results database — SQLite table for structured lab data."""

from __future__ import annotations

import sqlite3
from typing import Any

from klinika.standards.ldt import LabResult, LabValue


def init_lab_db(conn: sqlite3.Connection) -> None:
    """Create the lab_results table if it doesn't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS lab_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT REFERENCES patients(id),
            test_code TEXT,
            test_name TEXT,
            value TEXT,
            unit TEXT,
            ref_low TEXT,
            ref_high TEXT,
            flag TEXT,
            sample_date TEXT,
            order_nr TEXT,
            source TEXT DEFAULT 'ldt'
        );
        CREATE INDEX IF NOT EXISTS idx_labs_patient ON lab_results(patient_id);
        CREATE INDEX IF NOT EXISTS idx_labs_code ON lab_results(test_code);
    """)


def upsert_lab_result(conn: sqlite3.Connection, result: LabResult) -> int:
    """Insert all lab values from a LabResult. Returns count inserted."""
    count = 0
    for v in result.values:
        conn.execute(
            """INSERT INTO lab_results
               (patient_id, test_code, test_name, value, unit, ref_low, ref_high, flag, sample_date, order_nr)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result.patient_id, v.test_code, v.test_name, v.value,
             v.unit, v.ref_low, v.ref_high, v.flag, result.sample_date, result.order_nr),
        )
        count += 1
    conn.commit()
    return count


def get_lab_values(
    conn: sqlite3.Connection,
    patient_id: str,
    test_code: str | None = None,
) -> list[dict[str, Any]]:
    """Get lab values for a patient, optionally filtered by test code."""
    if test_code:
        rows = conn.execute(
            "SELECT test_code, test_name, value, unit, ref_low, ref_high, flag, sample_date "
            "FROM lab_results WHERE patient_id = ? AND test_code LIKE ? ORDER BY sample_date DESC",
            (patient_id, f"%{test_code}%"),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT test_code, test_name, value, unit, ref_low, ref_high, flag, sample_date "
            "FROM lab_results WHERE patient_id = ? ORDER BY sample_date DESC",
            (patient_id,),
        ).fetchall()
    return [
        {"test_code": r[0], "test_name": r[1], "value": r[2], "unit": r[3],
         "ref_low": r[4], "ref_high": r[5], "flag": r[6], "sample_date": r[7]}
        for r in rows
    ]


def get_abnormal_labs(
    conn: sqlite3.Connection,
    patient_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get all abnormal (H or L flagged) lab values, optionally filtered by patient."""
    if patient_id:
        rows = conn.execute(
            "SELECT l.patient_id, p.first_name, p.last_name, "
            "l.test_code, l.test_name, l.value, l.unit, l.ref_low, l.ref_high, l.flag, l.sample_date "
            "FROM lab_results l LEFT JOIN patients p ON l.patient_id = p.id "
            "WHERE l.flag IN ('H', 'L') AND l.patient_id = ? ORDER BY l.sample_date DESC",
            (patient_id,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT l.patient_id, p.first_name, p.last_name, "
            "l.test_code, l.test_name, l.value, l.unit, l.ref_low, l.ref_high, l.flag, l.sample_date "
            "FROM lab_results l LEFT JOIN patients p ON l.patient_id = p.id "
            "WHERE l.flag IN ('H', 'L') ORDER BY l.patient_id, l.sample_date DESC",
        ).fetchall()
    return [
        {"patient_id": r[0], "patient_name": f"{r[1]} {r[2]}" if r[1] else r[0],
         "test_code": r[3], "test_name": r[4], "value": r[5], "unit": r[6],
         "ref_low": r[7], "ref_high": r[8], "flag": r[9], "sample_date": r[10]}
        for r in rows
    ]
