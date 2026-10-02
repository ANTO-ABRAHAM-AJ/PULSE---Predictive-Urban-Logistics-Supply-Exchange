"""Event-level marketplace simulation (Assumptions O-01 ... O-04, E-01 ... E-03).

Turns hourly demand counts into individual rides and food orders, and
dispatches each one to a partner using the STATUS-QUO policy:

    nearest free, online, eligible partner - no repositioning.

This is what "history" looks like before PULSE: the warehouse, analytics and
forecasts are built on it, and Phase 10 measures how much better an optimized
allocation would have done.

Simplifications (documented in Assumptions.md):
  * partners start each day in their home zone and end each job where it ends;
    a job running past midnight keeps the partner busy into the next day;
  * a partner holds one job at a time;
  * time is in minutes from midnight; jobs may finish after the shift ends.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pulse.generation.city import CITY_DIR, load_city, road_km_matrix, speed_kmh
from pulse.generation.supply import load_supply_rules, shift_hours


def load_ops_rules(config_dir: Path | str = CITY_DIR) -> dict:
    with open(Path(config_dir) / "operations.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _logistic(x, max_prob, midpoint, scale):
    return max_prob / (1.0 + np.exp(-(x - midpoint) / scale))


class _Day:
    """Partner state for one simulated day."""

    def __init__(self, partners, logged_in, online_by_hour, home_idx):
        self.n = len(partners)
        self.loc = home_idx.copy()                 # zone index
        self.free_at = np.zeros(self.n)            # minute the partner is next free
        self.logged_in = logged_in                 # bool[n]
        self.online_by_hour = online_by_hour       # bool[24, n]


def simulate_day(date, requests, partners, logged_in, ctx, rng, carry_free_at=None):
    """Dispatch one day's requests in time order.

    `carry_free_at` holds minutes past midnight that partners are still busy
    with jobs from the previous day. Returns (rides, orders, snapshots, free_at).
    """
    ops, km, zone_ids, zidx = ctx["ops"], ctx["km"], ctx["zone_ids"], ctx["zidx"]
    is_weekend = ctx["is_weekend"]
    tw = ctx["is_two_wheeler"]
    state = _Day(partners, logged_in, ctx["online_by_hour"], ctx["home_idx"])
    if carry_free_at is not None:
        state.free_at = carry_free_at.copy()
    d = ops["dispatch"]
    lo, hi = d["intra_zone_km"]

    rides, orders, snaps = [], [], []
    next_snapshot_hour = 0

    for r in requests.itertuples(index=False):
        t, hour, z, service = r.minute, r.hour, zidx[r.zone_id], r.service
        while next_snapshot_hour <= hour:          # where online partners are at each hour start
            on = state.online_by_hour[next_snapshot_hour] & state.logged_in
            snaps.append((next_snapshot_hour, np.flatnonzero(on), state.loc[on].copy()))
            next_snapshot_hour += 1

        speed = speed_kmh(ctx["city"], hour, is_weekend)
        avail = state.online_by_hour[hour] & state.logged_in
        if service == "food":
            avail &= tw

        if service == "mobility":
            dest = ctx["dest_choice"](z, hour, rng)
            trip_km = km[z, dest] if dest != z else rng.uniform(lo, hi)
            pickup_zone = z
            limit_from = t
            wait_limit = d["max_wait_min"]["mobility"]
        else:
            rz = ctx["restaurant_choice"](z, rng)
            trip_km = km[rz, z] if rz != z else rng.uniform(lo, hi)
            pickup_zone = rz
            peak = hour in ops["food_peak_hours"]
            a, b = ops["prep_time_min"]["peak" if peak else "offpeak"]
            ready = t + rng.uniform(a, b)
            limit_from = ready
            wait_limit = d["max_wait_min"]["food"]
            if rng.random() < ops["restaurant_reject_prob"]:
                orders.append(_order_row(date, r, rz, "cancelled_restaurant", rng, ctx))
                continue

        pk = km[state.loc, pickup_zone]
        pk = np.where(state.loc == pickup_zone, (lo + hi) / 2, pk)
        cand = avail & (pk <= d["max_pickup_km"])
        travel = pk / speed * 60.0
        start = np.maximum(state.free_at, t)
        if service == "food":
            # Just-in-time assignment: the partner is sent so they reach the
            # restaurant around ready time, not left waiting there.
            start = np.maximum(start, ready - travel)
        arrive = np.where(cand, start + travel, np.inf)
        best = int(np.argmin(arrive))
        late = arrive[best] - limit_from

        if not np.isfinite(arrive[best]) or late > wait_limit:
            row_status = "cancelled_no_partner"
            if service == "mobility":
                rides.append(_ride_row(date, r, dest, trip_km, row_status))
            else:
                orders.append(_order_row(date, r, rz, row_status, rng, ctx, trip_km=trip_km, ready=ready))
            continue

        assigned = float(start[best])
        vehicle = "two_wheeler" if tw[best] else "four_wheeler"
        pid = ctx["partner_ids"][best]

        if service == "mobility":
            wait = arrive[best] - t
            if rng.random() < _logistic(wait, **_cc(ops, "mobility")):
                rides.append(_ride_row(date, r, dest, trip_km, "cancelled_customer",
                                       pid, vehicle, assigned, pk[best], wait))
                continue
            dropoff = arrive[best] + trip_km / speed * 60.0
            state.free_at[best] = dropoff
            state.loc[best] = dest
            rides.append(_ride_row(date, r, dest, trip_km, "completed", pid, vehicle,
                                   assigned, pk[best], wait, arrive[best], dropoff, ctx))
        else:
            picked = max(arrive[best], ready)
            delivered = picked + trip_km / speed * 60.0
            if rng.random() < _logistic(delivered - t, **_cc(ops, "food")):
                orders.append(_order_row(date, r, rz, "cancelled_customer", rng, ctx, pid,
                                         assigned, pk[best], trip_km, ready))
                continue
            state.free_at[best] = delivered
            state.loc[best] = z
            orders.append(_order_row(date, r, rz, "delivered", rng, ctx, pid, assigned,
                                     pk[best], trip_km, ready, picked, delivered))

    while next_snapshot_hour < 24:
        on = state.online_by_hour[next_snapshot_hour] & state.logged_in
        snaps.append((next_snapshot_hour, np.flatnonzero(on), state.loc[on].copy()))
        next_snapshot_hour += 1
    return rides, orders, snaps, np.maximum(state.free_at - 1440.0, 0.0)


def _cc(ops, service):
    c = ops["customer_cancel"][service]
    return {"max_prob": c["max_prob"], "midpoint": c["midpoint_min"], "scale": c["scale_min"]}


def _ride_row(date, r, dest, trip_km, status, pid=None, vehicle=None, assigned=None,
              pickup_km=None, wait=None, pickup=None, dropoff=None, ctx=None):
    fare = payout = None
    if status == "completed":
        f = ctx["ops"]["economics"]["fare"][vehicle]
        fare = round(f["base"] + f["per_km"] * trip_km, 2)
        payout = round(fare * ctx["ops"]["economics"]["ride_payout_share"], 2)
    return {"date": date, "request_min": r.minute, "zone_id": r.zone_id,
            "dest_zone_id": dest if isinstance(dest, str) else None, "dest_idx": dest,
            "trip_km": round(trip_km, 2), "status": status, "partner_id": pid,
            "vehicle_type": vehicle, "assigned_min": assigned,
            "pickup_km": None if pickup_km is None else round(float(pickup_km), 2),
            "pickup_eta_min": None if wait is None else round(float(wait), 2),
            "pickup_min": pickup, "dropoff_min": dropoff, "fare": fare, "partner_payout": payout}


def _order_row(date, r, rz, status, rng, ctx, pid=None, assigned=None, pickup_km=None,
               trip_km=None, ready=None, picked=None, delivered=None):
    ov = ctx["ops"]["food"]["order_value_lognormal"]
    value = round(float(rng.lognormal(np.log(ov["median"]), ov["sigma"])), 2)
    e = ctx["ops"]["economics"]
    commission = fee = payout = None
    if status == "delivered":
        commission = round(value * e["food_commission"], 2)
        fee = e["delivery_fee"]
        payout = round(e["food_payout"]["base"] + e["food_payout"]["per_km"] * (pickup_km + trip_km), 2)
    return {"date": date, "placed_min": r.minute, "zone_id": r.zone_id,
            "restaurant_zone_idx": rz, "order_value": value, "status": status,
            "partner_id": pid, "assigned_min": assigned,
            "pickup_km": None if pickup_km is None else round(float(pickup_km), 2),
            "delivery_km": None if trip_km is None else round(float(trip_km), 2),
            "ready_min": ready, "picked_min": picked, "delivered_min": delivered,
            "commission": commission, "delivery_fee": fee, "partner_payout": payout}


def _build_context(city, ops, supply_rules, partners):
    zone_ids = list(city["zones"])
    zidx = {z: i for i, z in enumerate(zone_ids)}
    km = road_km_matrix(city).loc[zone_ids, zone_ids].to_numpy()
    ztypes = np.array([city["zones"][z]["type"] for z in zone_ids])

    dest = ops["destination"]
    band_of_hour = {}
    for name, b in dest["bands"].items():
        for h in b.get("hours", []):
            band_of_hour[h] = name
    attract = {name: np.array([b["weights"][t] for t in ztypes])
               for name, b in dest["bands"].items()}
    decay = np.exp(-km / dest["decay_km"])
    dest_p = {(name, i): (attract[name] * decay[i]) / (attract[name] * decay[i]).sum()
              for name in attract for i in range(len(zone_ids))}

    def dest_choice(i, hour, rng):
        p = dest_p[band_of_hour.get(hour, "other"), i]
        return int(rng.choice(len(zone_ids), p=p))

    clusters = np.flatnonzero(ztypes == "restaurant_cluster")
    food = ops["food"]

    def restaurant_choice(i, rng):
        if ztypes[i] == "restaurant_cluster" or rng.random() < food["same_zone_restaurant_prob"]:
            return i
        near = clusters[km[i, clusters] <= food["restaurant_cluster_reach_km"]]
        return int(near[np.argmin(km[i, near])]) if len(near) else i

    hours = shift_hours(supply_rules)
    online = np.zeros((24, len(partners)), dtype=bool)
    for j, s in enumerate(partners["shift_type"]):
        online[hours[s], j] = True

    return {"city": city, "ops": ops, "km": km, "zone_ids": zone_ids, "zidx": zidx,
            "dest_choice": dest_choice, "restaurant_choice": restaurant_choice,
            "online_by_hour": online,
            "home_idx": partners["home_zone"].map(zidx).to_numpy(),
            "is_two_wheeler": (partners["vehicle_type"] == "two_wheeler").to_numpy(),
            "partner_ids": partners["partner_id"].to_numpy()}


def _requests_for_day(day_demand, rng):
    d = day_demand[day_demand["demand"] > 0]
    reps = d.loc[d.index.repeat(d["demand"]), ["hour", "zone_id", "service"]].reset_index(drop=True)
    reps["minute"] = reps["hour"] * 60 + rng.uniform(0, 60, len(reps))
    return reps.sort_values("minute", kind="stable").reset_index(drop=True)


def simulate(demand, calendar, partners, partner_days, config_dir=CITY_DIR,
             seed=None, progress=False):
    """Simulate every day. Returns (rides, orders, partner_hourly) DataFrames."""
    city, ops = load_city(config_dir), load_ops_rules(config_dir)
    ctx = _build_context(city, ops, load_supply_rules(config_dir), partners)
    rng = np.random.default_rng(ops["seed"] if seed is None else seed)
    pid_index = {p: i for i, p in enumerate(partners["partner_id"])}
    logged_by_date = partner_days.groupby("date")["partner_id"].apply(list).to_dict()
    demand_by_date = {d: g for d, g in demand.groupby("date")}

    all_rides, all_orders, all_snaps = [], [], []
    carry = None
    for k, day in enumerate(calendar.itertuples(index=False)):
        logged = np.zeros(len(partners), dtype=bool)
        logged[[pid_index[p] for p in logged_by_date.get(day.date, [])]] = True
        ctx["is_weekend"] = bool(day.is_weekend)
        reqs = _requests_for_day(demand_by_date.get(day.date, demand.iloc[0:0]), rng)
        rides, orders, snaps, carry = simulate_day(day.date, reqs, partners, logged, ctx,
                                                   rng, carry)
        all_rides += rides
        all_orders += orders
        for hour, idx, loc in snaps:
            all_snaps.append(pd.DataFrame({"date": day.date, "hour": hour,
                                           "partner_id": ctx["partner_ids"][idx],
                                           "zone_idx": loc}))
        if progress and (k + 1) % 7 == 0:
            print(f"  simulated {k + 1}/{len(calendar)} days")

    return _finalize(all_rides, all_orders, all_snaps, ctx)


def _ts(dates, minutes):
    m = pd.to_numeric(minutes, errors="coerce")
    return pd.to_datetime(dates) + pd.to_timedelta(m, unit="m")


def _finalize(rides, orders, snaps, ctx):
    zone_ids = np.array(ctx["zone_ids"])
    r = pd.DataFrame(rides)
    r["dest_zone_id"] = zone_ids[r.pop("dest_idx").to_numpy(dtype=int)]
    for c in ["request", "assigned", "pickup", "dropoff"]:
        r[f"{c}_ts"] = _ts(r["date"], r.pop(f"{c}_min")).dt.round("s")
    r.insert(0, "request_id", [f"R{i:08d}" for i in range(1, len(r) + 1)])

    o = pd.DataFrame(orders)
    o["restaurant_zone_id"] = zone_ids[o.pop("restaurant_zone_idx").to_numpy(dtype=int)]
    for c in ["placed", "assigned", "ready", "picked", "delivered"]:
        o[f"{c}_ts"] = _ts(o["date"], o.pop(f"{c}_min")).dt.round("s")
    o.insert(0, "order_id", [f"F{i:08d}" for i in range(1, len(o) + 1)])

    s = pd.concat(snaps, ignore_index=True)
    s["zone_id"] = zone_ids[s.pop("zone_idx").to_numpy()]
    hourly = _partner_busy_minutes(s, r, o)
    return r.drop(columns="date"), o.drop(columns="date"), hourly


def _partner_busy_minutes(snap, rides, orders):
    """Busy minutes and empty km per partner-hour (online snapshot as the base)."""
    jobs = pd.concat([
        rides.loc[rides.status == "completed", ["partner_id", "assigned_ts", "dropoff_ts", "pickup_km"]]
             .rename(columns={"dropoff_ts": "end_ts"}),
        orders.loc[orders.status == "delivered", ["partner_id", "assigned_ts", "delivered_ts", "pickup_km"]]
              .rename(columns={"delivered_ts": "end_ts"}),
    ], ignore_index=True)
    start = jobs["assigned_ts"].dt.floor("h")
    pieces = []
    for k in range(4):                       # a job spans at most a few hours
        h0 = start + pd.Timedelta(hours=k)
        h1 = h0 + pd.Timedelta(hours=1)
        lo = jobs["assigned_ts"].where(jobs["assigned_ts"] > h0, h0)
        hi = jobs["end_ts"].where(jobs["end_ts"] < h1, h1)
        mins = (hi - lo).dt.total_seconds() / 60
        keep = mins > 0
        pieces.append(pd.DataFrame({"partner_id": jobs.loc[keep, "partner_id"],
                                    "hour_ts": h0[keep], "busy_min": mins[keep]}))
    busy = pd.concat(pieces).groupby(["partner_id", "hour_ts"])["busy_min"].sum()
    empty = jobs.assign(hour_ts=start).groupby(["partner_id", "hour_ts"])["pickup_km"].sum()

    snap = snap.copy()
    snap["hour_ts"] = pd.to_datetime(snap["date"]) + pd.to_timedelta(snap["hour"], unit="h")
    snap = snap.join(busy, on=["partner_id", "hour_ts"]).join(empty, on=["partner_id", "hour_ts"])
    snap["busy_min"] = snap["busy_min"].fillna(0).clip(upper=60).round(2)
    snap["empty_km"] = snap["pickup_km"].fillna(0).round(2)
    snap["online_min"] = 60.0
    return snap[["date", "hour", "partner_id", "zone_id", "online_min", "busy_min", "empty_km"]]
