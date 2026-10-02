"""Stage 4 / Phase 10B: marginal value of supply and bottleneck ranking.

Two ways to price one extra partner of type k in zone i:

1. Shadow price (dual) of the supply constraint, read straight from the LP.
   Fast, but only valid for small changes, and when the solution is
   degenerate (several bases are optimal) the solver may report either the
   "add one" or the "lose one" value.

2. Re-solving with supply +1 and -1. Slower, but exact for the change
   management actually asks about.

Because the LP objective is concave in its supply limits, the three numbers
must always satisfy:

    gain from +1  <=  dual  <=  loss from -1

`marginal_value_table` reports all three, and the tests check this ordering.
The ranking uses the +1 re-solve, since "what is one more partner worth?"
is the business question.
"""
from __future__ import annotations

import copy

from pulse.optimization.model import solve_allocation


def _objective_with_supply(inst: dict, zone: str, ptype: str, change: float) -> float | None:
    trial = copy.deepcopy(inst)
    trial["supply"][zone][ptype] += change
    res = solve_allocation(trial)
    return res.objective if res.ok else None


def marginal_value_table(inst: dict, delta: float = 1.0) -> list[dict]:
    base = solve_allocation(inst)
    if not base.ok:
        raise ValueError(f"Base problem is {base.status}; marginal values undefined")

    rows = []
    for (zone, ptype), dual in base.supply_duals.items():
        up = _objective_with_supply(inst, zone, ptype, +delta)
        gain = (up - base.objective) / delta if up is not None else None

        loss = None
        if inst["supply"][zone][ptype] >= delta:
            down = _objective_with_supply(inst, zone, ptype, -delta)
            if down is not None:
                loss = (base.objective - down) / delta

        rows.append({
            "zone": zone,
            "partner_type": ptype,
            "dual": round(dual, 6) + 0.0,  # +0.0 turns -0.0 into 0.0
            "gain_plus_one": None if gain is None else round(gain, 6),
            "loss_minus_one": None if loss is None else round(loss, 6),
            "degenerate": loss is not None and gain is not None and abs(loss - gain) > 1e-6,
        })
    return rows


def top_bottlenecks(rows: list[dict], n: int = 5) -> list[dict]:
    """Where one more partner earns the most (positive gains only)."""
    ranked = [r for r in rows if r["gain_plus_one"] and r["gain_plus_one"] > 1e-6]
    return sorted(ranked, key=lambda r: r["gain_plus_one"], reverse=True)[:n]
