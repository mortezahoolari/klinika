"""
Stage 2 — Agent with clock tools + memory (remember/recall).

Proves cross-session persistence: facts stored in one session
can be recalled in a new session.

Usage:
    .venv/Scripts/python -m klinika.stage2_agent
"""

from klinika.agent.core import Agent
from klinika.memory.store import init_db
from klinika.tools.clock import TOOLS as CLOCK_TOOLS
from klinika.tools.memory import TOOLS as MEMORY_TOOLS, set_connection

SYSTEM_PROMPT = (
    "Du bist Klinika, ein medizinischer KI-Assistent für eine deutsche Hausarztpraxis. "
    "Antworte präzise und auf Deutsch.\n\n"
    "Du hast Zugriff auf Tools:\n"
    "- get_current_time / get_current_date: Aktuelle Zeit und Datum\n"
    "- remember: Speichere wichtige Fakten dauerhaft (z.B. Patientenpräferenzen, Allergien)\n"
    "- recall: Suche in gespeicherten Fakten nach relevanten Informationen\n\n"
    "Nutze 'remember' aktiv, wenn der Nutzer dir etwas Wichtiges mitteilt. "
    "Nutze 'recall' wenn nach gespeicherten Informationen gefragt wird."
)


def main() -> None:
    conn = init_db()
    set_connection(conn)

    all_tools = list(CLOCK_TOOLS) + list(MEMORY_TOOLS)
    agent = Agent(system_prompt=SYSTEM_PROMPT, tools=all_tools)

    print("Klinika Stage 2 — Agent mit Gedächtnis")
    print("Tippe eine Nachricht und drücke Enter. Ctrl+C zum Beenden.\n")

    while True:
        try:
            user_input = input("Du: ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\nAuf Wiedersehen!")
            break

        if not user_input:
            continue

        response = agent.run(user_input)
        print(f"Klinika: {response}\n")

    conn.close()


if __name__ == "__main__":
    main()
