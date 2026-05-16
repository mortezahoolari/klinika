"""
Klinika demo setup — one command from fresh clone to runnable demo.

Initializes the database, ingests all synthetic sample data, and generates
the morning briefing for 2026-04-06 (the demo date with 6 appointments).

Usage:
    python scripts/setup_demo.py
    python scripts/setup_demo.py --date 2026-04-06
    python scripts/setup_demo.py --model gemma4:26b
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _check_ollama() -> tuple[bool, list[str]]:
    try:
        import ollama
        response = ollama.list()
        model_names = [m.model for m in response.models]
        return True, model_names
    except Exception:
        return False, []


def _model_available(models: list[str], model: str) -> bool:
    base = model.split(":")[0]
    return any(m.startswith(base) for m in models)


def main() -> None:
    parser = argparse.ArgumentParser(description="Klinika demo data setup")
    parser.add_argument("--date", default=date.today().isoformat(),
                        help="Demo date for briefing generation (default: today)")
    parser.add_argument("--model", default=None,
                        help="Override chat model (default: from .env or gemma4:e4b)")
    args = parser.parse_args()

    print("=== Klinika Demo Setup ===\n")

    # --- Step 1: Ollama ---
    print("1. Checking Ollama...")
    running, models = _check_ollama()
    if not running:
        print("   WARNING: Ollama is not running or not installed.")
        print("   Data setup will continue, but you need Ollama before running the web UI.")
        print("   Install: https://ollama.com  |  then: ollama serve")
    else:
        print(f"   OK — Ollama running, {len(models)} model(s) available")

    # --- Step 2: Models ---
    print("2. Checking required models...")
    from klinika.config import CHAT_MODEL, EMBED_MODEL
    chat_model = args.model or CHAT_MODEL

    if running:
        missing_models = []
        for model in [chat_model, EMBED_MODEL]:
            if _model_available(models, model):
                print(f"   OK — {model}")
            else:
                print(f"   MISSING — {model}")
                missing_models.append(model)
        if missing_models:
            print("\n   Pull missing models with:")
            for m in missing_models:
                print(f"     ollama pull {m}")
            print("\n   Continuing with data setup (models needed only for inference)...")
    else:
        print(f"   Skipped (Ollama not running) — pull these before starting the UI:")
        print(f"     ollama pull {chat_model}")
        print(f"     ollama pull {EMBED_MODEL}")

    # --- Step 3: Database ---
    print("\n3. Initializing database...")
    from klinika.memory.store import init_db
    from klinika.services.patients import init_patient_db
    from klinika.services.labs import init_lab_db
    from klinika.services.drafts import init_drafts_db
    from klinika.services.devices import init_device_db
    from klinika.skills.store import init_skills_db

    conn = init_db()
    init_patient_db(conn)
    init_lab_db(conn)
    init_drafts_db(conn)
    init_device_db(conn)
    init_skills_db(conn)
    print("   OK — SQLite database ready")

    # Wire tool connections
    from klinika.tools.bdt import set_connection as set_bdt_conn
    from klinika.tools.calendar import set_connection as set_cal_conn
    from klinika.tools.ldt import set_connection as set_ldt_conn
    from klinika.tools.devices import set_connection as set_device_conn

    set_bdt_conn(conn)
    set_cal_conn(conn)
    set_ldt_conn(conn)
    set_device_conn(conn)

    samples = PROJECT_ROOT / "data" / "samples"

    # --- Step 3b: Regenerate calendar for the target date ---
    print(f"\n3b. Generating sample calendar for {args.date}...")
    import sys as _sys
    _sys.path.insert(0, str(PROJECT_ROOT / "scripts"))
    from generate_sample_doctolib import generate_calendar
    import json as _json
    from datetime import date as _date
    cal_data = generate_calendar(_date.fromisoformat(args.date))
    cal_file = samples / "sample_doctolib_calendar.json"
    cal_file.write_text(_json.dumps(cal_data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"   OK — {cal_data['total_count']} appointments written for {args.date}")

    # --- Step 4: BDT bootstrap ---
    print("\n4. Ingesting patient records (BDT bootstrap)...")
    from klinika.tools.bdt import bootstrap, read_incremental
    result = bootstrap(str(samples / "sample_clinic_bootstrap.bdt"))
    print(f"   {result}")

    # --- Step 5: BDT incremental ---
    print("5. Ingesting incremental BDT update...")
    result = read_incremental(str(samples / "sample_clinic_incremental.bdt"))
    print(f"   {result}")

    # --- Step 6: Calendar ---
    print("6. Syncing appointment calendar...")
    from klinika.tools.calendar import sync_doctolib
    result = sync_doctolib(str(samples / "sample_doctolib_calendar.json"))
    print(f"   {result}")

    # --- Step 7: Lab results ---
    print("7. Ingesting lab results (LDT)...")
    from klinika.tools.ldt import import_lab_results
    result = import_lab_results(str(samples / "sample_lab_results.ldt"))
    print(f"   {result}")

    # --- Step 8: Device results ---
    gdt_dir = samples / "gdt"
    if gdt_dir.exists() and list(gdt_dir.glob("*.gdt")):
        print("8. Ingesting device results (GDT)...")
        from klinika.tools.devices import import_device_result
        for gdt_file in sorted(gdt_dir.glob("*.gdt")):
            if "6302" in gdt_file.name:
                continue  # skip PVS request files — only import SA 6310 result files
            result = import_device_result(str(gdt_file))
            first_line = result.splitlines()[0]
            print(f"   {gdt_file.name}: {first_line}")
    else:
        print("8. No GDT device files found in data/samples/gdt/ — skipping")

    # --- Step 9: Morning briefing (no AI — data assembly only) ---
    print(f"\n9. Generating morning briefing for {args.date}...")
    from klinika.briefings.generator import generate_briefing
    briefings_dir = PROJECT_ROOT / "data" / "briefings"
    briefings_dir.mkdir(parents=True, exist_ok=True)
    try:
        md = generate_briefing(conn, args.date, use_ai=False)
        output_path = briefings_dir / f"{args.date}.md"
        output_path.write_text(md, encoding="utf-8")
        line_count = md.count("\n")
        print(f"   OK — {line_count} lines written to data/briefings/{args.date}.md")
        print("   (AI-enhanced briefing with Prioritäten section generates in the web UI)")
    except Exception as exc:
        print(f"   WARNING: Static briefing failed: {exc}")
        print("   (Briefing will generate fully when you open the Tagesbriefing tab)")

    # --- Done ---
    print("\n=== Setup complete ===")
    print()
    print("Start the web UI:")
    print("  uv run python -m klinika.web")
    print()
    print("Then open: http://localhost:9000")
    print()
    print("Demo walkthrough:")
    print(f"  1. Click 'Tagesbriefing' tab — AI briefing for {args.date} (6 appointments)")
    print("  2. Chat: 'Welche Medikamente bekommt Karl Schmidt?'")
    print("  3. Chat: 'Hat er eine Allergie gegen Penicillin?'")
    print("  4. Click the microphone and dictate a German clinical note")
    print("  5. Chat: 'Erstelle eine Überweisung an die Kardiologie für Herrn Becker'")
    print()
    if date.today().isoformat() != args.date:
        print(f"  Note: The sample calendar is loaded for {args.date}.")
        print(f"  The sidebar shows today's date ({date.today().isoformat()}).")
        print(f"  Use the Tagesbriefing tab to see the sample data for {args.date}.")


if __name__ == "__main__":
    main()
