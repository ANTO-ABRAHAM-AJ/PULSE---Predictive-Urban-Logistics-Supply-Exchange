"""Policy replay simulator with common random numbers (Phase 10, Assumption X-01).

Replays a set of days through the Stage 5b dispatch rules, with an optional
POLICY that may move idle partners at the start of every hour.

Fair comparison: every request's random attributes — arrival minute, ride
destination, restaurant, preparation time, restaurant rejection, customer
cancellation draw, order value, intra-zone distance — are drawn ONCE in
`prepare_days` and shared by every policy. Two policies therefore face
exactly the same riders and orders; only positioning and dispatch differ.

Dispatch rules are those of `pulse.generation.events` (nearest free eligible
partner, 20-minute wait limit, just-in-time food dispatch). A repositioning
move makes the partner unavailable while travelling and costs INR per km.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from pulse.generation.city import CITY_DIR, load_city, speed_kmh
from pulse.generation.events import _build_context, _cc, _logistic, load_ops_rules
from pulse.generation.supply import load_supply_rules


@dataclass
class PreparedDays:
    ctx: dict
    days: list                         # list of (date, is_weekend, logged_in bool[n], requests DataFrame)


@dataclass
class PolicyRun:
    jobs: pd.DataFrame                 # one row per request with its outcome
    moves: pd.DataFrame                # one row per repositioning move
    plans: list = field(default_factory=list)   # optimizer flows per hour (policy-specific)
    duals: list = field(default_factory=list)   # supply shadow prices per hour


def prepare_days(demand: pd.DataFrame, calendar: pd.DataFrame, partners: pd.DataFrame,
                 partner_days: pd.DataFrame, dates, config_dir=CITY_DIR, seed: int = 2026) -> PreparedDays:
    """Draw every request and its random attributes once, for the given dates."""
    city, ops = load_city(config_dir), load_ops_rules(config_dir)
    ctx = _build_context(city, ops, load_supply_rules(config_dir), partners)
    pid_index = {p: i for i, p in enumerate(partners["partner_id"])}
    logged_by_date = partner_days.groupby("date")["partner_id"].apply(list).to_dict()
    lo, hi = ops["dispatch"]["intra_zone_km"]
    zidx = ctx["zidx"]
    weekend = dict(zip(calendar["date"], calendar["is_weekend"]))

    days = []
    for k, date in enumerate(dates):
        rng = np.random.default_rng([seed, k])
        logged = np.zeros(len(partners), dtype=bool)
        logged[[pid_index[p] for p in logged_by_date.get(date, [])]] = True
        d = demand[(demand["date"] == date) & (demand["demand"] > 0)]
        reqs = d.loc[d.index.repeat(d["demand"]), ["hour", "zone_id", "service"]].reset_index(drop=True)
        reqs["minute"] = reqs["hour"] * 60 + rng.uniform(0, 60, len(reqs))
        reqs = reqs.sort_values("minute", kind="stable").reset_index(drop=True)
        z = reqs["zone_id"].map(zidx).to_numpy()
        n = len(reqs)
        dest, rest, prep = np.empty(n, int), np.empty(n, int), np.zeros(n)
        for i, (zz, h, s) in enumerate(zip(z, reqs["hour"], reqs["service"])):
            if s == "mobility":
                dest[i], rest[i] = ctx["dest_choice"](zz, h, rng), zz
            else:
                dest[i], rest[i] = zz, ctx["restaurant_choice"](zz, rng)
                a, b = ops["prep_time_min"]["peak" if h in ops["food_peak_hours"] else "offpeak"]
                prep[i] = rng.uniform(a, b)
        ov = ops["food"]["order_value_lognormal"]
        reqs = reqs.assign(z=z, dest=dest, rest=rest, prep=prep,
                           intra_km=rng.uniform(lo, hi, n),
                           reject=rng.random(n) < ops["restaurant_reject_prob"],
                           u_cancel=rng.random(n),
                           order_value=rng.lognormal(np.log(ov["median"]), ov["sigma"], n))
        days.append((date, bool(weekend[date]), logged, reqs))
    return PreparedDays(ctx=ctx, days=days)


def simulate_policy(prep: PreparedDays, policy=None) -> PolicyRun:
    """Replay the prepared days. `policy(day_info, hour, state) -> list of moves`,
    each move a tuple (partner_index, to_zone_index)."""
    ctx = prep.ctx
    ops, km, city = ctx["ops"], ctx["km"], ctx["city"]
    d, e = ops["dispatch"], ops["economics"]
    tw, online = ctx["is_two_wheeler"], ctx["online_by_hour"]
    cost_km = getattr(policy, "cost_per_km_by_type", {True: 0.0, False: 0.0})
    n = len(tw)
    carry = np.zeros(n)
    job_rows, move_rows = [], []

    for date, is_weekend, logged, reqs in prep.days:
        state = {"loc": ctx["home_idx"].copy(), "free_at": carry.copy(), "logged": logged,
                 "online": online, "tw": tw}
        next_hour = 0
        for r in reqs.itertuples(index=False):
            t, hour = r.minute, r.hour
            while next_hour <= hour:
                if policy is not None:
                    _apply_moves(policy((date, is_weekend), next_hour, state, ctx), state,
                                 next_hour, is_weekend, ctx, cost_km, date, move_rows)
                next_hour += 1
            speed = speed_kmh(city, hour, is_weekend)
            avail = online[hour] & logged
            food = r.service == "food"
            if food:
                avail = avail & tw
            pickup_zone = r.rest if food else r.z
            trip_km = (km[r.rest, r.z] if r.rest != r.z else r.intra_km) if food else \
                      (km[r.z, r.dest] if r.dest != r.z else r.intra_km)
            ready = t + r.prep
            limit_from = ready if food else t
            if food and r.reject:
                job_rows.append((date, hour, r.z, r.service, "cancelled_restaurant", 0.0, -1))
                continue
            loc, free_at = state["loc"], state["free_at"]
            pk = np.where(loc == pickup_zone, (d["intra_zone_km"][0] + d["intra_zone_km"][1]) / 2,
                          km[loc, pickup_zone])
            cand = avail & (pk <= d["max_pickup_km"])
            travel = pk / speed * 60.0
            start = np.maximum(free_at, t)
            if food:
                start = np.maximum(start, ready - travel)
            arrive = np.where(cand, start + travel, np.inf)
            best = int(np.argmin(arrive))
            if not np.isfinite(arrive[best]) or arrive[best] - limit_from > d["max_wait_min"][r.service]:
                job_rows.append((date, hour, r.z, r.service, "cancelled_no_partner", 0.0, -1))
                continue
            if not food:
                wait = arrive[best] - t
                if r.u_cancel < _logistic(wait, **_cc(ops, "mobility")):
                    job_rows.append((date, hour, r.z, r.service, "cancelled_customer", 0.0, best))
                    continue
                vehicle = "two_wheeler" if tw[best] else "four_wheeler"
                f = e["fare"][vehicle]
                fare = f["base"] + f["per_km"] * trip_km
                revenue = fare * (1 - e["ride_payout_share"])
                free_at[best] = arrive[best] + trip_km / speed * 60.0
                loc[best] = r.dest
            else:
                delivered = max(arrive[best], ready) + trip_km / speed * 60.0
                if r.u_cancel < _logistic(delivered - t, **_cc(ops, "food")):
                    job_rows.append((date, hour, r.z, r.service, "cancelled_customer", 0.0, best))
                    continue
                payout = e["food_payout"]["base"] + e["food_payout"]["per_km"] * (pk[best] + trip_km)
                revenue = r.order_value * e["food_commission"] + e["delivery_fee"] - payout
                free_at[best] = delivered
                loc[best] = r.z
            job_rows.append((date, hour, r.z, r.service, "completed", revenue, best))
        while next_hour < 24:
            if policy is not None:
                _apply_moves(policy((date, is_weekend), next_hour, state, ctx), state,
                             next_hour, is_weekend, ctx, cost_km, date, move_rows)
            next_hour += 1
        carry = np.maximum(state["free_at"] - 1440.0, 0.0)

    zone_ids = np.array(ctx["zone_ids"])
    jobs = pd.DataFrame(job_rows, columns=["date", "hour", "zone_idx", "service", "status", "revenue",
                                           "partner_idx"])
    jobs["zone_id"] = zone_ids[jobs.pop("zone_idx").to_numpy()]
    moves = pd.DataFrame(move_rows, columns=["date", "hour", "partner_idx", "from_idx", "to_idx", "km",
                                             "minutes", "cost"])
    if len(moves):
        moves["from_zone"] = zone_ids[moves["from_idx"].to_numpy()]
        moves["to_zone"] = zone_ids[moves["to_idx"].to_numpy()]
        moves["partner_id"] = ctx["partner_ids"][moves["partner_idx"].to_numpy()]
    return PolicyRun(jobs=jobs, moves=moves,
                     plans=getattr(policy, "plans", []), duals=getattr(policy, "duals", []))


def _apply_moves(moves, state, hour, is_weekend, ctx, cost_km, date, out):
    km, speed = ctx["km"], speed_kmh(ctx["city"], hour, is_weekend)
    t0 = hour * 60.0
    for p, to in moves:
        frm = state["loc"][p]
        if to == frm:
            continue
        dist = km[frm, to]
        minutes = dist / speed * 60.0
        state["free_at"][p] = max(state["free_at"][p], t0) + minutes
        state["loc"][p] = to
        out.append((date, hour, p, frm, to, dist, minutes, dist * cost_km[bool(state["tw"][p])]))


def summarize(run: PolicyRun) -> dict:
    j = run.jobs
    cost = float(run.moves["cost"].sum()) if len(run.moves) else 0.0
    out = {"requests": len(j), "completed": int((j.status == "completed").sum()),
           "lost_no_partner": int((j.status == "cancelled_no_partner").sum()),
           "revenue": float(j.revenue.sum()), "reposition_cost": cost, "moves": len(run.moves)}
    out["contribution"] = out["revenue"] - cost
    for s in ("mobility", "food"):
        g = j[j.service == s]
        out[f"{s}_completion"] = float((g.status == "completed").mean())
    return out
