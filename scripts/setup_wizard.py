"""
Klinika Setup Wizard  -  guided Day 1 installation for clinic staff.

Walks the practice admin through:
  1. BDT bootstrap (full patient history import from PVS export)
  2. LDT folder path (labGate drop folder)
  3. GDT bridge folder + device ID (PVS device integration)

Writes the configured paths to .env and runs the initial BDT import.

Usage:
    python scripts/setup_wizard.py          # interactive
    python scripts/setup_wizard.py --dry-run  # print config without writing
"""

import argparse
import re
import sqlite3
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent

# Ensure klinika package is importable
sys.path.insert(0, str(PROJECT_ROOT))


# ------------------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------------------

def _hr(char: str = "-", width: int = 60) -> str:
    return char * width


def _ask(prompt: str, default: str = "") -> str:
    """Prompt the user. Returns stripped input or default on empty."""
    hint = f" [{default}]" if default else " [press Enter to skip]"
    try:
        value = input(f"  {prompt}{hint}: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return value if value else default


def _read_env() -> dict[str, str]:
    """Read existing .env into a dict."""
    env_path = PROJECT_ROOT / ".env"
    result: dict[str, str] = {}
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                result[k.strip()] = v.strip()
    return result


def _write_env(values: dict[str, str], dry_run: bool) -> None:
    """Update or add keys in .env, preserving comments and existing values."""
    env_path = PROJECT_ROOT / ".env"
    existing_lines = env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []

    updated = set()
    new_lines: list[str] = []
    for line in existing_lines:
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.split("=", 1)[0].strip()
            if k in values:
                new_lines.append(f"{k}={values[k]}")
                updated.add(k)
                continue
        new_lines.append(line)

    # Append keys that were not already present
    for k, v in values.items():
        if k not in updated:
            new_lines.append(f"{k}={v}")

    content = "\n".join(new_lines) + "\n"

    if dry_run:
        print("\n[dry-run] Would write to .env:")
        for k, v in values.items():
            print(f"  {k}={v}")
    else:
        env_path.write_text(content, encoding="utf-8")
        print(f"\n  Configuration written to {env_path}")


# ------------------------------------------------------------------------------
# Step 1  -  BDT bootstrap
# ------------------------------------------------------------------------------

def _step_bdt(dry_run: bool) -> None:
    print(f"\n{_hr()}")
    print("Step 1/4  -  BDT Bootstrap (import full patient history from PVS)")
    print(_hr())
    print("  Your PVS can export all patient records as a BDT file (one-time).")
    print("  Common export menu paths:")
    print("    TURBOMED : Datei >Export >BDT-Export  (requires unlock code from CGM hotline)")
    print("    MEDISTAR : Datei >Datenexport >BDT")
    print("    medatixx : Administration >Datensicherung >BDT-Export")
    print("    T2med    : Extras >Datenexport >BDT")
    print()

    bdt_path = _ask("Path to your BDT export file")
    if not bdt_path:
        print("  Skipped  -  you can run bootstrap later: ask the agent 'bootstrap from <path>'")
        return

    p = Path(bdt_path)
    if not p.exists():
        print(f"  File not found: {bdt_path}")
        print("  Skipped  -  check the path and re-run the wizard.")
        return

    if dry_run:
        print(f"  [dry-run] Would import BDT from {bdt_path}")
        return

    print(f"  Importing from {bdt_path} ...")
    try:
        from klinika.standards.bdt import parse_bdt
        from klinika.services.patients import (
            init_patient_db, upsert_patient, upsert_encounter, upsert_diagnosis, upsert_medication
        )
        from klinika.config import DB_PATH

        conn = sqlite3.connect(DB_PATH)
        init_patient_db(conn)
        data = parse_bdt(p)

        for patient in data.patients:
            upsert_patient(conn, patient)
        for e in data.encounters:
            upsert_encounter(conn, e)
        for d in data.diagnoses:
            upsert_diagnosis(conn, d)
        for m in data.medications:
            upsert_medication(conn, m)
        conn.commit()
        conn.close()

        print(f"  Done  -  {len(data.patients)} patients, "
              f"{len(data.encounters)} encounters, "
              f"{len(data.diagnoses)} diagnoses, "
              f"{len(data.medications)} medications imported.")
    except Exception as e:
        print(f"  Import failed: {e}")


# ------------------------------------------------------------------------------
# Step 2  -  LDT lab folder
# ------------------------------------------------------------------------------

def _step_ldt(dry_run: bool) -> str:
    print(f"\n{_hr()}")
    print("Step 2/4  -  LDT Lab Folder (automatic lab result import)")
    print(_hr())
    print("  Set this to the folder where your lab middleware (labGate) drops .ldt files.")
    print("  This is the same folder your PVS already watches  -  Klinika will watch it too.")
    print("  Common paths:")
    print(r"    labGate default : \\Server\labGate")
    print(r"    MEDISTAR        : \\Medistar\ms$\labGate")
    print(r"    local           : C:\Praxis\Labor")
    print()

    folder = _ask("LDT lab folder path")
    if folder:
        p = Path(folder)
        if not p.exists():
            print(f"  Folder not found: {folder}")
            print("  You can create it or adjust the path later in .env (KLINIKA_LDT_FOLDER).")
    else:
        print("  Skipped  -  set KLINIKA_LDT_FOLDER in .env to enable auto-import later.")

    return folder


# ------------------------------------------------------------------------------
# Step 3  -  GDT bridge folder
# ------------------------------------------------------------------------------

def _step_gdt_folder(dry_run: bool) -> str:
    print(f"\n{_hr()}")
    print("Step 3/4  -  GDT Bridge Folder (live PVS patient context)")
    print(_hr())
    print("  When Klinika is registered as a GDT device in your PVS, the PVS will")
    print("  write a file to this folder whenever a patient is opened. Klinika")
    print("  reads it and knows who is being seen  -  without any manual lookup.")
    print("  After the consultation, Klinika can write results back to the same folder")
    print("  and the PVS will import them automatically.")
    print()
    print("  Register in your PVS:")
    print("    TURBOMED : Patient >F3 >Devices >GDT Interface Settings >New")
    print("    medatixx : Settings >Interfaces >New Device Interface")
    print("    T2med    : Administrator >Device Management >New Device (local folder only)")
    print()

    folder = _ask("GDT exchange folder path")
    if folder:
        p = Path(folder)
        if not p.exists():
            try:
                p.mkdir(parents=True, exist_ok=True)
                print(f"  Created folder: {folder}")
            except Exception as e:
                print(f"  Could not create folder: {e}")
    else:
        print("  Skipped  -  set KLINIKA_GDT_FOLDER in .env to enable bridge later.")

    return folder


# ------------------------------------------------------------------------------
# Step 4  -  GDT device ID
# ------------------------------------------------------------------------------

def _step_gdt_id() -> str:
    print(f"\n{_hr()}")
    print("Step 4/4  -  GDT Device ID")
    print(_hr())
    print("  This 8-character identifier must match exactly what you enter in your")
    print("  PVS device settings when registering Klinika as a GDT device.")
    print()

    device_id = _ask("GDT Device ID", default="KLINIKA")
    device_id = device_id[:8]  # GDT-IDs are max 8 chars
    print(f"  Using device ID: {device_id}")
    return device_id


# ------------------------------------------------------------------------------
# Main
# ------------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Klinika Setup Wizard")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would be done without making changes")
    args = parser.parse_args()

    print(_hr("="))
    print("  Klinika Setup Wizard")
    print("  Guided configuration for Day 1 clinic installation")
    print(_hr("="))

    _step_bdt(args.dry_run)

    ldt_folder = _step_ldt(args.dry_run)
    gdt_folder = _step_gdt_folder(args.dry_run)
    gdt_id = _step_gdt_id()

    # Build config updates
    env_updates: dict[str, str] = {}
    if ldt_folder:
        env_updates["KLINIKA_LDT_FOLDER"] = ldt_folder
    if gdt_folder:
        env_updates["KLINIKA_GDT_FOLDER"] = gdt_folder
        env_updates["KLINIKA_GDT_DEVICE_ID"] = gdt_id

    if env_updates:
        _write_env(env_updates, args.dry_run)
    else:
        print("\n  No bridge paths configured  -  nothing written to .env.")

    print(f"\n{_hr('=')}")
    print("  Setup complete!")
    print("  Start Klinika with:  uv run python -m klinika.web")
    print("  Open in browser:     http://localhost:9000")
    print(_hr("="))


if __name__ == "__main__":
    main()
