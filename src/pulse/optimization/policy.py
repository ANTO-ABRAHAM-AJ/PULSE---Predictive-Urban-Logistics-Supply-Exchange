"""Hourly repositioning policy driven by the PULSE allocation LP (Phase 10).

At the start of every hour the policy:
  1. counts partners by zone and vehicle — idle partners fully, partners still
     busy in proportion to the part of the hour they will be free;
  2. reads expected demand for the coming 90 minutes: a blend of the forecast
     for this hour and the next (`lookahead` weight on the next hour);
  3. solves the allocation LP (Stages 1-4 model, unchanged) on Bengaluru;
  4. turns the LP's cross-zone flows into whole moves of IDLE partners
     (stochastic rounding, fixed seed), cheapest-to-move first.

The LP also allocates two-wheeler capacity between services; in the
simulation, jobs inside a zone are still dispatched to the nearest partner,
so the policy acts through positioning only.
"""
from __future__ import annotations

import numpy as np

from pulse.optimization.model import solve_allocation

SERVICES = ["mobility", "food"]
TYPES = ["two_wheeler", "four_wheeler"]


class OptimizerPolicy:
    def __init__(self, forecast: dict, economics: dict, ctx: dict, lookahead: float = 0.5,
                 max_move_km: float = 12.0, seed: int = 10, record: bool = True,
                 remote_efficiency: dict | None = None):
        """`forecast[(date, hour, zone_id, service)]` = expected jobs in that hour."""
        self.forecast, self.econ, self.lookahead = forecast, economics, lookahead
        self.rng = np.random.default_rng(seed)
        self.zone_ids = ctx["zone_ids"]
        km = ctx["km"]
        self.distance = {a: {b: float(km[i, j]) for j, b in enumerate(self.zone_ids)}
                         for i, a in enumerate(self.zone_ids)}
        self.max_move_km = max_move_km
        self.cost_per_km_by_type = {True: economics["cost_per_km"]["two_wheeler"],
                                    False: economics["cost_per_km"]["four_wheeler"]}
        self.record, self.plans, self.duals = record, [], []
        self.remote_efficiency = remote_efficiency or {"mobility": 0.6, "food": 0.8}
        self.ctx = ctx

    def reach(self, is_weekend, hour):
        from pulse.generation.city import speed_kmh
        d = self.ctx["ops"]["dispatch"]
        ride_km = speed_kmh(self.ctx["city"], hour, is_weekend) * d["max_wait_min"]["mobility"] / 60.0
        return {"mobility": min(ride_km, d["max_pickup_km"]), "food": d["max_pickup_km"]}

    def expected_demand(self, date, hour):
        nxt = min(hour + 1, 23)
        w = self.lookahead if hour < 23 else 0.0
        return {z: {s: (1 - w) * self.forecast.get((date, hour, z, s), 0.0)
                       + w * self.forecast.get((date, nxt, z, s), 0.0) for s in SERVICES}
                for z in self.zone_ids}

    def __call__(self, day, hour, state, ctx):
        date, _ = day
        t0 = hour * 60.0
        on = state["online"][hour] & state["logged"]
        if hour < 23:
            on_next = state["online"][hour + 1] & state["logged"]
        else:
            on_next = on
        free_frac = np.clip((t0 + 60.0 - state["free_at"]) / 60.0, 0.0, 1.0)
        supply = {z: {k: 0.0 for k in TYPES} for z in self.zone_ids}
        for p in np.flatnonzero(on):
            supply[self.zone_ids[state["loc"][p]]][TYPES[0] if state["tw"][p] else TYPES[1]] += free_frac[p]

        inst = {"zones": self.zone_ids, "services": SERVICES, "partner_types": TYPES,
                "distance_km": self.distance, "max_reposition_km": self.max_move_km,
                "eligibility": {"two_wheeler": {"mobility": True, "food": True},
                                "four_wheeler": {"mobility": True, "food": False}},
                "jobs_per_partner": self.econ["jobs_per_partner"],
                "contribution": self.econ["contribution"], "penalty": self.econ["penalty"],
                "cost_per_km": self.econ["cost_per_km"],
                "supply": supply, "demand": self.expected_demand(date, hour),
                "min_service_level": {"mobility": 0.0, "food": 0.0},
                # Dispatch already serves nearby zones without moving anyone:
                # rides within the 20-minute reach at this hour's speed,
                # food within the 8 km pickup limit (just-in-time dispatch).
                "service_reach_km": self.reach(day[1], hour),
                "remote_efficiency": self.remote_efficiency}
        res = solve_allocation(inst)
        if not res.ok:
            return []
        if self.record:
            self.plans += [{"date": date, "hour": hour, **f} for f in res.flows if f["from"] != f["to"]]
            self.duals += [{"date": date, "hour": hour, "zone_id": z, "partner_type": k, "dual": v}
                           for (z, k), v in res.supply_duals.items() if v > 1e-6]

        # Aggregate cross-zone flows by (from, to, type) and round to whole partners.
        wanted = {}
        for f in res.flows:
            if f["from"] != f["to"]:
                key = (f["from"], f["to"], f["partner_type"])
                wanted[key] = wanted.get(key, 0.0) + f["partners"]
        zidx = ctx["zidx"]
        idle = on & on_next & (state["free_at"] <= t0 + 5.0)
        used = np.zeros(len(idle), dtype=bool)
        moves = []
        for (a, b, k), x in sorted(wanted.items(), key=lambda kv: self.distance[kv[0][0]][kv[0][1]]):
            n = int(np.floor(x + self.rng.random()))
            if n <= 0:
                continue
            is_tw = k == "two_wheeler"
            cand = np.flatnonzero(idle & ~used & (state["loc"] == zidx[a]) & (state["tw"] == is_tw))
            for p in cand[:n]:
                used[p] = True
                moves.append((int(p), zidx[b]))
        return moves
