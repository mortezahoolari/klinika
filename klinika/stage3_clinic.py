"""
Stage 3 — Agent with BDT bootstrap + daily calendar sync.

Combines all Stage 0-2 tools + BDT import + Doctolib calendar.
After bootstrap, the agent knows every patient, diagnosis, medication,
and can show today's schedule.

Usage:
    .venv\\Scripts\\python -m klinika.stage3_clinic
"""

from klinika.agent.core import Agent
from klinika.memory.store import init_db
from klinika.services.patients import init_patient_db
from klinika.tools.clock import TOOLS as CLOCK_TOOLS
from klinika.tools.memory import TOOLS as MEMORY_TOOLS, set_connection as set_memory_conn
from klinika.tools.bdt import TOOLS as BDT_TOOLS, set_connection as set_bdt_conn
from klinika.tools.calendar import TOOLS as CALENDAR_TOOLS, set_connection as set_cal_conn

SYSTEM_PROMPT = (
    "Du bist Klinika, ein medizinischer KI-Assistent für eine deutsche Hausarztpraxis. "
    "Antworte präzise und auf Deutsch.\n\n"
    "Du hast Zugriff auf folgende Tools:\n"
    "- get_current_time / get_current_date: Aktuelle Zeit und Datum\n"
    "- remember / recall: Fakten dauerhaft speichern und abrufen\n"
    "- bootstrap: Vollständigen BDT-Export aus dem PVS importieren (einmalig)\n"
    "- read_incremental: Inkrementellen BDT-Export importieren (wöchentlich)\n"
    "- patient_count: Anzahl der Patienten in der Datenbank\n"
    "- sync_doctolib: Tageskalender aus Doctolib-Export synchronisieren\n"
    "- todays_schedule: Heutigen Terminplan anzeigen\n\n"
    "Wenn der Nutzer nach Patientendaten fragt, nutze die entsprechenden Tools. "
    "Wenn BDT-Dateien importiert werden sollen, nutze bootstrap oder read_incremental."
)


def main() -> None:
    conn = init_db()
    init_patient_db(conn)
    set_memory_conn(conn)
    set_bdt_conn(conn)
    set_cal_conn(conn)

    all_tools = list(CLOCK_TOOLS) + list(MEMORY_TOOLS) + list(BDT_TOOLS) + list(CALENDAR_TOOLS)
    agent = Agent(system_prompt=SYSTEM_PROMPT, tools=all_tools)

    print("Klinika Stage 3 — Agent mit BDT-Import + Kalender")
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
