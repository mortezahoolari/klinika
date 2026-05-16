"""
Shared xDT line parser for the KBV xDT family (BDT, GDT, LDT, KVDT).

Line format: {3-char length}{4-char field ID}{content}\r\n
Encoding: ISO-8859-15

Parser for the KBV xDT line format (BDT, GDT, LDT, KVDT).
"""

from __future__ import annotations

from pathlib import Path

# Field ID that marks the start of a new record (Satzidentifikation)
FK_SATZART = "8000"


def parse_line(line: str) -> tuple[str, str]:
    """Parse one xDT line → (field_id, value).

    Line format: NNNFFFFcontent
    - NNN = 3-digit total line length
    - FFFF = 4-digit field identifier
    - content = remaining characters
    """
    if len(line) < 7:
        return ("", "")
    field_id = line[3:7]
    value = line[7:].rstrip("\r\n")
    return field_id, value


def parse_records(content: str) -> list[list[tuple[str, str]]]:
    """Parse raw xDT content into a list of records.

    Each record is a list of (field_id, value) tuples.
    Records are split whenever FK 8000 (Satzart) appears.
    """
    lines = content.replace("\r\n", "\n").strip().split("\n")
    records: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        field_id, value = parse_line(line)
        if not field_id:
            continue

        if field_id == FK_SATZART:
            if current:
                records.append(current)
            current = [(field_id, value)]
        else:
            current.append((field_id, value))

    if current:
        records.append(current)

    return records


def get_field(record: list[tuple[str, str]], field_id: str) -> str | None:
    """Get the first value for a field ID in a record. Returns None if not found."""
    for fid, value in record:
        if fid == field_id:
            return value
    return None


def get_fields(record: list[tuple[str, str]], field_id: str) -> list[str]:
    """Get all values for a field ID in a record (for multi-value fields)."""
    return [value for fid, value in record if fid == field_id]


def get_satzart(record: list[tuple[str, str]]) -> str | None:
    """Get the Satzart (record type) from a record."""
    return get_field(record, FK_SATZART)


def read_xdt_file(path: str | Path) -> str:
    """Read an xDT file, detecting UTF-8 and falling back to Windows-1252."""
    raw = Path(path).read_bytes()
    if raw.startswith(b'\xef\xbb\xbf'):
        return raw[3:].decode('utf-8')
    try:
        return raw.decode('utf-8')
    except UnicodeDecodeError:
        return raw.decode('windows-1252', errors='replace')
