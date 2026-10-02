"""Stage 4: where would one more partner create the most value?

Usage:
    python scripts/bottlenecks.py
"""
from pathlib import Path

from pulse.optimization import marginal_value_table, top_bottlenecks
from pulse.utils import load_instance

ROOT = Path(__file__).resolve().parents[1]


def fmt(v):
    return "     n/a" if v is None else f"{v:>8,.0f}"


def main() -> None:
    inst = load_instance(ROOT / "data" / "sample" / "toy_lunch.yaml")
    rows = marginal_value_table(inst)

    print(f"PULSE marginal value of supply - {inst['period']}\n")
    print("  INR per period for one partner of this type starting in this zone")
    print(f"  {'zone':<6}{'type':<14}{'dual':>8}{'add +1':>8}{'lose -1':>8}  note")
    for r in rows:
        note = "degenerate: add/lose differ" if r["degenerate"] else ""
        print(f"  {r['zone']:<6}{r['partner_type']:<14}{fmt(r['dual'])}"
              f"{fmt(r['gain_plus_one'])}{fmt(r['loss_minus_one'])}  {note}")

    print("\nTop bottlenecks (value of adding one partner):")
    top = top_bottlenecks(rows)
    if not top:
        print("  None - extra supply adds no value anywhere this period.")
    for rank, r in enumerate(top, 1):
        print(f"  {rank}. Zone {r['zone']} {r['partner_type']}: "
              f"+INR {r['gain_plus_one']:,.0f} per period")


if __name__ == "__main__":
    main()
