"""Phase 7: regenerate every Supply Intelligence document and chart.

Runs each analysis in 07_Supply_Intelligence/sql/, writes its result sets and
a generated headline into the matching document, and draws the Supply Map,
the supply heatmaps and the partner-time chart.

Needs PULSE_DW with the Phase 5 KPI views and the zone polygons.

Usage:
    python scripts/report_phase7.py
"""
import importlib.util
from pathlib import Path

import pandas as pd

from pulse.geo.plots import choropleth_panels, stacked_shares, zone_hour_heatmap
from pulse.geo.zones import load_zone_polygons
from pulse.reporting import fill_block
from pulse.warehouse.load import connect, load_settings, run_query_all

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "07_Supply_Intelligence"
SQL = PHASE / "sql"
CHARTS = PHASE / "images" / "charts"

_spec = importlib.util.spec_from_file_location("report_phase5", ROOT / "scripts" / "report_phase5.py")
_p5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p5)
clean, md = _p5.clean, _p5.md

ANALYSES = {
    "01_supply_profile": "01_Supply_Profile.md",
    "02_partner_time_states": "02_Partner_Time_States.md",
    "03_idle_supply": "03_Idle_Supply.md",
    "04_empty_km": "04_Empty_Kilometres.md",
    "05_service_eligibility": "05_Service_Eligibility.md",
}
STATES = ["Idle %", "To pickup %", "On trip %", "To restaurant %", "Delivering %"]


# ---------------- generated headline summaries ----------------
def h_profile(a, b):
    top = a.iloc[0]
    drift = b.set_index("Zone type")
    office = drift.loc["office"] if "office" in drift.index else drift.iloc[0]
    res = drift.loc["residential"] if "residential" in drift.index else drift.iloc[-1]
    return "\n".join([
        f"- Most partners live in **{top['Zone']}** (**{top['Partners living here']:,}**).",
        f"- Office zones are home to **{office['Partners living here %']:.1f}%** of partners but hold "
        f"**{office['Present at 09:00 %']:.1f}%** of them at 09:00 and **{office['Present at 19:00 %']:.1f}%** "
        f"at 19:00.",
        f"- Residential zones are home to **{res['Partners living here %']:.1f}%** of partners but hold only "
        f"**{res['Present at 09:00 %']:.1f}%** at 09:00, rising to **{res['Present at 19:00 %']:.1f}%** at 19:00.",
    ])


def h_states(a, b):
    online = a["Partners online"].astype(float)
    idle = (a["Idle %"] * online).sum() / online.sum()
    low = a[online >= online.median()].sort_values("Idle %").iloc[0]
    tw, fw = b.iloc[0], b.iloc[-1]
    return "\n".join([
        f"- Over a weekday, partners spend about **{idle:.0f}%** of their online time idle.",
        f"- Among the busier hours, idle time is lowest at **{int(low['Hour']):02d}:00** "
        f"(**{low['Idle %']:.1f}%**).",
        f"- **{tw['Vehicle']}s** are idle **{tw['Idle %']:.1f}%** of the time; "
        f"**{fw['Vehicle'].lower()}s** **{fw['Idle %']:.1f}%**.",
    ])


def h_idle(a, b):
    top = a.iloc[0]
    peak = b.loc[b["Jobs lost"].idxmax()]
    return "\n".join([
        f"- The largest idle pool is **{top['Zone']} at {int(top['Hour']):02d}:00**: "
        f"**{top['Idle partner-hours']:.0f}** idle partner-hours per weekday.",
        f"- At **{int(peak['Hour']):02d}:00**, the hour with the most lost jobs (**{peak['Jobs lost']:,.0f}**), "
        f"only **{peak['Idle within reach %']:.1f}%** of idle supply was within 20 minutes of a zone losing jobs.",
        f"- Across all weekday hours, **{(b['Idle within reach of a losing zone'].sum() / b['Idle partner-hours'].sum() * 100):.1f}%** "
        f"of idle partner-hours were within reach of unserved demand.",
    ])


def h_empty(a, b):
    worst = a.iloc[0]
    eta = b.loc[b["Avg ride pickup ETA (min)"].idxmax()]
    return "\n".join([
        f"- Ride pickups are longest in **{worst['Zone type']}** zones "
        f"(**{worst['Avg ride pickup km']:.2f} km** on average).",
        f"- Ride pickup ETA peaks at **{int(eta['Hour']):02d}:00** (**{eta['Avg ride pickup ETA (min)']:.1f} min**).",
        f"- Partners drive about **{b['Empty km per day'].sum():,.0f} empty km per weekday** to reach pickups.",
    ])


def h_eligibility(a, b):
    food = b.loc[b["Two-wheeler busy time on rides %"].idxmin()]
    rides = b.loc[b["Two-wheeler busy time on rides %"].idxmax()]
    return "\n".join([
        f"- Four-wheeler utilization ranges from **{b['Four-wheeler utilization %'].min():.1f}%** to "
        f"**{b['Four-wheeler utilization %'].max():.1f}%** across weekday hours; two-wheelers from "
        f"**{b['Two-wheeler utilization %'].min():.1f}%** to **{b['Two-wheeler utilization %'].max():.1f}%**.",
        f"- Two-wheelers spend the most busy time on rides at **{int(rides['Hour']):02d}:00** "
        f"(**{rides['Two-wheeler busy time on rides %']:.1f}%**) and the least at **{int(food['Hour']):02d}:00** "
        f"(**{food['Two-wheeler busy time on rides %']:.1f}%**).",
    ])


HEADLINES = {"01_supply_profile": h_profile, "02_partner_time_states": h_states,
             "03_idle_supply": h_idle, "04_empty_km": h_empty, "05_service_eligibility": h_eligibility}


def draw_charts(matrix: pd.DataFrame, living: pd.DataFrame, states: pd.DataFrame) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    zones, outline = load_zone_polygons()
    day = matrix[matrix["hour_of_day"].between(8, 21)].groupby("zone_code")["partners_online"].sum() / 14
    idle = matrix.groupby("zone_code")["idle_hours"].sum()
    choropleth_panels(
        zones, outline,
        {"Partners living here": living.set_index("zone_code")["partners_living"],
         "Avg partners present (08–21)": day,
         "Idle partner-hours": idle},
        "Supply Map of Bengaluru — where partners live, where they are, where they wait",
        CHARTS / "supply_map.png",
        {"Partners living here": "Greens", "Avg partners present (08–21)": "BuGn",
         "Idle partner-hours": "Purples"},
        {"Partners living here": "partners (home zone)",
         "Avg partners present (08–21)": "partners present per hour, weekdays",
         "Idle partner-hours": "idle partner-hours per weekday"})
    zone_hour_heatmap(matrix, "partners_online", "Partners present per weekday — zone × hour",
                      CHARTS / "heatmap_partners_present.png", "Greens")
    zone_hour_heatmap(matrix, "idle_hours", "Idle partner-hours per weekday — zone × hour",
                      CHARTS / "heatmap_idle.png", "Purples")
    zone_hour_heatmap(matrix, "utilization_pct", "Utilization % — zone × hour (weekdays)",
                      CHARTS / "heatmap_utilization.png", "YlGnBu")
    stacked_shares(states, "Hour", STATES, "How partners spend their online time — weekdays",
                   CHARTS / "partner_time_states.png",
                   ["#d9d9d9", "#9ecae1", "#3182bd", "#fdae6b", "#e6550d"])


def main() -> None:
    with connect(load_settings()) as conn:
        results = {}
        for stem, doc in ANALYSES.items():
            frames = [clean(f) for f in run_query_all(conn, SQL / f"{stem}.sql")]
            results[stem] = frames
            path = PHASE / doc
            for letter, df in zip("ABCDEFG", frames):
                fill_block(path, letter, md(df))
            fill_block(path, "headline", HEADLINES[stem](*frames))
            print(f"Updated {path.relative_to(ROOT)}  ({len(frames)} result sets)")
        matrix, living = [clean(f) for f in run_query_all(conn, SQL / "06_zone_hour_supply.sql")]
    draw_charts(matrix, living, results["02_partner_time_states"][0])
    print(f"Charts written to {CHARTS.relative_to(ROOT)} (supply map, 3 heatmaps, partner-time chart)")


if __name__ == "__main__":
    main()
