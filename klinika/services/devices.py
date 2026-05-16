"""Device results database — stores GDT exam results from medical devices."""

from __future__ import annotations

import sqlite3
from typing import Any

from klinika.standards.gdt import DeviceResult


def init_device_db(conn: sqlite3.Connection) -> None:
    """Create the device_results table if it doesn't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS device_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id TEXT REFERENCES patients(id),
            device_id TEXT,
            exam_id TEXT,
            exam_date TEXT,
            exam_time TEXT,
            test_id TEXT,
            test_name TEXT,
            value TEXT,
            unit TEXT,
            ref_low TEXT,
            ref_high TEXT,
            finding TEXT,
            comment TEXT,
            source TEXT DEFAULT 'gdt'
        );
        CREATE INDEX IF NOT EXISTS idx_device_patient ON device_results(patient_id);
        CREATE INDEX IF NOT EXISTS idx_device_exam ON device_results(device_id, exam_date);
    """)


def upsert_device_result(conn: sqlite3.Connection, result: DeviceResult) -> int:
    """Insert all measurements from a DeviceResult. Returns count inserted."""
    count = 0
    for m in result.measurements:
        conn.execute(
            """INSERT INTO device_results
               (patient_id, device_id, exam_id, exam_date, exam_time,
                test_id, test_name, value, unit, ref_low, ref_high, finding, comment)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (result.patient_id, result.device_id, result.exam_id,
             result.exam_date, result.exam_time,
             m.test_id, m.test_name, m.value, m.unit, m.ref_low, m.ref_high,
             result.finding, result.comment),
        )
        count += 1
    conn.commit()
    return count


def get_device_results(
    conn: sqlite3.Connection,
    patient_id: str,
    device_id: str | None = None,
) -> list[dict[str, Any]]:
    """Get device results for a patient, optionally filtered by device."""
    if device_id:
        rows = conn.execute(
            "SELECT device_id, exam_id, exam_date, exam_time, test_id, test_name, "
            "value, unit, ref_low, ref_high, finding, comment "
            "FROM device_results WHERE patient_id = ? AND device_id = ? "
            "ORDER BY exam_date DESC, exam_time DESC",
            (patient_id, device_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT device_id, exam_id, exam_date, exam_time, test_id, test_name, "
            "value, unit, ref_low, ref_high, finding, comment "
            "FROM device_results WHERE patient_id = ? "
            "ORDER BY exam_date DESC, exam_time DESC",
            (patient_id,),
        ).fetchall()
    return [
        {"device_id": r[0], "exam_id": r[1], "exam_date": r[2], "exam_time": r[3],
         "test_id": r[4], "test_name": r[5], "value": r[6], "unit": r[7],
         "ref_low": r[8], "ref_high": r[9], "finding": r[10], "comment": r[11]}
        for r in rows
    ]


def list_recent_results(conn: sqlite3.Connection, limit: int = 20) -> list[dict[str, Any]]:
    """List recent device results across all patients."""
    rows = conn.execute(
        "SELECT DISTINCT d.patient_id, p.first_name, p.last_name, "
        "d.device_id, d.exam_id, d.exam_date, d.finding "
        "FROM device_results d LEFT JOIN patients p ON d.patient_id = p.id "
        "GROUP BY d.patient_id, d.device_id, d.exam_date "
        "ORDER BY d.exam_date DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [
        {"patient_id": r[0], "patient_name": f"{r[1]} {r[2]}" if r[1] else r[0],
         "device_id": r[3], "exam_id": r[4], "exam_date": r[5], "finding": r[6]}
        for r in rows
    ]
