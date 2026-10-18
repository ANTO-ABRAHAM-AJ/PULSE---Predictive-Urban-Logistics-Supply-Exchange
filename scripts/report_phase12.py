"""Phase 12: build the Power BI semantic layer and its validation numbers.

1. Writes the Bengaluru zone map as TopoJSON (Power BI Shape Map input).
2. Creates the pbi.* views in PULSE_DW (12_PowerBI/sql/00_create_powerbi_views.sql).
3. Runs 12_PowerBI/sql/01_dashboard_checks.sql and writes the numbers every
   DAX measure must reproduce into 12_PowerBI/02_DAX_Measures.md.
4. Writes the row count of every Power BI table into 01_Data_Model.md and
   the measure catalogue (parsed from dax/PULSE_measures.dax) into 02.

Run after report_phase11.py. Takes under a minute.

Usage:
    python scripts/report_phase12.py
"""
import importlib.util
import re
from pathlib import Path

import pandas as pd

from pulse.geo.topojson import write_zone_topojson
from pulse.reporting import fill_block, inr, table

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "12_PowerBI"
SQL = PHASE / "sql"
DAX = PHASE / "dax" / "PULSE_measures.dax"
MAP = PHASE / "map" / "bengaluru_zones.json"
MODEL_DOC = PHASE / "01_Data_Model.md"
DAX_DOC = PHASE / "02_DAX_Measures.md"

_spec = importlib.util.spec_from_file_location("report_phase5", ROOT / "scripts" / "report_phase5.py")
_p5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p5)
clean, md = _p5.clean, _p5.md

# Power BI table -> (grain, role); order = load order in 01_Data_Model.md
TABLES = {
    "Dim_Time": ("Hour (time_key = yyyymmddhh)", "Calendar, dayparts, periods, weather"),
    "Dim_Zone": ("Zone", "Zone names, types, map key"),
    "Dim_Destination_Zone": ("Zone", "Destination of a repositioning move"),
    "Dim_Service": ("Service", "Mobility / Food Delivery"),
    "Dim_Vehicle": ("Vehicle type", "Two-wheeler / cab"),
    "Dim_Scenario": ("Simulated policy", "Names, order, colours, levers"),
    "Dim_Forecast_Model": ("Forecast model", "Names, order, benchmark flag"),
    "Fact_Marketplace": ("Zone x hour x service", "Observed demand, outcomes, money (16 weeks)"),
    "Fact_Supply": ("Zone x hour x vehicle", "Partner-hours: online, busy, idle; empty km"),
    "Fact_Pressure": ("Zone x hour", "Pressure index inputs, states, shortage types"),
    "Fact_Demand_Forecast": ("Zone x hour x service x model", "Holdout forecasts vs actual"),
    "Fact_Pressure_Forecast": ("Zone x hour", "Week-ahead shortage warnings vs outcome"),
    "Fact_Policy": ("Scenario x zone x hour x service", "Simulated outcomes per policy"),
    "Fact_Repositioning": ("Scenario x hour x corridor", "Optimizer moves"),
    "Fact_Supply_Value": ("Scenario x zone x hour x vehicle", "Value of one more partner (shadow price)"),
    "Fact_Incentives": ("Scenario x zone x hour", "Bonus partner-hours and cost"),
    "Fact_Scenario_Economics": ("Scenario", "Revenue, costs, contribution (whole holdout)"),
    "Stress_Summary": ("Stress case x policy", "Stress-test outcomes"),
    "Stress_Cases": ("Stress case", "Inputs for the bonus what-if"),
}

# ---------------------------------------------------------------- catalogue
TEXT_MEASURES = ("Headline", "Playbook", "Pressure State", "Colour", "Title", "Best Lever at Job Value")
FORMAT_OVERRIDES = {
    "Revenue per Completed Job": "₹#,0.00", "Break-even Bonus": "₹#,0.0", "Net Cost per Recovered Job": "₹#,0.0",
    "Break-even Job Value": "₹#,0.0", "Revenue per Rupee of Incentive": "0.00", "Avg Partners Online": "#,0.0",
    "Moves per Day": "#,0.0", "Econ Moves per Day": "#,0.0", "Map Value": "Dynamic (see 04_Interactivity.md)",
    "Selected Bonus": "₹#,0", "Empty km per Busy Hour": "0.0",
    "Value of One More Partner-Hour": "₹#,0", "Value of One More Two-Wheeler": "₹#,0",
    "Stress Cases Paying at Bonus": "0", "Ladder Service Cost per Job": "₹#,0.0", "Ladder Bonus Cost per Job": "₹#,0.0",
    "Selected Job Value": "₹#,0",
}
MONEY_WORDS = ("Revenue", "Cost", "Contribution", "Gain", "Payout", "Gross Value", "Net vs", "Uplift")


def measure_format(name: str) -> str:
    if name in FORMAT_OVERRIDES:
        return FORMAT_OVERRIDES[name]
    if any(w in name for w in TEXT_MEASURES):
        return "Text"
    if name.endswith("%"):
        return "0.0%"
    if "MPI" in name:
        return "0.00"
    if "(min)" in name or "km" in name:
        return "0.0"
    if any(w in name for w in MONEY_WORDS):
        return "₹#,0"
    return "#,0"


def measure_catalogue(path: Path = DAX) -> pd.DataFrame:
    """Every MEASURE in the .dax file with its display folder (section) and format string."""
    text = path.read_text(encoding="utf-8").split("\nEVALUATE", 1)[0]
    rows, folder = [], ""
    for line in text.splitlines():
        sec = re.match(r"//\s*-+\s*(\d+)\s+(.+)$", line)
        if sec:
            folder = f"{int(sec.group(1)):02d} {sec.group(2).strip()}"
            continue
        m = re.match(r"MEASURE '_Measures'\[(.+?)\]\s*=", line)
        if m:
            rows.append({"Display folder": folder, "Measure": m.group(1), "Format string": measure_format(m.group(1))})
    return pd.DataFrame(rows)


def check_names(path: Path = DAX) -> list[str]:
    """Names of the EVALUATE check rows, in order."""
    tail = path.read_text(encoding="utf-8").split("\nEVALUATE", 1)[1]
    return re.findall(r'"Check measure", "([^"]+)"', tail)


# ---------------------------------------------------------------- formatting
def shown_as(unit: str, v: float) -> str:
    if unit == "pct":
        return f"{v:.1f}%"
    if unit == "inr":
        return inr(v) if abs(v) >= 100 else ("−" if v < 0 else "") + f"₹{abs(v):,.2f}"
    if unit == "count":
        return f"{v:,.0f}"
    return f"{v:,.1f}"


def checks_table(a: pd.DataFrame) -> str:
    out = a.copy()
    out["SQL value"] = out["SQL value"].astype(float)
    out["Power BI shows"] = [shown_as(u, v) for u, v in zip(out["Unit"], out["SQL value"])]
    out = out[["#", "Area", "Check measure", "SQL value", "Power BI shows"]]
    return table(out, {"SQL value": "{:,.2f}"})


def headline(a: pd.DataFrame, b: pd.DataFrame) -> str:
    v = dict(zip(a["Check measure"], a["SQL value"].astype(float)))
    best = b.loc[b["Scenario"] != "Status quo"].sort_values("Jobs lost to no partner").iloc[0]
    return "\n".join([
        f"- The Power BI layer reproduces the warehouse: **{v['Demand']:,.0f}** jobs, ride completion "
        f"**{v['Ride Completion %']:.1f}%**, food **{v['Food Delivered %']:.1f}%**, partners idle **{v['Idle %']:.1f}%** "
        f"of online time.",
        f"- Policy results match Phases 10–11: profit repositioning changes lost jobs by "
        f"**{v['Lost Jobs Change vs SQ % (profit)']:+.1f}%** and contribution by "
        f"**{v['Contribution Change vs SQ % (profit)']:+.2f}%**; a completed job must be worth more than "
        f"**₹{v['Break-even Job Value (service vs profit)']:.1f}** for the service policy to win.",
        f"- The fewest lost jobs come from **{best['Scenario']}** ({best['Jobs lost to no partner']:,} lost), "
        f"at {inr(best['Net vs profit policy per day (INR)'])} a day against the profit policy.",
        f"- Incentive break-even rises from **₹{v['Break-even Bonus (normal day)']:.1f}** per partner-hour on a normal "
        f"day to **₹{v['Break-even Bonus (festival evening)']:.1f}** on festival evenings.",
    ])


def row_counts(conn) -> pd.DataFrame:
    rows = []
    for name, (grain, role) in TABLES.items():
        n = conn.cursor().execute(f"SELECT COUNT_BIG(*) FROM pbi.{name}").fetchone()[0]
        rows.append({"Power BI table": name, "Source view": f"pbi.{name}", "Grain": grain, "Rows": int(n),
                     "Role": role})
    return pd.DataFrame(rows)


def main() -> None:
    from pulse.warehouse.load import connect, load_settings, run_query_all, run_script

    topo = write_zone_topojson(MAP)
    print(f"Map: {MAP.relative_to(ROOT)} ({len(topo['objects']['zones']['geometries'])} zones)")

    with connect(load_settings()) as conn:
        run_script(conn, SQL / "00_create_powerbi_views.sql")
        print("Views: pbi schema created")
        a, b = [clean(f) for f in run_query_all(conn, SQL / "01_dashboard_checks.sql")]
        counts = row_counts(conn)

    if list(a["Check measure"]) != check_names():
        raise RuntimeError("Check rows in 01_dashboard_checks.sql and PULSE_measures.dax differ")

    fill_block(MODEL_DOC, "rowcounts", table(counts, {"Rows": "{:,}"}))
    fill_block(DAX_DOC, "catalogue", table(measure_catalogue(), {}), stamp=False)
    fill_block(DAX_DOC, "A", checks_table(a))
    fill_block(DAX_DOC, "B", md(b))
    fill_block(DAX_DOC, "headline", headline(a, b))
    print(f"Documents filled: {MODEL_DOC.name}, {DAX_DOC.name}  ({counts['Rows'].sum():,} rows in the model)")


if __name__ == "__main__":
    main()
