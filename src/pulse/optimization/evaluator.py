"""Independent evaluator: scores ANY allocation plan on realized demand.

Why this exists
    The optimizer plans on *forecast* demand and would score itself with its
    own objective. That is biased. The evaluator instead:
      1. draws realized demand (Poisson around the forecast),
      2. puts partners where a plan says they start the period,
      3. dispatches realized requests one at a time in random arrival order
         to the nearest available eligible partner (within tau),
      4. scores every policy with the same rules.

Plan format
    A plan is a dict:
      "pools":       list of {"zone", "partner_type", "service", "partners"}
                     service = None means the partner can serve any eligible
                     service; a service name means it is reserved for it.
      "move_cost":   INR spent repositioning before the period starts.

Capacity is tracked in integer "slots" so food (3 jobs/hour) and mobility
(2 jobs/hour) share a partner's hour exactly: slots per partner = lcm(q),
and one job of service s uses lcm(q) / q[s] slots.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np


@dataclass
class EvaluationResult:
    contribution: float = 0.0
    move_cost: float = 0.0
    dispatch_cost: float = 0.0          # deadhead km when serving from another zone
    unserved_penalty: float = 0.0
    served: dict = field(default_factory=dict)
    unserved: dict = field(default_factory=dict)
    utilization: float = 0.0

    @property
    def net(self) -> float:
        return (self.contribution - self.move_cost
                - self.dispatch_cost - self.unserved_penalty)

    def service_level(self, service: str | None = None) -> float:
        keys = [k for k in self.served if service is None or k[1] == service]
        demand = sum(self.served[k] + self.unserved[k] for k in keys)
        return sum(self.served[k] for k in keys) / demand if demand else 1.0


def sample_demand(inst: dict, rng: np.random.Generator) -> dict:
    """One realized-demand draw: Poisson around each forecast."""
    return {z: {s: int(rng.poisson(inst["demand"][z][s])) for s in inst["services"]}
            for z in inst["zones"]}


def evaluate(inst: dict, plan: dict, realized: dict,
             rng: np.random.Generator) -> EvaluationResult:
    Z, S = inst["zones"], inst["services"]
    q, dist, tau = inst["jobs_per_partner"], inst["distance_km"], inst["max_reposition_km"]
    lcm = math.lcm(*(int(q[s]) for s in S))
    need = {s: lcm // int(q[s]) for s in S}

    # Remaining slots per pool: (zone, partner_type, reserved_service_or_None)
    slots: dict = {}
    for p in plan["pools"]:
        key = (p["zone"], p["partner_type"], p["service"])
        slots[key] = slots.get(key, 0) + int(round(p["partners"] * lcm))
    total_slots = sum(slots.values())

    # Realized requests in random arrival order.
    requests = [(z, s) for z in Z for s in S for _ in range(realized[z][s])]
    order = rng.permutation(len(requests))

    res = EvaluationResult(move_cost=plan.get("move_cost", 0.0))
    res.served = {(z, s): 0 for z in Z for s in S}
    res.unserved = {(z, s): 0 for z in Z for s in S}

    for idx in order:
        j, s = requests[idx]
        chosen = None
        for i in sorted((i for i in Z if dist[i][j] <= tau), key=lambda i: dist[i][j]):
            options = [key for key, left in slots.items()
                       if key[0] == i and left >= need[s]
                       and inst["eligibility"][key[1]][s]
                       and key[2] in (None, s)]
            if options:
                weights = np.array([slots[k] for k in options], dtype=float)
                chosen = options[rng.choice(len(options), p=weights / weights.sum())]
                break
        if chosen is None:
            res.unserved[j, s] += 1
            res.unserved_penalty += inst["penalty"][s]
            continue
        slots[chosen] -= need[s]
        res.served[j, s] += 1
        res.contribution += inst["contribution"][s]
        res.dispatch_cost += inst["cost_per_km"][chosen[1]] * dist[chosen[0]][j]

    used = total_slots - sum(slots.values())
    res.utilization = used / total_slots if total_slots else 0.0
    return res
