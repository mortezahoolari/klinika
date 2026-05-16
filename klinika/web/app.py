"""
Klinika Web — FastAPI server with SSE streaming chat.

Serves the HTML chat UI and exposes:
- GET  /           → serves index.html
- POST /chat       → accepts message, returns SSE stream
- GET  /schedule   → today's schedule as JSON
- POST /reset      → resets conversation

Usage:
    .venv\\Scripts\\python -m klinika.web.app
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
from datetime import date
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from klinika.agent.core import Agent
from klinika.config import CHAT_MODEL, GDT_FOLDER, GDT_DEVICE_ID, LDT_FOLDER
from klinika.memory.store import init_db
from klinika.services.patients import init_patient_db, get_todays_appointments
from klinika.services.labs import init_lab_db
from klinika.tools.memory import set_connection as set_memory_conn
from klinika.tools.bdt import TOOLS as BDT_TOOLS, set_connection as set_bdt_conn
from klinika.tools.calendar import TOOLS as CALENDAR_TOOLS, set_connection as set_cal_conn
from klinika.tools.patients import TOOLS as PATIENT_TOOLS, set_connection as set_patient_conn
from klinika.tools.ldt import TOOLS as LDT_TOOLS, set_connection as set_ldt_conn
from klinika.tools.drafts import TOOLS as DRAFT_TOOLS, set_connection as set_draft_conn
from klinika.services.drafts import init_drafts_db
from klinika.tools.devices import TOOLS as DEVICE_TOOLS, set_connection as set_device_conn
from klinika.services.devices import init_device_db
from klinika.tools.skills import TOOLS as SKILL_TOOLS, set_connection as set_skill_conn, set_agent as set_skill_agent
from klinika.skills.store import init_skills_db
from klinika.briefings.generator import generate_briefing
from klinika.bridges.gdt_bridge import GDTBridge
from klinika.bridges.ldt_watcher import LDTWatcher
from klinika.agent.mcp_client import MCPClient
from klinika.tools.plugins import (
    TOOLS as PLUGIN_TOOLS,
    set_mcp_clients,
    register_plugin_tool,
    set_agent as set_plugin_agent,
    eject_plugins,
)

logger = logging.getLogger(__name__)

STATIC_DIR = Path(__file__).parent / "static"

def _build_system_prompt(lang: str, current_patient: str | None = None) -> str:
    today = date.today().strftime("%A, %d %B %Y")
    if lang == "de":
        base = (
            f"Du bist Klinika, ein medizinischer KI-Assistent für eine deutsche Hausarztpraxis. "
            f"Antworte präzise und auf Deutsch. Heutiges Datum: {today}.\n\n"
            "WICHTIGE REGELN:\n"
            "1. Alle Tools akzeptieren Patientennamen direkt — keine ID-Abfrage nötig.\n"
            "2. Für Entwürfe (Überweisung, Arztbrief, Rezept, AU, SOAP): "
            "rufe get_patient(name) auf, dann schreibe den vollständigen Entwurf auf Deutsch "
            "als deine Antwort. Klinische Dokumente sind immer auf Deutsch.\n\n"
            "VERFÜGBARE TOOLS:\n"
            "- get_patient(name): Vollprofil — Diagnosen, Medikamente, Allergien, Begegnungen, Labor\n"
            "- search_patients(diagnosis?, medication?, abnormal_labs?): Patientensuche\n"
            "- add_observation(patient_name, note): Klinische Notiz speichern\n"
            "- query_device_results(patient_name): EKG, Spirometrie, RR-Werte\n"
            "- todays_schedule(): Heutiger Terminplan\n"
            "- find_plugin(capability): MCP-Plugins nach Fachfunktionen durchsuchen"
        )
        if current_patient:
            base += f"\n\nAKTUELLER PATIENT (im PVS geöffnet): {current_patient}"
        return base
    base = (
        f"You are Klinika, a medical AI assistant for a German general practice. "
        f"Respond precisely and in English. Today's date: {today}.\n\n"
        "IMPORTANT RULES:\n"
        "1. All tools accept patient names directly — no ID lookup needed.\n"
        "2. For drafts (referral, letter, prescription, sick note, SOAP): "
        "call get_patient(name) to load patient data, then write the complete German "
        "document as your text response. Clinical documents are always in German.\n\n"
        "AVAILABLE TOOLS:\n"
        "- get_patient(name): Full profile — diagnoses, medications, allergies, encounters, labs\n"
        "- search_patients(diagnosis?, medication?, abnormal_labs?): Cross-patient search\n"
        "- add_observation(patient_name, note): Save a clinical note\n"
        "- query_device_results(patient_name): ECG, spirometry, BP results\n"
        "- todays_schedule(): Today's appointment schedule\n"
        "- find_plugin(capability): Search installed MCP plugins for specialist tools"
    )
    if current_patient:
        base += f"\n\nCURRENT PATIENT (open in PVS): {current_patient}"
    return base


def _get_lang(request: Request) -> str:
    return request.headers.get("Accept-Language", "en")[:2]


# Tools available to the agent in normal operation
def _core_tools() -> list:
    from klinika.tools.patients import TOOLS as PT
    from klinika.tools.calendar import TOOLS as CT
    from klinika.tools.devices import TOOLS as DVT

    # Patient: get_patient, search_patients, add_observation
    # (excludes: current_patient — redundant with todays_schedule + date in prompt)
    patient_core = [t for t in PT if t["function"]["name"] != "current_patient"]

    # Calendar: todays_schedule  (excludes: sync_doctolib — admin op)
    cal_core = [t for t in CT if t["function"]["name"] != "sync_doctolib"]

    # Devices: query_device_results  (excludes: import_device_result, list_device_results)
    device_core = [t for t in DVT if t["function"]["name"] == "query_device_results"]

    return patient_core + cal_core + device_core + PLUGIN_TOOLS


# Admin tools: data import, skills, memory — available only with --admin flag
def _admin_tools() -> list:
    from klinika.tools.bdt import TOOLS as BDT
    from klinika.tools.ldt import TOOLS as LT
    from klinika.tools.calendar import TOOLS as CT
    from klinika.tools.devices import TOOLS as DVT
    from klinika.tools.skills import TOOLS as SKT
    from klinika.tools.memory import TOOLS as MT
    from klinika.tools.clock import TOOLS as CLK

    import_tools = (
        list(BDT)
        + [t for t in LT if t["function"]["name"] == "import_lab_results"]
        + [t for t in CT if t["function"]["name"] == "sync_doctolib"]
        + [t for t in DVT if t["function"]["name"] != "query_device_results"]
    )
    other_admin = list(SKT) + list(MT) + list(CLK)
    return import_tools + other_admin


class ChatMessage(BaseModel):
    message: str


# --- App setup ---

app = FastAPI(title="Klinika", version="0.1.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

# Global state
_conn = None
_agent = None
_admin_mode = False
_gdt_bridge: GDTBridge | None = None
_ldt_watcher: LDTWatcher | None = None
_mcp_clients: list[MCPClient] = []
_current_lang: str = "en"
_last_gdt_patient: str | None = None


def _init(admin: bool = False):
    """Initialize DB + agent (called once at startup)."""
    global _conn, _agent, _admin_mode, _current_lang, _last_gdt_patient
    _admin_mode = admin
    _current_lang = "en"
    _last_gdt_patient = None
    _conn = init_db()
    init_patient_db(_conn)
    init_lab_db(_conn)
    init_drafts_db(_conn)
    init_device_db(_conn)
    init_skills_db(_conn)
    # Wire all DB connections (admin tools need them even if not loaded into agent)
    set_memory_conn(_conn)
    set_bdt_conn(_conn)
    set_cal_conn(_conn)
    set_patient_conn(_conn)
    set_ldt_conn(_conn)
    set_draft_conn(_conn)
    set_device_conn(_conn)
    set_skill_conn(_conn)

    tools = _core_tools()
    if admin:
        tools = tools + _admin_tools()
        logger.info("Admin mode: %d tools loaded", len(tools))
    else:
        logger.info("Core mode: %d tools loaded", len(tools))

    _agent = Agent(system_prompt=_build_system_prompt("en"), tools=tools)
    set_skill_agent(_agent)
    set_plugin_agent(_agent)  # allow find_plugin to inject MCP schemas on demand

    # Start PVS bridges (only if configured via env vars)
    global _gdt_bridge, _ldt_watcher
    if GDT_FOLDER:
        _gdt_bridge = GDTBridge(Path(GDT_FOLDER), GDT_DEVICE_ID, _conn)
        _gdt_bridge.start()
    if LDT_FOLDER:
        _ldt_watcher = LDTWatcher(Path(LDT_FOLDER), _conn)
        _ldt_watcher.start()

    # Connect MCP plugin servers (Mode 2 — vendor-built specialist AI)
    from klinika.config import MCP_SERVERS
    global _mcp_clients
    if MCP_SERVERS:
        for script in (s.strip() for s in MCP_SERVERS.split(",") if s.strip()):
            try:
                client = MCPClient(script)
                client.connect()
                _mcp_clients.append(client)
                for tool in client.list_tools():
                    name = tool["function"]["name"]
                    callable_fn = tool["callable"]
                    schema = {k: v for k, v in tool.items() if k != "callable"}
                    register_plugin_tool(name, schema, callable_fn)
                    # Schema NOT added to agent at startup — find_plugin injects lazily
            except Exception:
                logger.exception("MCP: failed to connect to '%s'", script)
        set_mcp_clients(_mcp_clients)
        logger.info("MCP: %d server(s) connected", len(_mcp_clients))


@app.on_event("startup")
async def startup():
    # _init() is called by main() with the --admin flag before uvicorn starts.
    # When running via uvicorn directly (e.g. in tests), fall back to core mode.
    if _agent is None:
        _init(admin=False)
    logger.info("Klinika web server started with model %s (%d tools)",
                CHAT_MODEL, len(_agent.tools) if hasattr(_agent, "tools") else 0)


@app.on_event("shutdown")
async def shutdown():
    for client in _mcp_clients:
        client.close()


# --- Streaming helpers ---

async def _run_sync_gen(gen):
    """Bridge any sync generator to an async generator via thread + asyncio.Queue."""
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue()

    def _thread():
        try:
            for item in gen:
                loop.call_soon_threadsafe(queue.put_nowait, item)
        except Exception as e:
            loop.call_soon_threadsafe(queue.put_nowait, {"type": "error", "content": str(e)})
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)

    threading.Thread(target=_thread, daemon=True).start()

    while True:
        item = await queue.get()
        if item is None:
            break
        yield item


async def _stream_agent(agent: Agent, message: str):
    async for event in _run_sync_gen(agent.run_stream(message)):
        yield event


# --- Routes ---

@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the chat UI."""
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(content=html)


@app.post("/chat")
async def chat(msg: ChatMessage):
    """Send a message, receive SSE stream with tool events and final text."""
    global _last_gdt_patient
    if _gdt_bridge is not None:
        gdt_patient = _gdt_bridge.current_patient
        current_name = gdt_patient[1] if gdt_patient else None
        if current_name != _last_gdt_patient:
            _last_gdt_patient = current_name
            # Patient switched in PVS — reset conversation history for fresh context
            _agent.set_system_prompt(_build_system_prompt(_current_lang, current_name))

    async def event_generator():
        try:
            async for event in _stream_agent(_agent, msg.message):
                if event["type"] == "tool":
                    yield {
                        "event": "tool",
                        "data": json.dumps({"name": event["name"], "status": event["status"]}),
                    }
                elif event["type"] == "text":
                    words = event["content"].split(" ")
                    for i, word in enumerate(words):
                        chunk = word + (" " if i < len(words) - 1 else "")
                        yield {"event": "text", "data": json.dumps({"content": chunk})}
                        await asyncio.sleep(0.02)
                    yield {"event": "done", "data": json.dumps({"content": ""})}
                elif event["type"] == "error":
                    yield {"event": "error", "data": json.dumps({"content": event["content"]})}
        except Exception as e:
            logger.exception("Chat error")
            yield {"event": "error", "data": json.dumps({"content": str(e)})}

    return EventSourceResponse(event_generator())


@app.get("/schedule")
async def schedule():
    """Return today's schedule as JSON."""
    today = date.today().isoformat()
    appointments = get_todays_appointments(_conn, today)
    return JSONResponse(content={"date": today, "appointments": appointments})


@app.post("/chat/voice")
async def chat_voice(request: Request):
    """Accept audio blob, transcribe with Whisper, send to agent, return SSE stream."""
    from klinika.voice.transcribe import transcribe_audio

    audio_bytes = await request.body()
    content_type = request.headers.get("content-type", "audio/wav")

    async def event_generator():
        try:
            # 1. Transcribe
            text = await asyncio.to_thread(transcribe_audio, audio_bytes, content_type)
            if not text:
                yield {"event": "error", "data": json.dumps({"content": "Keine Sprache erkannt."})}
                return

            # 2. Send transcription as event
            yield {"event": "transcription", "data": json.dumps({"content": text})}

            # 3. Process with agent (streaming tool events)
            async for event in _stream_agent(_agent, text):
                if event["type"] == "tool":
                    yield {
                        "event": "tool",
                        "data": json.dumps({"name": event["name"], "status": event["status"]}),
                    }
                elif event["type"] == "text":
                    words = event["content"].split(" ")
                    for i, word in enumerate(words):
                        chunk = word + (" " if i < len(words) - 1 else "")
                        yield {"event": "text", "data": json.dumps({"content": chunk})}
                        await asyncio.sleep(0.02)
                    yield {"event": "done", "data": json.dumps({"content": ""})}
                elif event["type"] == "error":
                    yield {"event": "error", "data": json.dumps({"content": event["content"]})}
        except Exception as e:
            logger.exception("Voice chat error")
            yield {"event": "error", "data": json.dumps({"content": str(e)})}

    return EventSourceResponse(event_generator())


@app.post("/transcribe")
async def transcribe(request: Request):
    """Transcribe audio to text without invoking the agent."""
    from klinika.voice.transcribe import transcribe_audio
    audio_bytes = await request.body()
    content_type = request.headers.get("content-type", "audio/webm")
    logger.info("Transcribe request: %d bytes, content-type=%s", len(audio_bytes), content_type)
    text = await asyncio.to_thread(transcribe_audio, audio_bytes, content_type)
    logger.info("Transcribe result: %r", text[:80] if text else "(empty)")
    return JSONResponse(content={"text": text})


@app.post("/reset")
async def reset(request: Request):
    """Reset the agent conversation, switching language if Accept-Language header is set."""
    global _current_lang, _last_gdt_patient
    lang = _get_lang(request)
    _current_lang = lang
    _last_gdt_patient = None
    eject_plugins()
    _agent.set_system_prompt(_build_system_prompt(lang))
    return JSONResponse(content={"status": "ok"})


@app.get("/briefing")
async def briefing(request: Request):
    """Generate today's morning briefing."""
    lang = _get_lang(request)
    today = date.today().isoformat()
    md = await asyncio.to_thread(generate_briefing, _conn, today, use_ai=True, lang=lang)
    return JSONResponse(content={"date": today, "markdown": md})


# --- Bridge routes ---

@app.get("/bridges/status")
async def bridges_status():
    """Return current status of all active PVS bridges."""
    return JSONResponse(content={
        "gdt": _gdt_bridge.status if _gdt_bridge else {"running": False},
        "ldt": _ldt_watcher.status if _ldt_watcher else {"running": False},
    })


class BridgeResultMessage(BaseModel):
    content: str


@app.post("/bridges/gdt/result")
async def gdt_result(msg: BridgeResultMessage):
    """Write a GDT SA 6310 result file for the currently open patient.

    The PVS will auto-import the file as a document in the patient record.
    Returns the written file path, or an error if no patient is currently active.
    """
    if _gdt_bridge is None:
        return JSONResponse(status_code=503, content={"error": "GDT bridge not configured"})
    out = _gdt_bridge.write_result(msg.content)
    if out is None:
        return JSONResponse(status_code=400, content={"error": "No patient currently open in PVS"})
    return JSONResponse(content={"written": str(out)})


# --- Entry point ---

def main():
    import argparse
    import uvicorn
    parser = argparse.ArgumentParser(description="Klinika Web Server")
    parser.add_argument("--admin", action="store_true",
                        help="Load admin tools (import, skills, memory) in addition to core tools")
    args = parser.parse_args()
    _init(admin=args.admin)
    mode = "ADMIN" if args.admin else "core"
    print(f"Klinika Web — {CHAT_MODEL} [{mode}] on http://localhost:9000")
    uvicorn.run(app, host="127.0.0.1", port=9000, log_level="info")


if __name__ == "__main__":
    main()
