"""Phase 11: incentive programmes and stress scenarios on the replay simulator.

Incentive mechanism (Assumption E-07)
    The platform secures extra two-wheeler partners in a target zone for a
    time window by paying a guaranteed bonus per partner-hour. They start in
    the target zone, are online only in the window, are dispatched like any
    partner, and are paid the bonus whether or not they get jobs. What it
    costs to attract them is uncertain, so programmes are tested at several
    bonus levels.

Targeting (no holdout data)
    A zone-hour is targeted when the average shadow price of one more
    two-wheeler there — from the profit policy run on VALIDATION weeks —
    exceeds the bonus. The number of partners covers the jobs still lost in
    that zone-hour (2 jobs per partner-hour), capped.

Stress scenarios
    Demand and supply of the replayed days are transformed before replay:
    every day rainy, a festival evening surge, a partner shortage, a demand
    surge. Integer demand is scaled by binomial thinning (factor < 1) or by
    adding Poisson extra jobs (factor > 1), with a fixed seed.
"""
from __future__ import annotations

import copy

import numpy as np
import pandas as pd

from pulse.optimization.simulation import PreparedDays

JOBS_PER_PARTNER_HOUR = 2.0


# ---------------------------------------------------------------- targeting
def choose_targets(duals: pd.DataFrame, lost: pd.DataFrame, bonus: float, weekdays: int,
                   max_partners: int = 6) -> pd.DataFrame:
    """duals: zone_id, hour, partner_type, dual (validation weekdays, positive values only).
    lost: zone_id, hour, lost (jobs lost per weekday under the profit policy).
    Returns zone_id, hour, value (avg INR per two-wheeler-hour), partners."""
    tw = duals[duals["partner_type"] == "two_wheeler"]
    value = (tw.groupby(["zone_id", "hour"])["dual"].sum() / weekdays).rename("value").reset_index()
    t = value[value["value"] >= bonus].merge(lost, on=["zone_id", "hour"], how="left").fillna({"lost": 0.0})
    t["partners"] = np.clip(np.ceil(t["lost"] / JOBS_PER_PARTNER_HOUR), 1, max_partners).astype(int)
    return t.sort_values(["zone_id", "hour"]).reset_index(drop=True)


def windows(targets: pd.DataFrame) -> list[dict]:
    """Group targeted hours of a zone into contiguous windows; each window
    is staffed by its largest hourly partner count."""
    out = []
    for zone, g in targets.groupby("zone_id"):
        hours = g["hour"].tolist()
        counts = dict(zip(g["hour"], g["partners"]))
        start = prev = hours[0]
        for h in hours[1:] + [None]:
            if h is not None and h == prev + 1:
                prev = h
                continue
            span = list(range(start, prev + 1))
            out.append({"zone_id": zone, "hours": span, "partners": max(counts[x] for x in span)})
            if h is not None:
                start = prev = h
    return out


# ------------------------------------------------------- adding the partners
def add_incentive_partners(prep: PreparedDays, programme: list[dict], weekdays_only: bool = True) -> PreparedDays:
    """Return a copy of `prep` with the programme's extra partners added."""
    ctx = dict(prep.ctx)
    n_extra = sum(w["partners"] for w in programme)
    if n_extra == 0:
        return prep
    zidx = ctx["zidx"]
    online = np.zeros((24, n_extra), dtype=bool)
    home = np.empty(n_extra, dtype=int)
    ids = []
    k = 0
    for w in programme:
        for i in range(w["partners"]):
            online[w["hours"], k] = True
            home[k] = zidx[w["zone_id"]]
            ids.append(f"INC-{w['zone_id']}-{w['hours'][0]:02d}-{i + 1}")
            k += 1
    ctx["online_by_hour"] = np.hstack([ctx["online_by_hour"], online])
    ctx["home_idx"] = np.concatenate([ctx["home_idx"], home])
    ctx["is_two_wheeler"] = np.concatenate([ctx["is_two_wheeler"], np.ones(n_extra, dtype=bool)])
    ctx["partner_ids"] = np.concatenate([np.asarray(ctx["partner_ids"], dtype=object), np.array(ids, dtype=object)])
    days = [(date, wk, np.concatenate([logged, np.full(n_extra, not (weekdays_only and wk))]), reqs)
            for date, wk, logged, reqs in prep.days]
    return PreparedDays(ctx=ctx, days=days)


def programme_cost(programme: list[dict], bonus: float, days: int) -> float:
    return bonus * days * sum(w["partners"] * len(w["hours"]) for w in programme)


def partner_hours_per_day(programme: list[dict]) -> int:
    return sum(w["partners"] * len(w["hours"]) for w in programme)


# ------------------------------------------------------------ stress tests
def scale_counts(counts: np.ndarray, factor: np.ndarray, rng) -> np.ndarray:
    counts = np.asarray(counts, dtype=int)
    factor = np.asarray(factor, dtype=float)
    out = counts.copy()
    down = factor < 1
    out[down] = rng.binomial(counts[down], factor[down])
    up = factor > 1
    out[up] = counts[up] + rng.poisson(counts[up] * (factor[up] - 1))
    return out


def stress(demand: pd.DataFrame, partner_days: pd.DataFrame, partners: pd.DataFrame,
           calendar: pd.DataFrame, scenario: str, rules: dict, seed: int = 11):
    """Return transformed (demand, partner_days) for a named stress scenario."""
    rng = np.random.default_rng(seed)
    d, pdays = demand.copy(), partner_days.copy()
    s = rules[scenario]
    if s["type"] == "rain":
        dry = set(calendar.loc[~calendar["is_rain"].astype(bool), "date"])
        f = np.where(d["date"].isin(dry), d["service"].map(s["demand_multiplier"]).astype(float), 1.0)
        d["demand"] = scale_counts(d["demand"], f, rng)
        tw = set(partners.loc[partners["vehicle_type"] == "two_wheeler", "partner_id"])
        drop = pdays["date"].isin(dry) & pdays["partner_id"].isin(tw) & \
            (rng.random(len(pdays)) > s["two_wheeler_supply_multiplier"])
        pdays = pdays[~drop]
    elif s["type"] == "demand":
        hours = s.get("hours", list(range(24)))
        f = np.where(d["hour"].isin(hours), s["multiplier"], 1.0)
        d["demand"] = scale_counts(d["demand"], f, rng)
    elif s["type"] == "supply":
        pdays = pdays[rng.random(len(pdays)) < s["keep_share"]]
    return d, pdays
