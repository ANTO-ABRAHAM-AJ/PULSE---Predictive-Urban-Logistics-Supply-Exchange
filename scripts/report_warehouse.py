"""Regenerate the result tables in 04_Data_Warehouse/Load_Results.md from SQL Server.

Needs PULSE_DW loaded (python scripts/load_warehouse.py) and the dataset
(python scripts/build_all.py) for the Python side of the reconciliation.

Usage:
    python scripts/report_warehouse.py
"""
from pathlib import Path

import pandas as pd

from pulse.reporting import fill_block, table
from pulse.warehouse.load import SQL_DIR, connect, load_settings, quality_checks, run_query

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
DOC = ROOT / "04_Data_Warehouse" / "Load_Results.md"


def python_reference() -> dict:
    """Same headline figures computed directly from the generated CSVs."""
    rides = pd.read_csv(P / "rides.csv", usecols=["zone_id", "status", "request_ts"],
                        parse_dates=["request_ts"])
    orders = pd.read_csv(P / "food_orders.csv", usecols=["status", "order_value"])
    hourly = pd.read_csv(P / "partner_hourly.csv", usecols=["online_min", "busy_min"])
    cal = pd.read_csv(P / "calendar.csv", parse_dates=["date"])
    zones = pd.read_csv(P / "zones.csv")
    office = set(zones.loc[zones["type"] == "office", "zone_id"])
    weekdays = set(cal.loc[~cal["is_weekend"], "date"])
    eve = rides[rides.zone_id.isin(office) & rides.request_ts.dt.hour.between(17, 19)
                & rides.request_ts.dt.normalize().isin(weekdays)]
    return {
        "Ride requests": len(rides),
        "Ride completion rate (%)": 100 * (rides.status == "completed").mean(),
        "Food orders": len(orders),
        "Food delivery rate (%)": 100 * (orders.status == "delivered").mean(),
        "Average order value (INR)": orders.order_value.mean(),
        "Partner utilization (%)": 100 * hourly.busy_min.sum() / hourly.online_min.sum(),
        "Office-zone weekday 17-19 ride completion (%)": 100 * (eve.status == "completed").mean(),
    }


def main() -> None:
    settings = load_settings()
    with connect(settings) as conn:
        summary = run_query(conn, SQL_DIR / "05_load_summary.sql")
        checks = quality_checks(conn)
        recon = run_query(conn, SQL_DIR / "06_reconciliation.sql")

    summary["row_count"] = summary["row_count"].astype(int)
    summary.columns = ["Table", "Role", "Rows"]
    total = summary["Rows"].sum()
    fill_block(DOC, "load_summary", table(summary, {"Rows": "{:,}"})
               + f"\n\n**{len(summary)} tables, {total:,} rows in total.**")

    checks["Result"] = checks["failing_rows"].map(lambda n: "✅ pass" if n == 0 else "❌ FAIL")
    checks.columns = ["Rule", "Failing rows", "Result"]
    passed = int((checks["Failing rows"] == 0).sum())
    fill_block(DOC, "quality", table(checks, {"Failing rows": "{:,}"})
               + f"\n\n**{passed} of {len(checks)} checks pass.**")

    ref = python_reference()
    recon["sql_value"] = recon["sql_value"].astype(float)
    recon["python_value"] = recon["measure"].map(ref)
    recon["Match"] = [("✅" if abs(s - p) < 0.01 else "❌") for s, p in zip(recon.sql_value, recon.python_value)]
    recon.columns = ["Measure", "SQL (warehouse)", "Python (generated files)", "Match"]
    fill_block(DOC, "reconciliation", table(recon, {"SQL (warehouse)": "{:,.2f}",
                                                    "Python (generated files)": "{:,.2f}"}))
    print(f"Updated {DOC.relative_to(ROOT)}")
    print(f"  {len(summary)} tables, {total:,} rows; {passed}/{len(checks)} quality checks pass; "
          f"{(recon['Match'] == '✅').sum()}/{len(recon)} reconciliation figures match")


if __name__ == "__main__":
    main()
