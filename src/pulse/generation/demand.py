"""Hourly demand generator: Zone x Hour x Service (Assumptions D-01 ... D-10).

Produces two tables:
  * truth    - the expected rate the generator used (HIDDEN: for validation only)
  * realized - Poisson counts around that rate (what the business "observes")

Downstream analytics and forecasting must only ever read `realized`.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pulse.generation.city import CITY_DIR, load_city

SERVICES = ("mobility", "food")


def load_demand_rules(config_dir: Path | str = CITY_DIR) -> dict:
    with open(Path(config_dir) / "demand.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def build_calendar(rules: dict, rng: np.random.Generator) -> pd.DataFrame:
    """One row per day: weekday/weekend, rain flag, event flag, train/holdout."""
    cal = rules["calendar"]
    n_days = 7 * (cal["history_weeks"] + cal["holdout_weeks"])
    dates = pd.date_range(cal["start_date"], periods=n_days, freq="D")
    rain_p = rules["rain"]["probability_by_month"]

    df = pd.DataFrame({"date": dates})
    df["day_of_week"] = df["date"].dt.dayofweek               # 0 = Monday
    df["is_weekend"] = df["day_of_week"] >= 5
    df["is_rain"] = [rng.random() < rain_p.get(d.month, rain_p["default"]) for d in dates]

    ev = rules["events"]
    eligible = df.index[df["is_weekend"]] if ev["only_weekends"] else df.index
    event_days = rng.choice(eligible, size=min(ev["count"], len(eligible)), replace=False)
    df["is_event"] = df.index.isin(event_days)

    cutoff = 7 * cal["history_weeks"]
    df["split"] = np.where(df.index < cutoff, "history", "holdout")
    return df


def _hour_multipliers(spec: list | None) -> np.ndarray:
    m = np.ones(24)
    for (start, end), mult in spec or []:
        m[start:end] *= mult
    return m


def expected_rates(rules: dict, city: dict, calendar: pd.DataFrame,
                   rng: np.random.Generator) -> pd.DataFrame:
    """Expected jobs for every Date x Hour x Zone x Service (the hidden truth)."""
    profiles = {(day, s): np.array(rules["hour_profile"][day][s], dtype=float)
                for day in ("weekday", "weekend") for s in SERVICES}
    profiles = {k: v / v.sum() for k, v in profiles.items()}       # share of the day
    mods = rules.get("zone_type_hour_modifiers", {})
    sigma = rules["noise"]["day_lognormal_sigma"]
    scale = rules["city_scale"]
    ev = rules["events"]

    frames = []
    for _, day in calendar.iterrows():
        day_type = "weekend" if day["is_weekend"] else "weekday"
        for zid, z in city["zones"].items():
            ztype = z["type"]
            for s in SERVICES:
                base = rules["daily_base"][ztype][s] * scale
                if day["is_weekend"]:
                    base *= rules["weekend_multiplier"][ztype]
                rate = base * profiles[day_type, s]
                rate = rate * _hour_multipliers(mods.get(ztype, {}).get(day_type, {}).get(s))
                if day["is_rain"]:
                    rate = rate * rules["rain"]["demand_multiplier"][s]
                if day["is_event"] and zid in ev["zones"]:
                    rate = rate * _hour_multipliers(ev["effects"].get(s))
                rate = rate * rng.lognormal(0.0, sigma)                 # hidden day noise
                frames.append(pd.DataFrame({
                    "date": day["date"], "hour": np.arange(24), "zone_id": zid,
                    "service": s, "expected": rate}))
    return pd.concat(frames, ignore_index=True)


def generate_demand(seed: int | None = None, weeks: int | None = None,
                    config_dir: Path | str = CITY_DIR):
    """Return (calendar, truth, realized). `weeks` overrides the horizon (for tests)."""
    rules = load_demand_rules(config_dir)
    city = load_city(config_dir)
    if weeks is not None:
        rules["calendar"]["history_weeks"] = weeks
        rules["calendar"]["holdout_weeks"] = 0
    rng = np.random.default_rng(rules["calendar"]["seed"] if seed is None else seed)

    calendar = build_calendar(rules, rng)
    truth = expected_rates(rules, city, calendar, rng)
    realized = truth[["date", "hour", "zone_id", "service"]].copy()
    realized["demand"] = rng.poisson(truth["expected"].to_numpy())
    return calendar, truth, realized
