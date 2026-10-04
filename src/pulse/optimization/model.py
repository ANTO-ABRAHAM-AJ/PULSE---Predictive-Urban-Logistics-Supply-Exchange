"""PULSE core: single-period supply allocation & repositioning LP.

Decision
    x[i, j, k, s] >= 0   partners of type k moved from zone i to serve
                         service s in zone j  (i == j means "stay")
    u[j, s]       >= 0   unserved demand for service s in zone j

Objective (maximize)
      sum m[s] * (D[j,s] - u[j,s])            contribution from served demand
    - sum c[k] * dist[i,j] * x[i,j,k,s]        repositioning cost
    - sum p[s] * u[j,s]                        service-level penalty

Constraints
    supply:        sum_{j,s} x[i,j,k,s]               <= S[i,k]
    coverage:      sum_{i,k} q[s] * x[i,j,k,s] + u[j,s] >= D[j,s]
    unserved cap:  u[j,s] <= D[j,s]
    service level: u[j,s] <= (1 - alpha[s]) * D[j,s]
    eligibility / reach: x is only created where e[k,s] and dist[i,j] <= tau

Optional extension (Phase 10, used when the instance has "service_reach_km"):
    y[i, j, k, s] >= 0   partners of type k that STAY in zone i but serve
                         demand in a nearby zone j through normal dispatch
                         (dist[i,j] <= reach[s]); no repositioning cost, but
                         each covers only remote_efficiency[s] x q[s] jobs
                         because of the pickup drive.
    This matches how dispatch really works, so paid moves (x with i != j)
    are chosen only when a whole neighbourhood is short. Without the
    "service_reach_km" key the model is exactly the Stage 1-4 model.

Solved as a continuous LP with GLOP so dual values are valid
(used for marginal-value analysis in Stage 4).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ortools.linear_solver import pywraplp

_STATUS = {
    pywraplp.Solver.OPTIMAL: "OPTIMAL",
    pywraplp.Solver.FEASIBLE: "FEASIBLE",
    pywraplp.Solver.INFEASIBLE: "INFEASIBLE",
    pywraplp.Solver.UNBOUNDED: "UNBOUNDED",
    pywraplp.Solver.ABNORMAL: "ABNORMAL",
    pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED",
}

EPS = 1e-6


@dataclass
class AllocationResult:
    status: str
    objective: float | None = None
    flows: list[dict] = field(default_factory=list)       # non-zero x
    served: dict = field(default_factory=dict)            # (zone, service) -> units
    unserved: dict = field(default_factory=dict)          # (zone, service) -> units
    components: dict = field(default_factory=dict)        # objective breakdown
    supply_duals: dict = field(default_factory=dict)      # (zone, partner_type) -> INR per extra partner
    message: str = ""

    @property
    def ok(self) -> bool:
        return self.status == "OPTIMAL"


def _arcs(inst: dict):
    """Yield every allowed (i, j, k, s) combination."""
    tau = inst["max_reposition_km"]
    for i in inst["zones"]:
        for j in inst["zones"]:
            if inst["distance_km"][i][j] > tau:
                continue
            for k in inst["partner_types"]:
                for s in inst["services"]:
                    if inst["eligibility"][k][s]:
                        yield i, j, k, s


def solve_allocation(inst: dict) -> AllocationResult:
    solver = pywraplp.Solver.CreateSolver("GLOP")
    if solver is None:
        raise RuntimeError("GLOP solver not available in this OR-Tools build")

    Z, S, K = inst["zones"], inst["services"], inst["partner_types"]
    dist, q = inst["distance_km"], inst["jobs_per_partner"]
    m, p, c = inst["contribution"], inst["penalty"], inst["cost_per_km"]
    supply, demand, alpha = inst["supply"], inst["demand"], inst["min_service_level"]

    # Variables
    x = {a: solver.NumVar(0.0, solver.infinity(), "x_%s_%s_%s_%s" % a) for a in _arcs(inst)}
    y = {}                                       # serve-from-neighbour arcs (optional)
    reach = inst.get("service_reach_km")
    if reach:
        eff = inst["remote_efficiency"]
        for i in Z:
            for j in Z:
                if i == j:
                    continue
                for k in K:
                    for s in S:
                        if inst["eligibility"][k][s] and dist[i][j] <= reach[s]:
                            y[i, j, k, s] = solver.NumVar(0.0, solver.infinity(), "y_%s_%s_%s_%s" % (i, j, k, s))
    u = {}
    for j in Z:
        for s in S:
            cap = (1.0 - alpha[s]) * demand[j][s]
            u[j, s] = solver.NumVar(0.0, max(cap, 0.0), f"u_{j}_{s}")

    # Supply constraints
    out_x, in_x, out_y, in_y = {}, {}, {}, {}
    for (a, b, kk, ss), v in x.items():
        out_x.setdefault((a, kk), []).append(v)
        in_x.setdefault((b, ss), []).append(q[ss] * v)
    for (a, b, kk, ss), v in y.items():
        out_y.setdefault((a, kk), []).append(v)
        in_y.setdefault((b, ss), []).append(inst["remote_efficiency"][ss] * q[ss] * v)

    supply_con = {}
    for i in Z:
        for k in K:
            supply_con[i, k] = solver.Add(
                sum(out_x.get((i, k), [])) + sum(out_y.get((i, k), [])) <= supply[i][k],
                f"supply_{i}_{k}",
            )

    # Coverage constraints
    for j in Z:
        for s in S:
            solver.Add(
                sum(in_x.get((j, s), [])) + sum(in_y.get((j, s), [])) + u[j, s] >= demand[j][s],
                f"cover_{j}_{s}",
            )

    # Objective
    served_value = sum(m[s] * (demand[j][s] - u[j, s]) for j in Z for s in S)
    move_cost = sum(c[k] * dist[i][j] * v for (i, j, k, s), v in x.items())
    penalty = sum(p[s] * u[j, s] for j in Z for s in S)
    solver.Maximize(served_value - move_cost - penalty)

    status = _STATUS.get(solver.Solve(), "UNKNOWN")
    if status != "OPTIMAL":
        msg = ("No allocation meets the minimum service levels with current supply."
               if status == "INFEASIBLE" else f"Solver returned {status}.")
        return AllocationResult(status=status, message=msg)

    flows = [
        {"from": i, "to": j, "partner_type": k, "service": s,
         "partners": v.solution_value(),
         "cost": c[k] * dist[i][j] * v.solution_value()}
        for (i, j, k, s), v in x.items() if v.solution_value() > EPS
    ]
    unserved = {(j, s): u[j, s].solution_value() for j in Z for s in S}
    served = {(j, s): demand[j][s] - unserved[j, s] for j in Z for s in S}

    components = {
        "contribution": sum(m[s] * served[j, s] for j in Z for s in S),
        "reposition_cost": sum(f["cost"] for f in flows),
        "unserved_penalty": sum(p[s] * unserved[j, s] for j in Z for s in S),
    }
    components["objective"] = (components["contribution"]
                               - components["reposition_cost"]
                               - components["unserved_penalty"])

    # Shadow price of each supply constraint: the objective gain from one
    # more partner of type k starting in zone i (valid for small changes).
    supply_duals = {key: con.dual_value() for key, con in supply_con.items()}

    return AllocationResult(status=status, objective=solver.Objective().Value(),
                            flows=flows, served=served, unserved=unserved,
                            components=components, supply_duals=supply_duals)
