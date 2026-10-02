"""Customers and restaurants (Assumptions C-08, C-09).

Assigns every ride and food order to a customer, and every food order to a
restaurant in its restaurant zone. Popularity and activity are lognormal, so
a minority of restaurants and customers account for most volume.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pulse.generation.city import CITY_DIR, load_city


def load_entity_rules(config_dir: Path | str = CITY_DIR) -> dict:
    with open(Path(config_dir) / "entities.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_restaurants(rules, city, rng) -> pd.DataFrame:
    rows = []
    for zid, z in city["zones"].items():
        for _ in range(rules["restaurants_per_zone"][z["type"]]):
            rows.append({"zone_id": zid,
                         "cuisine": rng.choice(rules["cuisines"]),
                         "popularity": rng.lognormal(0, rules["restaurant_popularity_sigma"])})
    df = pd.DataFrame(rows)
    df.insert(0, "restaurant_id", [f"REST{i:05d}" for i in range(1, len(df) + 1)])
    return df


def build_customers(rules, zone_volume: pd.Series, rng) -> pd.DataFrame:
    share = zone_volume / zone_volume.sum()
    counts = np.maximum(1, np.round(share * rules["customers_total"]).astype(int))
    zones = np.repeat(counts.index.to_numpy(), counts.to_numpy())
    df = pd.DataFrame({"home_zone_id": zones,
                       "activity": rng.lognormal(0, rules["customer_activity_sigma"], len(zones))})
    df.insert(0, "customer_id", [f"C{i:06d}" for i in range(1, len(df) + 1)])
    return df


def _pick_by_zone(zone_of_event: pd.Series, pool: pd.DataFrame, zone_col: str,
                  id_col: str, weight_col: str, rng) -> np.ndarray:
    """For each event, pick an entity from the same zone, weighted."""
    out = np.empty(len(zone_of_event), dtype=object)
    for zid, idx in zone_of_event.groupby(zone_of_event).groups.items():
        cands = pool[pool[zone_col] == zid]
        p = cands[weight_col].to_numpy() / cands[weight_col].sum()
        out[zone_of_event.index.get_indexer(idx)] = rng.choice(cands[id_col].to_numpy(), size=len(idx), p=p)
    return out


def assign_entities(rides: pd.DataFrame, orders: pd.DataFrame,
                    config_dir: Path | str = CITY_DIR, seed: int | None = None):
    """Return (rides, orders, customers, restaurants) with ids attached."""
    rules = load_entity_rules(config_dir)
    city = load_city(config_dir)
    rng = np.random.default_rng(rules["seed"] if seed is None else seed)

    restaurants = build_restaurants(rules, city, rng)
    volume = (rides["zone_id"].value_counts().add(orders["zone_id"].value_counts(), fill_value=0)
              .reindex(list(city["zones"]), fill_value=0) + 1)
    customers = build_customers(rules, volume, rng)

    rides = rides.drop(columns=["customer_id"], errors="ignore").reset_index(drop=True)
    orders = orders.drop(columns=["customer_id", "restaurant_id"], errors="ignore").reset_index(drop=True)
    rides["customer_id"] = _pick_by_zone(rides["zone_id"], customers, "home_zone_id",
                                         "customer_id", "activity", rng)
    orders["customer_id"] = _pick_by_zone(orders["zone_id"], customers, "home_zone_id",
                                          "customer_id", "activity", rng)
    orders["restaurant_id"] = _pick_by_zone(orders["restaurant_zone_id"], restaurants, "zone_id",
                                            "restaurant_id", "popularity", rng)
    return rides, orders, customers, restaurants
