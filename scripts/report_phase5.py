"""Phase 5: create the KPI views and regenerate every Phase 5 findings document.

For each analysis NN_name.sql in 05_Marketplace_Analytics/sql/, every result
set it returns is written into the matching NN_*.md document (blocks A, B, ...)
together with a generated headline summary. Nothing is typed by hand.

Needs PULSE_DW loaded; the reconciliation also reads data/processed/.

Usage:
    python scripts/report_phase5.py
"""
from decimal import Decimal
from pathlib import Path

import pandas as pd

from pulse.reporting import fill_block, inr, table
from pulse.warehouse.load import connect, load_settings, run_query_all, run_script

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "05_Marketplace_Analytics"
SQL = PHASE / "sql"
P = ROOT / "data" / "processed"

ANALYSES = {
    "01_marketplace_overview": "01_Marketplace_Overview.md",
    "02_mobility_performance": "02_Mobility_Performance.md",
    "03_food_performance": "03_Food_Delivery_Performance.md",
    "04_supply_utilization": "04_Supply_Utilization.md",
    "05_marketplace_economics": "05_Marketplace_Economics.md",
}


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """SQL Decimals -> int where whole, else float."""
    out = df.copy()
    for c in out.columns:
        if out[c].map(lambda v: isinstance(v, Decimal)).any():
            vals = out[c].map(lambda v: None if v is None else float(v))
            whole = vals.dropna().map(float.is_integer).all()
            out[c] = vals.map(lambda v: None if v is None else int(v)) if whole else vals
    return out


def fmt_for(df: pd.DataFrame) -> dict:
    f = {}
    for c in df.columns:
        name = str(c)
        if "%" in name:
            f[c] = "{:.1f}"
        elif "(INR)" in name and ("per" in name or "AOV" in name):
            f[c] = lambda v: f"₹{v:,.2f}" if isinstance(v, float) and not v.is_integer() else inr(v)
        elif "(INR)" in name:
            f[c] = inr
        elif "ratio" in name.lower():
            f[c] = "{:.2f}"
        elif "(min)" in name or "km" in name:
            f[c] = "{:.1f}"
        elif any(k in name for k in ("per day", "per weekday", "per hour", "per restaurant")):
            f[c] = lambda v: f"{v:,.0f}" if isinstance(v, int) else f"{v:,.1f}"
    return f


def md(df: pd.DataFrame) -> str:
    return table(df, fmt_for(df))


# ---------------- generated headline summaries ----------------
def h_overview(a, b):
    by = a.set_index("Service")
    tot = by.loc["Marketplace total"]
    rides, food = by.iloc[0], by.iloc[1]
    allp = b.set_index("Vehicle").loc["All partners"]
    return "\n".join([
        f"- **{tot['Demand per day']:,.0f} jobs per day**, of which "
        f"**{tot['Completion %']:.1f}%** are fulfilled.",
        f"- Rides are fulfilled **{rides['Completion %']:.1f}%** of the time versus "
        f"**{food['Completion %']:.1f}%** for food; **{rides['Lost: no partner %']:.1f}%** of ride "
        f"requests are lost because no partner can reach the customer.",
        f"- Platform revenue: **{inr(tot['Platform revenue (INR)'])}** over the period — "
        f"**₹{rides['Revenue per completed job (INR)']:.2f}** per ride and "
        f"**₹{food['Revenue per completed job (INR)']:.2f}** per food order.",
        f"- Partners are busy only **{allp['Utilization %']:.1f}%** of their online time.",
    ])


def h_mobility(a, b):
    worst, best = a.iloc[0], a.iloc[-1]
    peak = b.loc[b["Lost to no partner per weekday"].idxmax()]
    low = b.loc[b["Requests per weekday"] >= b["Requests per weekday"].median()].sort_values("Completion %").iloc[0]
    return "\n".join([
        f"- Ride completion ranges from **{worst['Completion %']:.1f}%** in **{worst['Zone type']}** zones "
        f"to **{best['Completion %']:.1f}%** in **{best['Zone type']}** zones.",
        f"- The most rides are lost at **{int(peak['Hour']):02d}:00** on weekdays: "
        f"**{peak['Lost to no partner per weekday']:,.0f}** requests per day find no partner.",
        f"- Among busy hours, completion is lowest at **{int(low['Hour']):02d}:00** "
        f"(**{low['Completion %']:.1f}%**).",
    ])


def h_food(a, b):
    worst, best = a.iloc[0], a.iloc[-1]
    otd = (b["Avg order-to-door (min)"] * b["Orders per weekday"]).sum() / b["Orders per weekday"].sum()
    peak = b.loc[b["Orders per weekday"].idxmax()]
    return "\n".join([
        f"- Delivery success ranges from **{worst['Delivered %']:.1f}%** in **{worst['Zone type']}** zones "
        f"to **{best['Delivered %']:.1f}%** in **{best['Zone type']}** zones.",
        f"- Weekday order-to-door time averages about **{otd:.0f} minutes**, and varies little across zone types.",
        f"- The busiest weekday hour is **{int(peak['Hour']):02d}:00** with "
        f"**{peak['Orders per weekday']:,.0f}** orders per day.",
    ])


def h_supply(a, b):
    peak = a.loc[a["Jobs lost to no partner"].idxmax()]
    top, bottom = b.iloc[0], b.iloc[-1]
    return "\n".join([
        f"- At **{int(peak['Hour']):02d}:00** on weekdays, **{peak['Jobs lost to no partner']:,.0f}** jobs per day "
        f"are lost to no partner while **{peak['Idle partner-hours']:,.0f}** partner-hours sit idle.",
        f"- **{top['Zone type']}** zones generate **{top['Share of work %']:.1f}%** of the work but hold only "
        f"**{top['Share of online partners %']:.1f}%** of online partners (ratio **{top['Work-to-supply ratio']:.2f}**).",
        f"- **{bottom['Zone type']}** zones hold **{bottom['Share of online partners %']:.1f}%** of online partners "
        f"for **{bottom['Share of work %']:.1f}%** of the work (ratio **{bottom['Work-to-supply ratio']:.2f}**).",
    ])


def h_economics(a, b):
    by = a.set_index("Service")
    rides, food = by.iloc[0], by.iloc[1]
    return "\n".join([
        f"- Food delivery provides **{food['Share of contribution %']:.1f}%** of contribution; rides "
        f"**{rides['Share of contribution %']:.1f}%**.",
        f"- Take rate: **{rides['Take rate %']:.1f}%** of ride fares and **{food['Take rate %']:.1f}%** of food GMV.",
        f"- Contribution per job: **₹{rides['Contribution per job (INR)']:.2f}** per ride and "
        f"**₹{food['Contribution per job (INR)']:.2f}** per food order.",
        f"- Weekly contribution ranges from **{inr(b['Contribution (INR)'].min())}** to "
        f"**{inr(b['Contribution (INR)'].max())}** across the {len(b)} weeks.",
    ])


HEADLINES = {"01_marketplace_overview": h_overview, "02_mobility_performance": h_mobility,
             "03_food_performance": h_food, "04_supply_utilization": h_supply,
             "05_marketplace_economics": h_economics}


def reconcile(overview: pd.DataFrame) -> str:
    """Overview figures recomputed from the generated CSVs must equal SQL."""
    rides = pd.read_csv(P / "rides.csv", usecols=["status", "fare", "partner_payout"])
    orders = pd.read_csv(P / "food_orders.csv",
                         usecols=["status", "commission", "delivery_fee", "partner_payout"])
    c, d = rides[rides.status == "completed"], orders[orders.status == "delivered"]
    py = {"Mobility": (len(rides), len(c), (c.fare - c.partner_payout).sum()),
          "Food Delivery": (len(orders), len(d), (d.commission + d.delivery_fee - d.partner_payout).sum())}
    rows = []
    for svc, (dem, comp, rev) in py.items():
        s = overview.set_index("Service").loc[svc]
        for name, sql_v, py_v, tol in [("Demand", s["Demand"], dem, 0), ("Completed", s["Completed"], comp, 0),
                                       ("Platform revenue (INR)", s["Platform revenue (INR)"], rev, 1)]:
            rows.append({"Service": svc, "Measure": name, "SQL": sql_v, "Python": round(py_v),
                         "Match": "✅" if abs(sql_v - py_v) <= tol else "❌"})
    df = pd.DataFrame(rows)
    return table(df, {"SQL": "{:,.0f}", "Python": "{:,.0f}"})


def main() -> None:
    settings = load_settings()
    with connect(settings) as conn:
        run_script(conn, SQL / "00_create_kpi_views.sql")
        print("KPI views created / updated")
        results = {}
        for stem, doc in ANALYSES.items():
            frames = [clean(f) for f in run_query_all(conn, SQL / f"{stem}.sql")]
            results[stem] = frames
            path = PHASE / doc
            for letter, df in zip("ABCDEFG", frames):
                fill_block(path, letter, md(df))
            fill_block(path, "headline", HEADLINES[stem](*frames))
            print(f"Updated {path.relative_to(ROOT)}  ({len(frames)} result sets)")

    fill_block(PHASE / ANALYSES["01_marketplace_overview"], "reconciliation",
               reconcile(results["01_marketplace_overview"][0]))
    print("Reconciliation written to 01_Marketplace_Overview.md")


if __name__ == "__main__":
    main()
