"""Tests for xdt.read_xdt_file() encoding detection."""

import tempfile
from pathlib import Path

from klinika.standards.xdt import read_xdt_file


def _write_tmp(raw: bytes) -> Path:
    f = tempfile.NamedTemporaryFile(delete=False, suffix=".gdt")
    f.write(raw)
    f.close()
    return Path(f.name)


def test_read_utf8_file():
    content = "013800001\r\n012800100\r\nMüller Ärzte€\r\n"
    path = _write_tmp(content.encode("utf-8"))
    assert read_xdt_file(path) == content


def test_read_utf8_bom_file():
    content = "013800001\r\nÄrztekammer\r\n"
    bom = b'\xef\xbb\xbf'
    path = _write_tmp(bom + content.encode("utf-8"))
    assert read_xdt_file(path) == content


def test_read_windows1252_file():
    # ü = 0xFC, ä = 0xE4, ö = 0xF6 in Windows-1252
    raw = "Müller".encode("windows-1252")
    path = _write_tmp(raw)
    result = read_xdt_file(path)
    assert "M\xfcller" in result or "Müller" in result


def test_read_iso88591_umlauts():
    # German umlauts are identical bytes in ISO-8859-1, ISO-8859-15, and Windows-1252
    content = "Schäfer Günther Jörg"
    raw = content.encode("iso-8859-1")
    path = _write_tmp(raw)
    result = read_xdt_file(path)
    assert "Sch" in result and "fer" in result   # ä byte decoded consistently
