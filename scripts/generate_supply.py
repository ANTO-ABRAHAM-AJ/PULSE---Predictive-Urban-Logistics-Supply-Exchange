"""Stage 5b (part 1): generate the partner fleet and baseline hourly supply.

Needs data/processed/calendar.csv from scripts/generate_demand.py.

Outputs (data/processed/, gitignored):
    partners.csv        one row per partner
    partner_days.csv    partner-days logged in
    supply_hourly.csv   baseline online partners: Date x Hour x Zone x Vehicle

Usage:
    python scripts/generate_supply.py
"""
from pathlib import Path

import pandas as pd

from pulse.generation.supply import generate_supply

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"


def main() -> None:
    cal_path = OUT / "calendar.csv"
    if not cal_path.exists():
        raise SystemExit("calendar.csv not found - run scripts/generate_demand.py first")
    calendar = pd.read_csv(cal_path, parse_dates=["date"])

    partners, partner_days, supply = generate_supply(calendar)
    partners.to_csv(OUT / "partners.csv", index=False)
    partner_days.to_csv(OUT / "partner_days.csv", index=False)
    supply.to_csv(OUT / "supply_hourly.csv", index=False)

    mix = partners["vehicle_type"].value_counts()
    print(f"Partners: {len(partners):,}  "
          f"(two-wheeler {mix.get('two_wheeler', 0):,}, four-wheeler {mix.get('four_wheeler', 0):,})")
    print(f"Partner-days logged in: {len(partner_days):,} "
          f"(~{len(partner_days) / len(calendar):,.0f} per day)")
    print(f"Online partner-hours: {supply['online_partners'].sum():,}")
    print(f"Files written to {OUT}")


if __name__ == "__main__":
    main()
