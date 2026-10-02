"""Rebuild the whole synthetic Bengaluru dataset in the correct order.

    1. generate_demand.py   zones, distances, calendar, hourly demand
    2. generate_supply.py   partner fleet and baseline supply
    3. generate_events.py   every ride and food order (takes 1-4 minutes)
    4. generate_entities.py customers and restaurants attached to events

Usage:
    python scripts/build_all.py
"""
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
STEPS = ["generate_demand.py", "generate_supply.py", "generate_events.py",
         "generate_entities.py"]


def main() -> None:
    t0 = time.time()
    for i, script in enumerate(STEPS, 1):
        print(f"\n=== Step {i}/{len(STEPS)}: {script} ===")
        result = subprocess.run([sys.executable, str(SCRIPTS / script)])
        if result.returncode != 0:
            raise SystemExit(f"{script} failed - stopping.")
    print(f"\nAll data rebuilt in {time.time() - t0:,.0f} s")


if __name__ == "__main__":
    main()
