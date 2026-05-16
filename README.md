# Klinika

**A local-first AI thinking layer for German physicians.**

Klinika runs Gemma 4 on-premise — no cloud, no SaaS, no patient data leaving the building. It sits beside whatever practice management software (PVS) the clinic already uses, reads the same file formats (BDT, LDT, GDT) every German PVS exports, and gives the doctor a thinking partner they can actually trust.

> Built for the [Gemma 4 Good Hackathon](https://www.kaggle.com/competitions/gemma-4-good-hackathon) · Health & Sciences track

---

## The Problem

A German GP sees 25 patients a day. For each one, they manually cross-reference lab results, update ICD-10 diagnosis codes, and write referral letters — then copy everything into their practice software. That's 2–3 hours of documentation every day, in a profession that already has a physician shortage.

Cloud-based AI assistants are a non-starter: German healthcare law requires patient data to stay on-premise. DSGVO (GDPR) compliance by policy isn't enough — it needs to be compliance by architecture.

---

## What Klinika Does

- **Morning briefing** — before the first patient arrives, Klinika reads the day's schedule, cross-references lab results, and generates an AI-prioritized patient list with clinical context
- **Natural language queries** — "Which patients are on Metformin and have HbA1c above 8?" answered from the real patient database
- **Document drafting** — referral letters, sick notes, discharge summaries, SOAP notes — in German, using actual patient data from the database
- **Voice input** — dictate directly; Whisper transcribes offline, no audio leaves the device
- **Skill learning** — save any workflow as a named skill: "Erstelle DMP-Dokumentation für Diabetes-Patient" becomes a one-click operation
- **Device data** — imports ECG, spirometry, and blood pressure results directly from GDT files
- **MCP plugin support** — specialist AI vendors ship an MCP server (e.g. ECG analysis, spirometry AI); Klinika connects at startup and the agent discovers installed plugins on demand with `find_plugin`

---

## Hardware Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | RTX 3070 (8 GB VRAM) | RTX 3080 (16 GB VRAM) |
| RAM | 16 GB | 32 GB |
| CPU | Any modern x86-64 | Intel i7-12th gen or better |
| OS | Windows 11 | Windows 11 |
| Storage | 30 GB free | 50 GB free |

**Model options (all benchmarked — 6/6 tool accuracy):**
- `gemma4:e2b` — 2B MoE, ~7 GB VRAM, ~10s warm latency (recommended default)
- `gemma4:e4b` — 4B MoE, ~10 GB VRAM, ~16s warm latency
- `gemma4:26b` — 26B dense, ~17 GB VRAM, ~38s warm latency (best output quality)

---

## Quick Start

```bash
# 1. Install Ollama and pull models
ollama pull gemma4:26b        # or gemma4:e4b for faster/lighter
ollama pull nomic-embed-text

# 2. Clone and install
git clone https://github.com/mortezahoolari/klinika.git
cd klinika
pip install uv
uv sync

# 3. Seed demo data (synthetic patients, one-time)
python scripts/setup_demo.py

# 4. Start the web UI
uv run python -m klinika.web

# 5. Open in browser
start http://localhost:9000
```

The **Tagesbriefing** tab shows the AI-generated morning briefing. The **Chat** tab gives free-form access to the full tool set.

---

## Architecture

```
Doctor
  │ speaks / types
  ▼
Web UI (FastAPI + SSE, :9000)
  │ streams tokens
  ▼
Agent loop (Ollama function-calling)
  │ calls tools
  ▼
6 core tools (action-oriented, name-based)
  ├── get_patient(name)              → full profile: demographics, diagnoses,
  │                                    medications, allergies, encounters, labs
  ├── search_patients(...)           → cross-patient query + abnormal lab flagging
  ├── add_observation(name, note)    → save clinical note
  ├── query_device_results(name)     → ECG, spirometry, BP (GDT)
  ├── todays_schedule()              → today's appointments
  └── find_plugin(capability)        → discover installed MCP vendor plugins
  + MCP plugins (vendor subprocesses, stdio transport — e.g. ecg_server.py)
  + admin tools: import_lab_results, import_device_result, bootstrap, skills, memory
  │ reads/writes
  ▼
SQLite (data/klinika.db)  ←  BDT/LDT/GDT parsers
  │                            (KBV-compliant)
  ▼
Gemma 4 via Ollama        ←  nomic-embed-text (embeddings)
  (local, no network)
```

**Data flow on installation day:**
1. Clinic admin exports full BDT from existing PVS (MEDISTAR, TURBOMED, medatixx, etc.)
2. `bootstrap` tool ingests all patient records, diagnoses, medications, encounters
3. Daily: calendar sync from Doctolib (or PVS export) + LDT lab inbox + GDT device folder
4. Drafts go back to the doctor for copy-paste into the PVS — Klinika never writes back

---

## Supported Standards

| Standard | Version | Used for |
|----------|---------|---------|
| BDT | 3.0 (KBV) | Patient demographics, diagnoses, medications, encounters |
| LDT | 3.2.19 (KBV) | Lab results from external labs |
| GDT | SA 6310 | Device results: ECG, spirometry, blood pressure |
| Doctolib JSON | — | Appointment calendar (via scraper pattern) |

These are the file formats that every certified German practice management system exchanges. Klinika requires no PVS-specific integration — it reads the standard exports.

---

## Privacy by Architecture

- **No cloud calls** — Gemma 4 runs locally via Ollama. Embeddings run locally via nomic-embed-text.
- **No telemetry** — nothing is sent anywhere.
- **No authentication** — designed for single-physician use on a locked workstation.
- **DSGVO compliance** — patient data stays on the device by construction, not by policy.
- **Synthetic test data** — all sample files in `data/samples/` are generated. No real patients.

---

## Project Structure

```
klinika/
├── agent/          # Ollama function-calling agent loop
├── tools/          # 20+ tools (patients, labs, devices, drafts, skills, …)
├── services/       # SQLite service layer (patients, labs, devices, drafts)
├── standards/      # BDT, LDT, GDT parsers (KBV-compliant)
├── briefings/      # Morning briefing generator
├── drafting/       # Document templates (5 types)
├── memory/         # SQLite + nomic-embed-text semantic recall
├── skills/         # Skill persistence and retrieval
├── voice/          # faster-whisper offline transcription
└── web/            # FastAPI server + chat UI (Chat + Tagesbriefing tabs)

scripts/
├── setup_demo.py           # One-command demo setup
├── generate_sample_bdt.py  # Regenerate synthetic BDT data
├── generate_sample_ldt.py  # Regenerate synthetic LDT data
└── generate_sample_doctolib.py

data/samples/               # Synthetic patient data (safe to share)
docs/                       # Architecture docs
tests/                      # 173 tests across all stages
```

---

## Configuration

Copy `.env.example` to `.env` and adjust:

```env
OLLAMA_HOST=http://localhost:11434
KLINIKA_DB_PATH=./data/klinika.db
KLINIKA_CHAT_MODEL=gemma4:e2b      # or gemma4:e4b / gemma4:26b
KLINIKA_EMBED_MODEL=nomic-embed-text
KLINIKA_WHISPER_MODEL=base         # tiny / base / small / medium

# MCP plugin servers — comma-separated paths (Mode 2 vendor plugins)
# KLINIKA_MCP_SERVERS=plugins/ecg_server.py
```

---

## Running Tests

```bash
uv run pytest tests/ -v
```

173 tests covering parsers (BDT/LDT/GDT), services, tools, agent loop, briefing, skills, drafting, MCP client, and plugin discovery.

---

## License

Apache 2.0 — see [LICENSE](LICENSE).
