"""Stage 5b (part 2): simulate every ride and food order under status-quo dispatch.

Needs outputs of generate_demand.py and generate_supply.py.

Outputs (data/processed/, gitignored):
    rides.csv            one row per ride request
    food_orders.csv      one row per food order
    partner_hourly.csv   per partner per online hour: location, busy minutes, empty km

Usage:
    python scripts/generate_events.py          (about 2-4 minutes)
"""
import time
from pathlib import Path

import pandas as pd

from pulse.generation.events import simulate

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"


def main() -> None:
    for f in ("calendar.csv", "demand_hourly.csv", "partners.csv", "partner_days.csv"):
        if not (P / f).exists():
            raise SystemExit(f"{f} not found - run generate_demand.py and generate_supply.py first")
    calendar = pd.read_csv(P / "calendar.csv", parse_dates=["date"])
    demand = pd.read_csv(P / "demand_hourly.csv", parse_dates=["date"])
    partners = pd.read_csv(P / "partners.csv")
    partner_days = pd.read_csv(P / "partner_days.csv", parse_dates=["date"])

    t0 = time.time()
    rides, orders, hourly = simulate(demand, calendar, partners, partner_days, progress=True)
    rides.to_csv(P / "rides.csv", index=False)
    orders.to_csv(P / "food_orders.csv", index=False)
    hourly.to_csv(P / "partner_hourly.csv", index=False)

    rc = (rides["status"] == "completed").mean()
    fc = (orders["status"] == "delivered").mean()
    util = hourly["busy_min"].sum() / hourly["online_min"].sum()
    print(f"\nSimulated {len(calendar)} days in {time.time() - t0:,.0f} s")
    print(f"  rides:  {len(rides):,}  completion {rc:.1%}")
    print(f"  orders: {len(orders):,}  delivered {fc:.1%}")
    print(f"  partner-hours: {len(hourly):,}  utilization {util:.1%}")
    print(f"  files written to {P}")


if __name__ == "__main__":
    main()
