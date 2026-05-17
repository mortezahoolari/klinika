# Klinika

**A local-first AI intelligence hub for German physicians.**

Klinika runs Gemma 4 on-premise — no cloud, no SaaS, no patient data leaving the building. It connects to the clinic's existing practice software via BDT/LDT/GDT (the open KBV standards every German PVS exports), and to specialist AI vendors via MCP plugins — turning the doctor's workstation into an intelligence hub where every system talks through one interface.

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
- **Device data** — imports ECG, spirometry, and blood pressure results directly from GDT files
- **MCP plugin support** — specialist AI vendors ship an MCP server (e.g. ECG analysis, spirometry AI); the agent discovers installed plugins on demand via `find_plugin`, keeping vendor schemas out of the context until needed

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
ollama pull gemma4:26b        # or gemma4:e2b for faster/lighter

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

The **Daily Briefing** tab shows the AI-generated morning briefing. The **Chat** tab gives free-form access to the full tool set.

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
5 clinical tools
  ├── get_patient(name)              → full profile: demographics, diagnoses,
  │                                    medications, allergies, encounters, labs
  ├── search_patients(...)           → cross-patient query + abnormal lab flagging
  ├── add_observation(name, note)    → save clinical note
  ├── query_device_results(name)     → ECG, spirometry, BP (GDT)
  └── todays_schedule()              → today's appointments
  + find_plugin(capability)          → discovers MCP vendor plugins; injects their
  │                                    tool schemas into the agent on demand
  + injected plugin tools (e.g. analyze_ecg) — available after find_plugin fires
  + admin tools: import_lab_results, import_device_result, memory
  │ reads/writes
  ▼
SQLite (data/klinika.db)  ←  BDT/LDT/GDT parsers
  │                            (KBV-compliant)
  ▼
Gemma 4 via Ollama
  (local, no network)
```

**Data flow on installation day:**
1. Clinic admin exports full BDT from existing PVS (MEDISTAR, TURBOMED, medatixx, etc.)
2. Klinika ingests the BDT file — patient records, diagnoses, medications, encounters
3. Daily: calendar sync from Doctolib (or PVS export) + LDT lab inbox + GDT device folder
4. Drafts go back to the doctor for copy-paste into the PVS; device results can be written back automatically via GDT SA 6310

---

## Supported Standards

| Standard | Version | Used for |
|----------|---------|---------|
| BDT | 3.0 (KBV) | Patient demographics, diagnoses, medications, encounters |
| LDT | 3.2.19 (KBV) | Lab results from external labs |
| GDT | SA 6302 / SA 6310 | Device results (ECG, spirometry, BP); bidirectional PVS bridge |
| MCP plugins | — | Any additional standard: HL7, FHIR, DICOM, proprietary vendor formats |

BDT, LDT, and GDT are natively implemented — every certified German PVS exports them. For everything else, specialist vendors ship an MCP server that wraps their native protocol. Klinika speaks MCP; the plugin handles the translation. This makes the hub extensible to any device or data source without changes to the core.

---

## Privacy by Architecture

- **No cloud calls** — Gemma 4 runs locally via Ollama.
- **No telemetry** — nothing is sent anywhere.
- **No authentication** — designed for single-physician use on a locked workstation.
- **DSGVO compliance** — patient data stays on the device by construction, not by policy.
- **Synthetic test data** — all sample files in `data/samples/` are generated. No real patients.

---

## Project Structure

```
klinika/
├── agent/          # Ollama function-calling agent loop + MCP client
├── tools/          # Clinical tools, admin tools, plugin discovery
├── services/       # SQLite service layer (patients, labs, devices, drafts)
├── standards/      # BDT, LDT, GDT parsers (KBV-compliant)
├── bridges/        # GDT bidirectional bridge + LDT folder watcher
├── briefings/      # Morning briefing generator
├── drafting/       # Document templates (referral, SOAP, sick note, …)
├── voice/          # faster-whisper offline transcription
└── web/            # FastAPI server + SSE streaming + chat UI

scripts/
├── setup_demo.py           # One-command demo setup (seeds DB + briefing)
└── setup_wizard.py         # Guided Day 1 install (BDT, LDT folder, GDT bridge)

plugins/
└── ecg_server.py           # Example MCP vendor plugin (fastmcp, stdio)

data/samples/               # Synthetic patient data (safe to share)
tests/                      # 173 tests across all stages
```

---

## Configuration

Copy `.env.example` to `.env` and adjust:

```env
OLLAMA_HOST=http://localhost:11434
KLINIKA_DB_PATH=./data/klinika.db
KLINIKA_CHAT_MODEL=gemma4:e2b      # or gemma4:e4b / gemma4:26b
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
