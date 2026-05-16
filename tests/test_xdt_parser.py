"""Tests for the shared xDT line parser."""

from klinika.standards.xdt import parse_line, parse_records, get_field, get_fields, get_satzart


def test_parse_line_basic():
    field_id, value = parse_line("0138000 0020")
    assert field_id == "8000"


def test_parse_line_with_content():
    field_id, value = parse_line("0163101Schmidt")
    assert field_id == "3101"
    assert value == "Schmidt"


def test_parse_line_short():
    field_id, value = parse_line("abc")
    assert field_id == ""


def test_parse_records_splits_on_satzart():
    content = "01380006100\r\n0163101Schmidt\r\n01380006200\r\n0176220Befund\r\n"
    records = parse_records(content)
    assert len(records) == 2
    assert get_satzart(records[0]) == "6100"
    assert get_satzart(records[1]) == "6200"


def test_get_field():
    record = [("8000", "6100"), ("3101", "Schmidt"), ("3102", "Karl")]
    assert get_field(record, "3101") == "Schmidt"
    assert get_field(record, "9999") is None


def test_get_fields_multi_value():
    record = [("8000", "6100"), ("3484", "Penicillin"), ("3484", "Amoxicillin")]
    allergies = get_fields(record, "3484")
    assert allergies == ["Penicillin", "Amoxicillin"]
