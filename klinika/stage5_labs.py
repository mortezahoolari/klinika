"""
Stage 5 — Agent with LDT lab integration.

Extends Stage 4 with lab result import, querying, and abnormal flagging.

Usage:
    .venv\\Scripts\\python -m klinika.stage5_labs
"""

from klinika.agent.core import Agent
from klinika.memory.store import init_db
from klinika.services.patients import init_patient_db
from klinika.services.labs import init_lab_db
from klinika.tools.clock import TOOLS as CLOCK_TOOLS
from klinika.tools.memory import TOOLS as MEMORY_TOOLS, set_connection as set_memory_conn
from klinika.tools.bdt import TOOLS as BDT_TOOLS, set_connection as set_bdt_conn
from klinika.tools.calendar import TOOLS as CALENDAR_TOOLS, set_connection as set_cal_conn
from klinika.tools.patients import TOOLS as PATIENT_TOOLS, set_connection as set_patient_conn
from klinika.tools.ldt import TOOLS as LDT_TOOLS, set_connection as set_ldt_conn

SYSTEM_PROMPT = (
    "Du bist Klinika, ein medizinischer KI-Assistent für eine deutsche Hausarztpraxis. "
    "Antworte präzise und auf Deutsch.\n\n"
    "Du hast Zugriff auf folgende Tools:\n\n"
    "**Datenimport:**\n"
    "- bootstrap / read_incremental: BDT-Daten aus dem PVS importieren\n"
    "- sync_doctolib: Tageskalender aus Doctolib synchronisieren\n"
    "- import_lab_results: Laborergebnisse aus LDT-Datei importieren\n\n"
    "**Patientenabfragen:**\n"
    "- get_patient / find_patient / get_medications / get_diagnoses / get_allergies / get_encounters\n"
    "- search_patients: Patienten nach Diagnose oder Medikament suchen\n"
    "- current_patient / add_observation\n\n"
    "**Laborabfragen:**\n"
    "- query_lab_values(patient_id, test_code?): Laborwerte eines Patienten\n"
    "- flag_abnormals(patient_id?): Alle auffälligen Laborwerte anzeigen\n\n"
    "**Kalender & Sonstiges:**\n"
    "- todays_schedule / get_current_time / get_current_date\n"
    "- remember / recall: Allgemeine Fakten speichern/abrufen\n\n"
    "Nutze import_lab_results um LDT-Dateien zu importieren. "
    "Nutze flag_abnormals um schnell auffällige Werte zu finden. "
    "Nutze query_lab_values für gezielte Laborwert-Abfragen pro Patient."
)


def main() -> None:
    conn = init_db()
    init_patient_db(conn)
    init_lab_db(conn)
    set_memory_conn(conn)
    set_bdt_conn(conn)
    set_cal_conn(conn)
    set_patient_conn(conn)
    set_ldt_conn(conn)

    all_tools = (
        list(CLOCK_TOOLS) + list(MEMORY_TOOLS) + list(BDT_TOOLS)
        + list(CALENDAR_TOOLS) + list(PATIENT_TOOLS) + list(LDT_TOOLS)
    )
    agent = Agent(system_prompt=SYSTEM_PROMPT, tools=all_tools)

    print("Klinika Stage 5 — Agent mit Laborintegration")
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
        # Windows cp1252 console can't handle all Unicode from Gemma
        try:
            print(f"Klinika: {response}\n")
        except UnicodeEncodeError:
            print(f"Klinika: {response.encode('ascii', errors='replace').decode('ascii')}\n")

    conn.close()


if __name__ == "__main__":
    main()
