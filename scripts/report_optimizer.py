"""Regenerate the result tables in 10_Optimization/Validation_Results.md.

Usage:
    python scripts/report_optimizer.py      (about 10 seconds)
"""
import copy
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from pulse.optimization import marginal_value_table, solve_allocation, top_bottlenecks
from pulse.reporting import fill_block, inr, table
from pulse.utils import load_instance

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "10_Optimization" / "Validation_Results.md"
TOY = ROOT / "data" / "sample" / "toy_lunch.yaml"
sys.path.insert(0, str(Path(__file__).resolve().parent))
from compare_policies import compare  # noqa: E402

INR = inr


def stage1(inst):
    r = solve_allocation(inst)
    moves = pd.DataFrame(r.flows).query("`from` != `to`")
    moves = moves.rename(columns={"from": "From", "to": "To", "partner_type": "Partner type",
                                  "service": "Service", "partners": "Partners", "cost": "Cost"})
    out = "**Repositioning decided by the optimizer**\n\n"
    out += table(moves[["From", "To", "Partner type", "Service", "Partners", "Cost"]],
                 {"Partners": "{:.0f}", "Cost": INR})
    c = r.components
    econ = pd.DataFrame([
        ("Contribution", c["contribution"], 4080), ("Repositioning cost", c["reposition_cost"], 80),
        ("Unserved penalty", c["unserved_penalty"], 150), ("Objective", c["objective"], 3850)],
        columns=["Item", "Optimizer", "Hand calculation"])
    econ["Match"] = np.where(np.isclose(econ["Optimizer"], econ["Hand calculation"]), "✅", "❌")
    out += "\n\n**Economics vs hand calculation**\n\n"
    out += table(econ, {"Optimizer": INR, "Hand calculation": INR})
    unserved = {k: v for k, v in r.unserved.items() if v > 1e-6}
    out += "\n\nUnserved demand: " + ", ".join(f"{z} {s} = {v:.0f}" for (z, s), v in unserved.items())
    return out


def _variant(inst, change):
    i = copy.deepcopy(inst)
    change(i)
    return solve_allocation(i)


def stage2(inst):
    def no_supply(i):
        for z in i["zones"]:
            for k in i["partner_types"]:
                i["supply"][z][k] = 0

    def excess(i):
        for z in i["zones"]:
            for k in i["partner_types"]:
                i["supply"][z][k] *= 10

    cases = [
        ("No supply", no_supply, "Nothing moves; all demand unserved"),
        ("10× supply", excess, "Everything served, no repositioning"),
        ("A food = 1,000 (impossible)", lambda i: i["demand"]["A"].update(food=1000),
         "All reachable two-wheelers do food; no crash"),
        ("Free repositioning", lambda i: i.update(cost_per_km={k: 0 for k in i["partner_types"]}),
         "Same service outcome, ₹80 better"),
        ("C mobility 8 → 80 (spike)", lambda i: i["demand"]["C"].update(mobility=80),
         "A food stays fully served; only spare partners go to C"),
        ("80% food service floor", lambda i: i["min_service_level"].update(food=0.8),
         "Reported infeasible (E cannot reach 80%)"),
        ("100% mobility service floor", lambda i: i["min_service_level"].update(mobility=1.0),
         "Floor met exactly"),
    ]
    rows = []
    for name, change, expected in cases:
        r = _variant(inst, change)
        unserved = sum(r.unserved.values()) if r.ok else None
        rows.append({"Scenario": name, "Status": r.status,
                     "Objective": r.objective if r.ok else None,
                     "Unserved units": unserved,
                     "Repositioning cost": r.components.get("reposition_cost") if r.ok else None,
                     "Expected behaviour": expected})
    return table(pd.DataFrame(rows), {"Objective": INR, "Repositioning cost": INR,
                                      "Unserved units": "{:,.0f}"})


def _f(fmt, v):
    return fmt(v) if callable(fmt) else fmt.format(v)


def stage3(inst, draws=500):
    rows = compare(inst, draws)
    b, o = rows["baseline"], rows["optimized"]
    metrics = [("Contribution", lambda r: r.contribution, INR),
               ("Repositioning cost", lambda r: r.move_cost, INR),
               ("Dispatch deadhead", lambda r: r.dispatch_cost, INR),
               ("Unserved penalty", lambda r: r.unserved_penalty, INR),
               ("**Net value**", lambda r: r.net, INR),
               ("Service level — mobility", lambda r: r.service_level("mobility"), "{:.1%}"),
               ("Service level — food", lambda r: r.service_level("food"), "{:.1%}"),
               ("Utilization", lambda r: r.utilization, "{:.1%}")]
    lines = ["| Metric (mean per lunch hour) | Baseline | Optimized |", "|---|---|---|"]
    for name, f, fmt in metrics:
        lines.append(f"| {name} | {_f(fmt, np.mean([f(x) for x in b]))} | "
                     f"{_f(fmt, np.mean([f(x) for x in o]))} |")
    diff = np.array([x.net - y.net for x, y in zip(o, b)])
    se = diff.std(ddof=1) / np.sqrt(len(diff))
    base = np.mean([x.net for x in b])
    lines.append("")
    lines.append(f"**Uplift:** {INR(diff.mean())} per period "
                 f"({diff.mean() / base:.1%} of baseline net), 95% CI "
                 f"{INR(diff.mean() - 1.96 * se)} to {INR(diff.mean() + 1.96 * se)}. "
                 f"Optimized wins in **{np.mean(diff > 0):.0%}** of {draws} demand draws.")
    return "\n".join(lines)


def stage4(inst):
    rows = pd.DataFrame(marginal_value_table(inst))
    rows["degenerate"] = np.where(rows["degenerate"], "yes", "")
    rows = rows.rename(columns={"zone": "Zone", "partner_type": "Partner type", "dual": "Dual",
                                "gain_plus_one": "Add +1", "loss_minus_one": "Lose −1",
                                "degenerate": "Add ≠ lose"})
    out = table(rows, {"Dual": INR, "Add +1": INR, "Lose −1": INR})
    top = top_bottlenecks(marginal_value_table(inst))
    out += "\n\n**Top bottlenecks (value of one more partner):** " + "; ".join(
        f"{i}. Zone {r['zone']} {r['partner_type'].replace('_', '-')} — {INR(r['gain_plus_one'])}"
        for i, r in enumerate(top, 1))
    return out


def main() -> None:
    inst = load_instance(TOY)
    fill_block(DOC, "stage1", stage1(inst))
    fill_block(DOC, "stage2", stage2(inst))
    fill_block(DOC, "stage3", stage3(inst))
    fill_block(DOC, "stage4", stage4(inst))
    print(f"Updated {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
