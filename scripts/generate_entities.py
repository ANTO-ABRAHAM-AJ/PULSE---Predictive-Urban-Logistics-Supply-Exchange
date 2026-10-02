"""Stage 5c: attach customers and restaurants to every ride and order.

Needs rides.csv and food_orders.csv from generate_events.py. Rewrites both
with customer_id (and restaurant_id for orders), and writes customers.csv and
restaurants.csv.

Usage:
    python scripts/generate_entities.py
"""
from pathlib import Path

import pandas as pd

from pulse.generation.entities import assign_entities

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"


def main() -> None:
    for f in ("rides.csv", "food_orders.csv"):
        if not (P / f).exists():
            raise SystemExit(f"{f} not found - run generate_events.py first")
    rides = pd.read_csv(P / "rides.csv", low_memory=False)
    orders = pd.read_csv(P / "food_orders.csv", low_memory=False)

    rides, orders, customers, restaurants = assign_entities(rides, orders)
    rides.to_csv(P / "rides.csv", index=False)
    orders.to_csv(P / "food_orders.csv", index=False)
    customers.to_csv(P / "customers.csv", index=False)
    restaurants.to_csv(P / "restaurants.csv", index=False)

    print(f"Customers: {len(customers):,}   Restaurants: {len(restaurants):,}")
    print(f"Rides and orders now carry customer_id; orders carry restaurant_id")
    print(f"Files written to {P}")


if __name__ == "__main__":
    main()
