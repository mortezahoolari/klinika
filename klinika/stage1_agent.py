"""
Stage 1 — Agent with clock tools.

Proves the tool-calling loop works: model calls get_current_time/get_current_date
and incorporates results into its answer.

Usage:
    .venv/Scripts/python -m klinika.stage1_agent
"""

from klinika.agent.core import Agent
from klinika.tools.clock import TOOLS as CLOCK_TOOLS

SYSTEM_PROMPT = (
    "Du bist Klinika, ein medizinischer KI-Assistent für eine deutsche Hausarztpraxis. "
    "Antworte präzise und auf Deutsch. "
    "Du hast Zugriff auf Tools — nutze sie wenn nötig, um aktuelle Informationen zu liefern."
)


def main() -> None:
    agent = Agent(system_prompt=SYSTEM_PROMPT, tools=list(CLOCK_TOOLS))

    print(f"Klinika Stage 1 — Agent mit Tools")
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


if __name__ == "__main__":
    main()
