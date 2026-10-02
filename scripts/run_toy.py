"""Solve the toy lunch instance and print a readable allocation report.

Usage (from repo root, after `pip install -e .`):
    python scripts/run_toy.py
"""
from pathlib import Path

from pulse.optimization import solve_allocation
from pulse.utils import load_instance

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    inst = load_instance(ROOT / "data" / "sample" / "toy_lunch.yaml")
    res = solve_allocation(inst)

    print(f"PULSE toy allocation - {inst['period']}")
    print(f"Status: {res.status}")
    if not res.ok:
        print(res.message)
        return

    print("\nPartner movements (stays shown as X -> X):")
    print(f"  {'from':<5}{'to':<5}{'type':<14}{'service':<10}{'partners':>9}{'cost':>8}")
    for f in sorted(res.flows, key=lambda f: (f["from"], f["to"], f["service"])):
        print(f"  {f['from']:<5}{f['to']:<5}{f['partner_type']:<14}{f['service']:<10}"
              f"{f['partners']:>9.2f}{f['cost']:>8.1f}")

    print("\nService outcome by zone:")
    print(f"  {'zone':<6}{'service':<10}{'demand':>8}{'served':>8}{'unserved':>10}{'level':>8}")
    for j in inst["zones"]:
        for s in inst["services"]:
            d = inst["demand"][j][s]
            sv, un = res.served[j, s], res.unserved[j, s]
            lvl = sv / d if d else 1.0
            print(f"  {j:<6}{s:<10}{d:>8.0f}{sv:>8.1f}{un:>10.1f}{lvl:>8.0%}")

    c = res.components
    print("\nEconomics (INR):")
    print(f"  Contribution        {c['contribution']:>10,.0f}")
    print(f"  Repositioning cost -{c['reposition_cost']:>10,.0f}")
    print(f"  Unserved penalty   -{c['unserved_penalty']:>10,.0f}")
    print(f"  Objective           {c['objective']:>10,.0f}")


if __name__ == "__main__":
    main()
