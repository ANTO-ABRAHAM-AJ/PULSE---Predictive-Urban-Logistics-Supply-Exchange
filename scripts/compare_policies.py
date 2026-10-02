"""Stage 3: optimized plan vs naive baseline on many realized-demand draws.

Both policies face the SAME demand draw and the SAME arrival order in each
run (common random numbers), so differences come from the policy only.

Usage:
    python scripts/compare_policies.py            # 500 draws
    python scripts/compare_policies.py --draws 2000
"""
import argparse
from pathlib import Path

import numpy as np

from pulse.optimization import baseline_plan, evaluate, optimized_plan, sample_demand
from pulse.utils import load_instance

ROOT = Path(__file__).resolve().parents[1]


def compare(inst: dict, draws: int, seed: int = 42) -> dict:
    plans = {"baseline": baseline_plan(inst), "optimized": optimized_plan(inst)}
    master = np.random.default_rng(seed)
    rows = {name: [] for name in plans}
    for _ in range(draws):
        demand_seed, order_seed = master.integers(0, 2**32, size=2)
        realized = sample_demand(inst, np.random.default_rng(demand_seed))
        for name, plan in plans.items():
            rows[name].append(evaluate(inst, plan, realized,
                                       np.random.default_rng(order_seed)))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--draws", type=int, default=500)
    ap.add_argument("--data", default=str(ROOT / "data" / "sample" / "toy_lunch.yaml"))
    args = ap.parse_args()

    inst = load_instance(args.data)
    rows = compare(inst, args.draws)
    b, o = rows["baseline"], rows["optimized"]
    diff = np.array([x.net - y.net for x, y in zip(o, b)])

    def mean(rs, f):
        return float(np.mean([f(r) for r in rs]))

    print(f"PULSE policy comparison - {inst['period']} - {args.draws} demand draws\n")
    print(f"  {'metric (mean per period)':<28}{'baseline':>12}{'optimized':>12}")
    metrics = [
        ("Contribution (INR)", lambda r: r.contribution),
        ("Repositioning cost (INR)", lambda r: r.move_cost),
        ("Dispatch deadhead (INR)", lambda r: r.dispatch_cost),
        ("Unserved penalty (INR)", lambda r: r.unserved_penalty),
        ("Net (INR)", lambda r: r.net),
        ("Service level - mobility", lambda r: r.service_level("mobility")),
        ("Service level - food", lambda r: r.service_level("food")),
        ("Utilization", lambda r: r.utilization),
    ]
    for label, f in metrics:
        bv, ov = mean(b, f), mean(o, f)
        fmt = "{:>12.1%}" if "level" in label or "Util" in label else "{:>12,.0f}"
        print(f"  {label:<28}" + fmt.format(bv) + fmt.format(ov))

    se = diff.std(ddof=1) / np.sqrt(len(diff))
    print(f"\n  Optimized - baseline, net: {diff.mean():+,.0f} INR per period "
          f"(95% CI {diff.mean() - 1.96 * se:+,.0f} to {diff.mean() + 1.96 * se:+,.0f})")
    print(f"  Optimized wins in {np.mean(diff > 0):.0%} of draws, "
          f"ties in {np.mean(diff == 0):.0%}, loses in {np.mean(diff < 0):.0%}")


if __name__ == "__main__":
    main()
