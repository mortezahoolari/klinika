"""
Stage 4 — Agent with hybrid retrieval: precise SQL lookups + fuzzy recall.

Combines all tools from Stages 0-4. The agent picks the right retrieval
tool based on the query: exact lookup for "Schmidt's medications",
fuzzy recall for "what do I know about Müller?".

Usage:
    .venv\\Scripts\\python -m klinika.stage4_records
"""

from klinika.agent.core import Agent
from klinika.memory.store import init_db
from klinika.services.patients import init_patient_db
from klinika.tools.clock import TOOLS as CLOCK_TOOLS
from klinika.tools.memory import TOOLS as MEMORY_TOOLS, set_connection as set_memory_conn
from klinika.tools.bdt import TOOLS as BDT_TOOLS, set_connection as set_bdt_conn
from klinika.tools.calendar import TOOLS as CALENDAR_TOOLS, set_connection as set_cal_conn
from klinika.tools.patients import TOOLS as PATIENT_TOOLS, set_connection as set_patient_conn

SYSTEM_PROMPT = (
    "Du bist Klinika, ein medizinischer KI-Assistent für eine deutsche Hausarztpraxis. "
    "Antworte präzise und auf Deutsch.\n\n"
    "Du hast Zugriff auf folgende Tools:\n\n"
    "**Datenimport:**\n"
    "- bootstrap / read_incremental: BDT-Daten aus dem PVS importieren\n"
    "- sync_doctolib: Tageskalender aus Doctolib synchronisieren\n\n"
    "**Patientenabfragen (präzise SQL-Suche):**\n"
    "- get_patient(id): Vollständige Stammdaten eines Patienten\n"
    "- find_patient(name): Patient nach Name suchen\n"
    "- get_medications(id): Medikamente eines Patienten\n"
    "- get_diagnoses(id): Diagnosen (ICD-10) eines Patienten\n"
    "- get_allergies(id): Allergien eines Patienten\n"
    "- get_encounters(id): Letzte Begegnungen/Behandlungen\n"
    "- search_patients(diagnosis?, medication?): Patienten nach Diagnose oder Medikament finden\n"
    "- current_patient: Aktueller Patient basierend auf Terminplan\n"
    "- add_observation(id, note): Klinische Notiz speichern\n\n"
    "**Kalender & Zeit:**\n"
    "- todays_schedule: Heutiger Terminplan\n"
    "- get_current_time / get_current_date\n\n"
    "**Gedächtnis (semantische Suche):**\n"
    "- remember / recall: Für allgemeine Fakten und Präferenzen\n\n"
    "Nutze die präzisen Patiententools (get_patient, find_patient, get_medications etc.) "
    "für konkrete klinische Abfragen. Nutze recall() nur für allgemeine/unscharfe Erinnerungen."
)


def main() -> None:
    conn = init_db()
    init_patient_db(conn)
    set_memory_conn(conn)
    set_bdt_conn(conn)
    set_cal_conn(conn)
    set_patient_conn(conn)

    all_tools = (
        list(CLOCK_TOOLS) + list(MEMORY_TOOLS) + list(BDT_TOOLS)
        + list(CALENDAR_TOOLS) + list(PATIENT_TOOLS)
    )
    agent = Agent(system_prompt=SYSTEM_PROMPT, tools=all_tools)

    print("Klinika Stage 4 — Agent mit Patientenabfragen")
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
