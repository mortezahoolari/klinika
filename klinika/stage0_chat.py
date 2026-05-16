"""
Stage 0 — Bare Gemma 4 E4B chat.

Streams responses from the local Ollama model. No tools, no memory.
Tests German clinical terminology and measures tok/s.

Usage:
    .venv/Scripts/python -m klinika.stage0_chat
"""

import time
import sys

import ollama

from klinika.config import CHAT_MODEL, OLLAMA_HOST

SYSTEM_PROMPT = (
    "Du bist Klinika, ein medizinischer KI-Assistent für eine deutsche Hausarztpraxis. "
    "Antworte präzise und auf Deutsch, es sei denn der Nutzer fragt auf einer anderen Sprache. "
    "Du hilfst bei klinischen Fragen, Dokumentation und Patientenmanagement."
)


def chat() -> None:
    """Simple REPL: user types → model streams response → repeat."""
    client = ollama.Client(host=OLLAMA_HOST)
    messages: list[dict] = [{"role": "system", "content": SYSTEM_PROMPT}]

    print(f"Klinika Stage 0 — {CHAT_MODEL} via {OLLAMA_HOST}")
    print("Tippe eine Nachricht und drücke Enter. Ctrl+C zum Beenden.\n")

    while True:
        try:
            user_input = input("Du: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAuf Wiedersehen!")
            break

        if not user_input:
            continue

        messages.append({"role": "user", "content": user_input})

        print("Klinika: ", end="", flush=True)
        t0 = time.perf_counter()
        token_count = 0
        full_response = ""

        stream = client.chat(model=CHAT_MODEL, messages=messages, stream=True)
        for chunk in stream:
            content = chunk.get("message", {}).get("content", "")
            if content:
                print(content, end="", flush=True)
                full_response += content
                token_count += 1

        elapsed = time.perf_counter() - t0
        tok_per_sec = token_count / elapsed if elapsed > 0 else 0
        print(f"\n  [{token_count} tokens, {elapsed:.1f}s, {tok_per_sec:.1f} tok/s]\n")

        messages.append({"role": "assistant", "content": full_response})


if __name__ == "__main__":
    chat()
