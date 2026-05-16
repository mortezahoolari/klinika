"""
Audio transcription — Whisper-based offline speech-to-text.

Uses faster-whisper for local transcription (no data leaves the clinic).
Gemma 4 E4B native audio is experimental (Ollama crash bug #15333).

Install: pip install faster-whisper
"""

from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path

from klinika.config import VOICE_MODE, WHISPER_MODEL

logger = logging.getLogger(__name__)

_whisper_model = None


def _get_whisper_model():
    """Lazy-load the Whisper model."""
    global _whisper_model
    if _whisper_model is None:
        try:
            from faster_whisper import WhisperModel
            logger.info("Loading Whisper model '%s'...", WHISPER_MODEL)
            _whisper_model = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8")
            logger.info("Whisper model loaded.")
        except ImportError:
            raise RuntimeError(
                "faster-whisper nicht installiert. "
                "Installieren mit: pip install faster-whisper"
            )
    return _whisper_model


def transcribe_audio(audio_bytes: bytes, mime_type: str = "audio/wav") -> str:
    """Transcribe audio bytes to text.

    Currently uses Whisper (offline, local). Native Gemma 4 audio
    is experimental and deferred (Ollama bug #15333).
    """
    return _transcribe_whisper(audio_bytes)


def _transcribe_whisper(audio_bytes: bytes) -> str:
    """Transcribe via faster-whisper (offline, local)."""
    # Reject audio that is too short to contain real speech (< 4 KB)
    if len(audio_bytes) < 4096:
        logger.warning("Audio too short (%d bytes) — skipping transcription", len(audio_bytes))
        return ""

    model = _get_whisper_model()

    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(audio_bytes)
        tmp_path = f.name

    try:
        segments, info = model.transcribe(
            tmp_path,
            beam_size=5,
            vad_filter=True,   # filter silence to reduce hallucinations
        )
        text = " ".join(segment.text.strip() for segment in segments)
        logger.warning("Transcribed %d bytes → %d words (lang=%s prob=%.2f): %r",
                       len(audio_bytes), len(text.split()), info.language,
                       info.language_probability, text[:80])
        # Discard hallucinations: < 4 words with low language confidence
        if len(text.split()) < 4 and info.language_probability < 0.7:
            return ""
        return text.strip()
    finally:
        Path(tmp_path).unlink(missing_ok=True)
