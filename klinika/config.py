"""Klinika configuration — loads settings from .env file."""

from pathlib import Path

from dotenv import load_dotenv
import os

# Load .env from project root
_project_root = Path(__file__).parent.parent
load_dotenv(_project_root / ".env")

OLLAMA_HOST: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
CHAT_MODEL: str = os.getenv("KLINIKA_CHAT_MODEL", "gemma4:e4b")
EMBED_MODEL: str = os.getenv("KLINIKA_EMBED_MODEL", "nomic-embed-text")
DB_PATH: str = os.getenv("KLINIKA_DB_PATH", str(_project_root / "data" / "klinika.db"))
VOICE_MODE: str = os.getenv("KLINIKA_VOICE_MODE", "whisper")  # whisper, native (experimental), auto
WHISPER_MODEL: str = os.getenv("KLINIKA_WHISPER_MODEL", "base")  # tiny, base, small, medium

# Bridge configuration — empty string disables the bridge
GDT_FOLDER: str = os.getenv("KLINIKA_GDT_FOLDER", "")        # PVS ↔ Klinika exchange folder
GDT_DEVICE_ID: str = os.getenv("KLINIKA_GDT_DEVICE_ID", "KLINIKA")  # 8-char GDT device identifier
LDT_FOLDER: str = os.getenv("KLINIKA_LDT_FOLDER", "")         # labGate drop folder

# MCP plugin servers — comma-separated paths to server scripts (empty = no plugins)
MCP_SERVERS: str = os.getenv("KLINIKA_MCP_SERVERS", "")
