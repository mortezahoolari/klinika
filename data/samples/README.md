# Klinika Sample Data

Test/seed data for Klinika development. All files are either synthetic (generated) or official KBV test corpora — **no real patient data**.

---

## BDT (Stage 3 — PVS bootstrap + incremental)

| File | Source | Purpose |
|------|--------|---------|
| `sample_clinic_bootstrap.bdt` | Generated via `scripts/generate_sample_bdt.py` | **Full bootstrap** — 5 fictional German patients with complete history (diagnoses, meds, allergies, encounters). Simulates PVS full BDT export on installation day |
| `sample_clinic_incremental.bdt` | Generated via `scripts/generate_sample_bdt.py` | **Weekly delta** — 1 new patient (Wagner) + 2 new encounters for existing patients (Schmidt, Müller). Simulates weekly incremental sync |
| `BDT-Datensatzbeschreibung_3-0.pdf` | [QMS Qualitätsring Medizinische Software](https://wiki.meditex-software.com/images/BDT-Datensatzbeschreibung_3-0.pdf) (2013) | Official BDT 3.0 specification, 106 pages — Satzart definitions + field IDs |
| `BDT-spec.txt` | `pdftotext -layout` extraction of above | Text version for grep/reference |

**Sample patients (IDs 00042–00046 in bootstrap):**
- 00042 Karl Schmidt (m, 1958) — Diabetes T2, Hypertonie, Hypercholesterinämie
- 00043 Ursula Müller (f, 1962) — Diabetes T2, Hypertonie, Adipositas
- 00044 Dieter Weber (m, 1955) — COPD, KHK
- 00045 Monika Fischer (f, 1978) — Allergische Rhinitis, Gastritis
- 00046 Hans Becker (m, 1948) — Herzinsuffizienz NYHA IV, CKD, Vorhofflimmern
- 00047 Sabine Wagner (f, 1985) — added via incremental sync

---

## Doctolib calendar (Stage 3b — daily calendar sync)

| File | Source | Purpose |
|------|--------|---------|
| `sample_doctolib_calendar.json` | Generated via `scripts/generate_sample_doctolib.py` | Today's 6 appointments — 5 linked to BDT patients (00042-00046) + 1 walk-in |

Enables full flow test: BDT bootstrap populates parallel record → calendar sync adds today's schedule → briefing references both.

---

## LDT (Stage 5 — lab results)

| File | Source | Purpose |
|------|--------|---------|
| `sample_lab_results.ldt` | Generated via `scripts/generate_sample_ldt.py` | **Simplified xDT-format** lab Befunde for our 5 BDT patients (28 lab values, 14 abnormal). For MVP integration testing. |

**Test values per patient (linked to their BDT diagnoses):**
- Schmidt: HbA1c 8.1 ↑, Glucose 142 ↑, LDL 138 ↑ (diabetes + hyperlipidemia worsening)
- Müller: HbA1c 7.5 ↑ (diabetes, slight improvement)
- Weber: CRP 18.5 ↑, Leukozyten 11.2 ↑ (COPD exacerbation)
- Fischer: Gesamt-IgE 285 ↑ (allergies)
- Becker: Kreatinin 1.9 ↑, eGFR 38 ↓, NT-proBNP 3250 ↑, Hb 11.8 ↓ (CKD + heart failure + anemia)

### Official KBV LDT 3.2.19 corpus

`ldt/` folder — official KBV LDT 3.2.19 test corpus from [update.kbv.de](https://update.kbv.de/ita-update/Labor/Labordatenkommunikation/).

Use these for **full LDT 3.2.19 protocol compliance testing**. They use the complex object-oriented format (Obj_XXXX nested wrappers) and contain embedded PDFs.

| File | Purpose |
|------|---------|
| `LDT-3.2.19-Gesamtdokument.pdf` | Official complete LDT 3.2.19 specification (187 pages) |
| `LDT-3.2.19-UseCases.pdf` | Official LDT 3.2.19 use case documentation (66 pages) |
| `ldt_lab_order.ldt` | Generated lab order (KBV LDT 3.2.19 format) |
| `Z01_UseCase01_Auftrag_UseCase1_FA_LG.ldt` | Lab order — specialist → laboratory community (FA → LG) |
| `Z01_UseCase05_Befund_mitPDF.ldt` | Lab result with embedded PDF report |
| `Z01_UseCase06_Befund_mitPDF.ldt` | Lab result with embedded PDF report (variant) |
| `Z01_UseCase09_Befund_mitPDF_ohneUnterschrift.ldt` | Lab result with PDF, no signature |
| `Z01_UseCase12_Storno_Auftrag.ldt` | Cancelled lab order |
| `Z01_UseCase13_Auftrag323_323.ldt` | Lab order (Satzart 323) |
| `Z01_UseCase14_Befund_Obj_0073_mit_PDF.ldt` | Lab result with object 0073 + PDF |
| `Z01_UseCase15_Befund_mit_PDF.ldt` | Lab result with PDF |
| `Z01_UseCase17_Muster39.ldt` | Muster 39 form-based lab request |

---

## GDT (Stage 6 — device results)

`gdt/` folder — sample SA 6310 device exam results linked to BDT patients. Generated via `scripts/generate_sample_gdt.py`.

| File | Device | Patient | Measurements |
|------|--------|---------|--------------|
| `gdt_6310_ekg1_00042.gdt` | ECG (EKG1) | Karl Schmidt | HR 78, PQ 168ms, QRS 92ms, QTc 425ms, Sinusrhythmus. LVH signs. |
| `gdt_6310_spir_00044.gdt` | Spirometer (SPIR) | Dieter Weber | FVC 3.12L, FEV1 1.89L, FEV1/FVC 60.6%, PEF 4.8L/s. GOLD II-III. |
| `gdt_6310_rr01_00046.gdt` | Blood pressure (RR01) | Hans Becker | RR 148/92, HR 88, SpO2 94%. Elevated + edema. |

---

## Format reference — xDT line structure

BDT, LDT, GDT, KVDT all share the same line format:

```
{3-char length}{4-char field ID}{content}\r\n
```

Where `length` = 3 (length chars) + 4 (field ID) + content_length + 2 (CRLF).

**Encoding:** ISO-8859-15.

Example: `017800018Herr Schmidt\r\n` — length 017, field 8001, content "8Herr Schmidt".
