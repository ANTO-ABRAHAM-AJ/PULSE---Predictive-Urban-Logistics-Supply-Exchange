"""Policies expressed as evaluator plans.

Naive baseline: no repositioning. Every partner starts in its home zone and
can take any eligible job; the evaluator's dispatcher then sends the nearest
available partner to each request as it arrives.

Optimized plan: partners start where the LP put them, reserved for the
service the LP chose. Partners the LP left unassigned stay home, flexible.
"""
from __future__ import annotations

from pulse.optimization.model import AllocationResult, solve_allocation


def baseline_plan(inst: dict) -> dict:
    pools = [{"zone": z, "partner_type": k, "service": None,
              "partners": inst["supply"][z][k]}
             for z in inst["zones"] for k in inst["partner_types"]
             if inst["supply"][z][k] > 0]
    return {"name": "baseline", "pools": pools, "move_cost": 0.0}


def optimized_plan(inst: dict, result: AllocationResult | None = None) -> dict:
    if result is None:
        result = solve_allocation(inst)
    if not result.ok:
        raise ValueError(f"Cannot build a plan from a {result.status} solution")

    pools = [{"zone": f["to"], "partner_type": f["partner_type"],
              "service": f["service"], "partners": f["partners"]}
             for f in result.flows]

    # Partners the LP did not assign stay home, unreserved.
    for z in inst["zones"]:
        for k in inst["partner_types"]:
            assigned = sum(f["partners"] for f in result.flows
                           if f["from"] == z and f["partner_type"] == k)
            spare = inst["supply"][z][k] - assigned
            if spare > 1e-6:
                pools.append({"zone": z, "partner_type": k,
                              "service": None, "partners": spare})

    return {"name": "optimized", "pools": pools,
            "move_cost": result.components["reposition_cost"]}
