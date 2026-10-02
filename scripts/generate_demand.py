"""Stage 5a: generate Bengaluru zones + hourly demand.

Outputs (data/processed/, gitignored):
    zones.csv              zone id, name, type, lat, lon
    distance_km.csv        zone-to-zone road distance matrix
    calendar.csv           date, weekday/weekend, rain, event, history/holdout
    demand_hourly.csv      REALIZED demand  (what analytics and models may use)
    _truth_demand_hourly.csv   expected rates (hidden; validation only)

Usage:
    python scripts/generate_demand.py
"""
from pathlib import Path

from pulse.generation.city import load_city, road_km_matrix, zones_frame
from pulse.generation.demand import generate_demand

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "processed"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    city = load_city()
    zones_frame(city).to_csv(OUT / "zones.csv", index=False)
    road_km_matrix(city).to_csv(OUT / "distance_km.csv")

    calendar, truth, realized = generate_demand()
    calendar.to_csv(OUT / "calendar.csv", index=False)
    realized.to_csv(OUT / "demand_hourly.csv", index=False)
    truth.to_csv(OUT / "_truth_demand_hourly.csv", index=False)

    days = len(calendar)
    print(f"Generated {days} days x 24 hours x {len(city['zones'])} zones x 2 services")
    print(f"  rows: {len(realized):,}   total jobs: {realized['demand'].sum():,}"
          f"   (~{realized['demand'].sum() / days:,.0f} per day)")
    print(f"  rain days: {calendar['is_rain'].sum()}   event days: {calendar['is_event'].sum()}")
    by = realized.groupby("service")["demand"].sum()
    print(f"  mobility: {by['mobility']:,}   food: {by['food']:,}")
    print(f"  files written to {OUT}")


if __name__ == "__main__":
    main()
