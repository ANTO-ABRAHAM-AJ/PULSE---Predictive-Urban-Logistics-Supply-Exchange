"""Partner fleet and baseline supply (Assumptions S-01 ... S-05).

Produces:
  * partners       - one row per partner: vehicle, home zone, shift, eligibility
  * partner_days   - one row per partner per day they logged in
  * supply_hourly  - BASELINE online partners per Date x Hour x Home zone x Vehicle,
                     i.e. where supply is before any repositioning. This is the
                     "expected baseline supply" Phase 9 forecasts and Phase 10 moves.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pulse.generation.city import CITY_DIR, load_city
from pulse.generation.demand import load_demand_rules


def load_supply_rules(config_dir: Path | str = CITY_DIR) -> dict:
    with open(Path(config_dir) / "supply.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_partners(rules: dict, city: dict, city_scale: float,
                   rng: np.random.Generator) -> pd.DataFrame:
    fleet = rules["fleet"]
    n = int(round(fleet["partners_at_scale_1"] * city_scale))

    vtypes = list(fleet["vehicle_mix"])
    vehicle = rng.choice(vtypes, size=n, p=[fleet["vehicle_mix"][v] for v in vtypes])

    zone_ids = list(city["zones"])
    w = np.array([rules["home_zone_weight"][city["zones"][z]["type"]] for z in zone_ids])
    home = rng.choice(zone_ids, size=n, p=w / w.sum())

    shift_names = list(rules["shifts"])
    shares = np.array([rules["shifts"][s]["share"] for s in shift_names])
    shift = rng.choice(shift_names, size=n, p=shares / shares.sum())

    return pd.DataFrame({
        "partner_id": [f"P{i:05d}" for i in range(1, n + 1)],
        "vehicle_type": vehicle,
        "home_zone": home,
        "shift_type": shift,
        "eligible_services": ["|".join(fleet["eligibility"][v]) for v in vehicle],
    })


def shift_hours(rules: dict) -> dict[str, list[int]]:
    """Hours of the day each shift is online."""
    return {name: sorted({h for a, b in s["windows"] for h in range(a, b)})
            for name, s in rules["shifts"].items()}


def build_partner_days(rules: dict, partners: pd.DataFrame, calendar: pd.DataFrame,
                       rain_two_wheeler_mult: float,
                       rng: np.random.Generator) -> pd.DataFrame:
    """Daily log-in draws. Only logged-in partner-days are kept."""
    p = rules["login_probability"]
    is_tw = (partners["vehicle_type"] == "two_wheeler").to_numpy()
    rows = []
    for _, day in calendar.iterrows():
        prob = np.full(len(partners), p["weekend"] if day["is_weekend"] else p["weekday"])
        if day["is_rain"]:
            prob[is_tw] *= rain_two_wheeler_mult
        logged = rng.random(len(partners)) < prob
        rows.append(pd.DataFrame({"date": day["date"],
                                  "partner_id": partners["partner_id"].to_numpy()[logged]}))
    return pd.concat(rows, ignore_index=True)


def build_supply_hourly(rules: dict, partners: pd.DataFrame,
                        partner_days: pd.DataFrame) -> pd.DataFrame:
    """Baseline online partners by Date x Hour x Home zone x Vehicle."""
    hours = shift_hours(rules)
    pd_ = partner_days.merge(partners[["partner_id", "vehicle_type", "home_zone", "shift_type"]],
                             on="partner_id")
    counts = (pd_.groupby(["date", "home_zone", "vehicle_type", "shift_type"])
                 .size().rename("n").reset_index())
    expanded = [counts.assign(hour=h)[lambda df, s=s: df["shift_type"] == s]
                for s, hs in hours.items() for h in hs]
    hourly = (pd.concat(expanded, ignore_index=True)
                .groupby(["date", "hour", "home_zone", "vehicle_type"])["n"].sum()
                .rename("online_partners").reset_index()
                .rename(columns={"home_zone": "zone_id"}))
    return hourly.sort_values(["date", "hour", "zone_id", "vehicle_type"], ignore_index=True)


def generate_supply(calendar: pd.DataFrame, seed: int | None = None,
                    config_dir: Path | str = CITY_DIR):
    """Return (partners, partner_days, supply_hourly) for an existing calendar."""
    rules = load_supply_rules(config_dir)
    demand_rules = load_demand_rules(config_dir)
    city = load_city(config_dir)
    rng = np.random.default_rng(rules["fleet"]["seed"] if seed is None else seed)

    partners = build_partners(rules, city, demand_rules["city_scale"], rng)
    partner_days = build_partner_days(
        rules, partners, calendar,
        demand_rules["rain"]["two_wheeler_supply_multiplier"], rng)
    supply_hourly = build_supply_hourly(rules, partners, partner_days)
    return partners, partner_days, supply_hourly
