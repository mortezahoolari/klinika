"""
GDT (Geraetedatentransfer) parser — handles GDT SA 6302 (request from PVS) and
SA 6310 (exam results) files, plus a writer for SA 6310 result files.

Uses the shared xDT parser for line-level parsing. GDT field IDs for
measurements (8410/8411/8420/8421/8461/8462) are identical to LDT.

Reference: KBV GDT SA 6302/SA 6310 specification
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from klinika.standards.xdt import (
    get_field,
    get_satzart,
    parse_records,
    read_xdt_file,
)

# GDT Satzarten
SA_EXAM_REQUEST = "6302"   # PVS → device: new examination request (patient opened)
SA_EXAM_RESULTS = "6310"   # device → PVS: examination results

# GDT field IDs — patient identity (used in both 6302 and 6310)
FK_SURNAME = "3101"
FK_FIRSTNAME = "3102"
FK_DOB = "3103"       # DDMMYYYY

# GDT field IDs — device/session identity
FK_SENDER_ID = "8315"
FK_RECEIVER_ID = "8316"
FK_RECORD_LEN = "8100"
FK_PATIENT_ID = "3000"
FK_EXAM_ID = "8402"
FK_EXAM_DATE = "6200"
FK_EXAM_TIME = "6201"

# GDT field IDs — measurements
FK_TEST_ID = "8410"
FK_TEST_NAME = "8411"
FK_TEST_VALUE = "8420"
FK_TEST_UNIT = "8421"
FK_TEST_REF_LOW = "8461"
FK_TEST_REF_HIGH = "8462"
FK_TEST_STATUS = "8480"
FK_FINDING = "6220"
FK_COMMENT = "6226"


@dataclass
class GDTRequest:
    """Patient open trigger received from PVS via SA 6302."""
    surname: str
    firstname: str
    dob: str        # DDMMYYYY as received from PVS
    sender_id: str  # 8-char PVS GDT-ID (field 8315)
    receiver_id: str  # 8-char Klinika GDT-ID (field 8316)


@dataclass
class DeviceMeasurement:
    test_id: str
    test_name: str
    value: str
    unit: str = ""
    ref_low: str = ""
    ref_high: str = ""


@dataclass
class DeviceResult:
    patient_id: str
    device_id: str
    exam_id: str
    exam_date: str = ""
    exam_time: str = ""
    measurements: list[DeviceMeasurement] = field(default_factory=list)
    finding: str = ""
    comment: str = ""


def _parse_6310_record(record: list[tuple[str, str]]) -> DeviceResult:
    """Extract a DeviceResult from a SA 6310 record."""
    patient_id = get_field(record, FK_PATIENT_ID) or ""
    device_id = get_field(record, FK_SENDER_ID) or ""
    exam_id = get_field(record, FK_EXAM_ID) or ""
    exam_date = get_field(record, FK_EXAM_DATE) or ""
    exam_time = get_field(record, FK_EXAM_TIME) or ""
    finding = get_field(record, FK_FINDING) or ""
    comment = get_field(record, FK_COMMENT) or ""

    # Parse measurements: group fields by FK_TEST_ID (8410) boundaries
    measurements: list[DeviceMeasurement] = []
    fields = [(fid, val) for fid, val in record
              if fid not in ("8000", "8100", FK_SENDER_ID, FK_RECEIVER_ID,
                             "9206", "9218", FK_PATIENT_ID, FK_EXAM_ID,
                             FK_EXAM_DATE, FK_EXAM_TIME, FK_FINDING, FK_COMMENT)]

    groups: list[list[tuple[str, str]]] = []
    current: list[tuple[str, str]] = []
    for fid, val in fields:
        if fid == FK_TEST_ID:
            if current:
                groups.append(current)
            current = [(fid, val)]
        else:
            current.append((fid, val))
    if current:
        groups.append(current)

    for group in groups:
        gdict = {fid: val for fid, val in group}
        test_id = gdict.get(FK_TEST_ID, "")
        test_name = gdict.get(FK_TEST_NAME, "")
        value = gdict.get(FK_TEST_VALUE, "") or gdict.get(FK_TEST_STATUS, "")
        unit = gdict.get(FK_TEST_UNIT, "")
        ref_low = gdict.get(FK_TEST_REF_LOW, "")
        ref_high = gdict.get(FK_TEST_REF_HIGH, "")
        if test_id:
            measurements.append(DeviceMeasurement(
                test_id=test_id, test_name=test_name,
                value=value, unit=unit, ref_low=ref_low, ref_high=ref_high,
            ))

    return DeviceResult(
        patient_id=patient_id, device_id=device_id, exam_id=exam_id,
        exam_date=exam_date, exam_time=exam_time,
        measurements=measurements, finding=finding, comment=comment,
    )


def parse_gdt(path: str | Path) -> list[DeviceResult]:
    """Parse a GDT file. Returns list of DeviceResult (one per SA 6310 record)."""
    content = read_xdt_file(path)
    records = parse_records(content)
    results = []
    for record in records:
        if get_satzart(record) == SA_EXAM_RESULTS:
            results.append(_parse_6310_record(record))
    return results


def parse_gdt_request(path: str | Path) -> GDTRequest | None:
    """Parse a SA 6302 request file written by the PVS when a patient is opened.

    Returns GDTRequest if the file is a valid SA 6302, None otherwise.
    """
    content = read_xdt_file(path)
    records = parse_records(content)
    for record in records:
        if get_satzart(record) == SA_EXAM_REQUEST:
            return GDTRequest(
                surname=get_field(record, FK_SURNAME) or "",
                firstname=get_field(record, FK_FIRSTNAME) or "",
                dob=get_field(record, FK_DOB) or "",
                sender_id=get_field(record, FK_SENDER_ID) or "",
                receiver_id=get_field(record, FK_RECEIVER_ID) or "",
            )
    return None


def _make_line(field_id: str, value: str) -> str:
    """Build one GDT line: NNN FFFF content \\r\\n (length = 9 + len(value))."""
    n = 9 + len(value)
    return f"{n:03d}{field_id}{value}\r\n"


def write_gdt_result(
    path: str | Path,
    request: GDTRequest,
    device_id: str,
    content: str,
) -> None:
    """Write a SA 6310 result file that the PVS will auto-import.

    The finding text (content) is placed in field 6220. Patient identity fields
    are mirrored from the original request so the PVS can match the record.
    Sender and receiver IDs are swapped: Klinika is now the sender.
    """
    lines = [
        _make_line("8000", SA_EXAM_RESULTS),
        _make_line("9218", "02.10"),
        _make_line("8315", device_id[:8].ljust(4)),  # Klinika as sender
        _make_line("8316", request.sender_id),        # PVS as receiver
        _make_line("3101", request.surname),
        _make_line("3102", request.firstname),
    ]
    if request.dob:
        lines.append(_make_line("3103", request.dob))
    lines.append(_make_line(FK_FINDING, content))

    raw = "".join(lines).encode("iso-8859-15")
    Path(path).write_bytes(raw)
