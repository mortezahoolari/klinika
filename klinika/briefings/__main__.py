"""
Generate a morning briefing.

Usage:
    .venv\\Scripts\\python -m klinika.briefings [--date YYYY-MM-DD] [--no-ai]
"""

import argparse
import sys
from datetime import date
from pathlib import Path

from klinika.memory.store import init_db
from klinika.services.patients import init_patient_db
from klinika.services.labs import init_lab_db
from klinika.briefings.generator import generate_briefing


def main():
    parser = argparse.ArgumentParser(description="Generate Klinika morning briefing")
    parser.add_argument("--date", default=date.today().isoformat(),
                        help="Date for briefing (YYYY-MM-DD, default: today)")
    parser.add_argument("--no-ai", action="store_true",
                        help="Skip AI priority analysis (faster, no Gemma call)")
    args = parser.parse_args()

    conn = init_db()
    init_patient_db(conn)
    init_lab_db(conn)

    print(f"Generating briefing for {args.date}...")
    md = generate_briefing(conn, args.date, use_ai=not args.no_ai)

    # Write to file
    out_dir = Path("data/briefings")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_file = out_dir / f"{args.date}.md"
    out_file.write_text(md, encoding="utf-8")

    print(f"Briefing written to {out_file}")
    print(f"\n{md}")

    conn.close()


if __name__ == "__main__":
    main()
