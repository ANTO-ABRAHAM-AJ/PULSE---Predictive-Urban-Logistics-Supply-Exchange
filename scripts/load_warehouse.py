"""Phase 4: build the PULSE_DW star schema in SQL Server and load all data.

Needs the full dataset (python scripts/build_all.py) and SQL Server running.
Re-running rebuilds the warehouse from scratch.

Usage:
    python scripts/load_warehouse.py
"""
from pathlib import Path

from pulse.warehouse import TABLE_ORDER, build_tables, check_integrity, read_sources
from pulse.warehouse.load import load_all, load_settings

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"


def main() -> None:
    if not (P / "customers.csv").exists():
        raise SystemExit("customers.csv not found - run python scripts/build_all.py first")
    settings = load_settings()
    print(f"Target: {settings['server']} / {settings['database']}")

    print("1. Transforming source files into star-schema tables...")
    tables = build_tables(read_sources(P))
    problems = check_integrity(tables)
    if problems:
        raise SystemExit("Integrity problems found before loading:\n  " + "\n  ".join(problems))
    print("   keys unique and every foreign key resolves")

    print("2. Loading into SQL Server...")
    checks = load_all(tables, TABLE_ORDER, settings)

    print("3. Data-quality checks (failing rows should all be 0):")
    for row in checks.itertuples(index=False):
        flag = "OK  " if row.failing_rows == 0 else "FAIL"
        print(f"   [{flag}] {row.check_name:<48} {row.failing_rows:>8,}")
    failed = int((checks["failing_rows"] > 0).sum())
    print("\nWarehouse loaded." if failed == 0 else f"\n{failed} data-quality check(s) failed.")


if __name__ == "__main__":
    main()
