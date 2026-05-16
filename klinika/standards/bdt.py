"""
BDT (Behandlungsdatenträger) parser — extracts structured patient data from BDT files.

Uses the shared xDT parser for line-level parsing, then maps BDT-specific
Satzarten (record types) and Feldkennungen (field IDs) to typed dataclasses.

Reference: BDT 3.0 Datensatzbeschreibung (data/samples/BDT-Datensatzbeschreibung_3-0.pdf)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from klinika.standards.xdt import (
    get_field,
    get_fields,
    get_satzart,
    parse_records,
    read_xdt_file,
)

# BDT Satzarten (record types)
SA_FILE_HEADER = "0020"
SA_PRACTICE = "0010"
SA_PATIENT = "6100"
SA_TREATMENT = "6200"
SA_FILE_END = "0021"

# BDT Feldkennungen (field IDs)
FK_PATIENT_ID = "3000"
FK_LAST_NAME = "3101"
FK_FIRST_NAME = "3102"
FK_DOB = "3103"
FK_SEX = "3110"
FK_STREET = "3107"
FK_ZIP = "3112"
FK_CITY = "3113"
FK_PHONE = "3626"
FK_INSURANCE = "3622"
FK_INSURANCE_NR = "3119"
FK_VKNR = "4104"
FK_STATUS = "3108"
FK_ALLERGY = "3484"

FK_TREATMENT_DATE = "6200"
FK_DOCTOR_ID = "9801"
FK_FINDING = "6220"
FK_ICD_CODE = "6001"
FK_DIAGNOSIS_TEXT = "6205"
FK_MEDICATION = "6330"
FK_DOSAGE = "6332"


@dataclass
class Patient:
    id: str
    last_name: str
    first_name: str
    dob: str = ""
    sex: str = ""
    street: str = ""
    zip_code: str = ""
    city: str = ""
    phone: str = ""
    insurance: str = ""
    insurance_nr: str = ""
    allergies: list[str] = field(default_factory=list)


@dataclass
class Encounter:
    patient_id: str
    date: str
    doctor_id: str = ""
    note: str = ""


@dataclass
class Diagnosis:
    patient_id: str
    icd_code: str
    text: str = ""


@dataclass
class Medication:
    patient_id: str
    name: str
    dosage: str = ""


@dataclass
class BDTData:
    patients: list[Patient] = field(default_factory=list)
    encounters: list[Encounter] = field(default_factory=list)
    diagnoses: list[Diagnosis] = field(default_factory=list)
    medications: list[Medication] = field(default_factory=list)


def _parse_patient_record(record: list[tuple[str, str]]) -> Patient:
    """Extract a Patient from a SA 6100 record."""
    return Patient(
        id=get_field(record, FK_PATIENT_ID) or "",
        last_name=get_field(record, FK_LAST_NAME) or "",
        first_name=get_field(record, FK_FIRST_NAME) or "",
        dob=get_field(record, FK_DOB) or "",
        sex=get_field(record, FK_SEX) or "",
        street=get_field(record, FK_STREET) or "",
        zip_code=get_field(record, FK_ZIP) or "",
        city=get_field(record, FK_CITY) or "",
        phone=get_field(record, FK_PHONE) or "",
        insurance=get_field(record, FK_INSURANCE) or "",
        insurance_nr=get_field(record, FK_INSURANCE_NR) or "",
        allergies=get_fields(record, FK_ALLERGY),
    )


def _parse_treatment_record(record: list[tuple[str, str]]) -> tuple[
    list[Encounter], list[Diagnosis], list[Medication]
]:
    """Extract encounters, diagnoses, and medications from a SA 6200 record.

    A single SA 6200 record can contain any combination of:
    - A dated encounter (FK 6200 + FK 6220)
    - A diagnosis (FK 6001 + FK 6205)
    - A medication (FK 6330 + FK 6332)
    """
    patient_id = get_field(record, FK_PATIENT_ID) or ""
    encounters = []
    diagnoses = []
    medications = []

    # Encounter (if has a date + finding)
    date = get_field(record, FK_TREATMENT_DATE)
    finding = get_field(record, FK_FINDING)
    if date and finding:
        encounters.append(Encounter(
            patient_id=patient_id,
            date=date,
            doctor_id=get_field(record, FK_DOCTOR_ID) or "",
            note=finding,
        ))

    # Diagnosis (if has ICD code)
    icd = get_field(record, FK_ICD_CODE)
    if icd:
        diagnoses.append(Diagnosis(
            patient_id=patient_id,
            icd_code=icd,
            text=get_field(record, FK_DIAGNOSIS_TEXT) or "",
        ))

    # Medication (if has medication name)
    med = get_field(record, FK_MEDICATION)
    if med:
        medications.append(Medication(
            patient_id=patient_id,
            name=med,
            dosage=get_field(record, FK_DOSAGE) or "",
        ))

    return encounters, diagnoses, medications


def parse_bdt(path: str | Path) -> BDTData:
    """Parse a BDT file into structured data.

    Returns a BDTData with patients, encounters, diagnoses, and medications.
    """
    content = read_xdt_file(path)
    records = parse_records(content)
    data = BDTData()

    for record in records:
        satzart = get_satzart(record)

        if satzart == SA_PATIENT:
            data.patients.append(_parse_patient_record(record))

        elif satzart == SA_TREATMENT:
            encs, diags, meds = _parse_treatment_record(record)
            data.encounters.extend(encs)
            data.diagnoses.extend(diags)
            data.medications.extend(meds)

    return data
