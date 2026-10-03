"""Phase 6: regenerate every Hyperlocal Demand Intelligence document and chart.

Runs each analysis in 06_Demand_Intelligence/sql/, writes its result sets and a
generated headline into the matching document, and draws the maps and
heatmaps from the zone x hour matrix (sql/06_zone_hour_matrix.sql).

Needs PULSE_DW with the Phase 5 KPI views (python scripts/report_phase5.py)
and the zone polygons (python scripts/build_zone_geometry.py).

Usage:
    python scripts/report_phase6.py
"""
import importlib.util
from pathlib import Path

import pandas as pd

from pulse.geo.plots import choropleth_panels, zone_hour_heatmap
from pulse.geo.zones import load_zone_polygons
from pulse.reporting import fill_block, inr, table
from pulse.warehouse.load import connect, load_settings, run_query_all

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "06_Demand_Intelligence"
SQL = PHASE / "sql"
CHARTS = PHASE / "images" / "charts"

# Reuse Phase 5's Decimal cleaning and column formatting.
_spec = importlib.util.spec_from_file_location("report_phase5", ROOT / "scripts" / "report_phase5.py")
_p5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p5)
clean, md = _p5.clean, _p5.md

ANALYSES = {
    "01_zone_demand_profile": "01_Zone_Demand_Profile.md",
    "02_time_of_day_patterns": "02_Time_of_Day_Patterns.md",
    "03_demand_pressure": "03_Demand_Pressure.md",
    "04_restaurant_density": "04_Restaurant_Density.md",
    "05_demand_variability": "05_Demand_Growth_and_Variability.md",
}


# ---------------- generated headline summaries ----------------
def h_profile(a, b):
    top = a.iloc[0]
    rides = a.sort_values("Rides per weekday", ascending=False).iloc[0]
    food = a.sort_values("Orders per weekday", ascending=False).iloc[0]
    by_type = a.groupby("Zone type")["Weekend to weekday ratio"].mean()
    peak = b.iloc[0]
    return "\n".join([
        f"- The busiest zone is **{top['Zone']} ({top['Zone name']})** with "
        f"**{top['Share of weekday demand %']:.1f}%** of weekday demand.",
        f"- Most ride requests: **{rides['Zone']}** (**{rides['Rides per weekday']:,.0f}** per weekday); "
        f"most food orders: **{food['Zone']}** (**{food['Orders per weekday']:,.0f}** per weekday).",
        f"- Weekends change demand most in **{by_type.idxmin()}** zones (weekend ÷ weekday "
        f"**{by_type.min():.2f}**) and **{by_type.idxmax()}** zones (**{by_type.max():.2f}**).",
        f"- The single busiest weekday zone-hour is **{peak['Zone']} at {int(peak['Hour']):02d}:00** with "
        f"**{peak['Jobs per day']:,.0f}** jobs per day.",
    ])


def h_time(a, b):
    def peak(df, col):
        r = df.loc[df[col].idxmax()]
        return f"{int(r['Hour']):02d}:00"
    cols = [c for c in a.columns if c != "Hour"]
    ride_peaks = ", ".join(f"{c} {peak(a, c)}" for c in cols)
    food_peaks = ", ".join(f"{c} {peak(b, c)}" for c in cols)
    return "\n".join([
        f"- Weekday ride peak by zone type: {ride_peaks}.",
        f"- Weekday food peak by zone type: {food_peaks}.",
    ])


def h_pressure(a, b):
    worst = a.iloc[0]
    top3 = b.head(3)
    share3 = top3["Share of city losses %"].sum()
    return "\n".join([
        f"- The worst weekday pressure point is **{worst['Zone']} {worst['Service'].lower()} at "
        f"{int(worst['Hour']):02d}:00**: **{worst['Lost per day']:.1f}** jobs lost per day "
        f"(**{worst['Lost %']:.1f}%** of its demand).",
        f"- Three zones — **{', '.join(top3['Zone'])}** — account for **{share3:.1f}%** of all jobs lost "
        f"to no partner.",
        f"- **{(a['Service'] == 'Mobility').sum()} of the top {len(a)}** pressure points are ride requests.",
    ])


def h_restaurants(a, b):
    dense = a.iloc[0]
    top = b.iloc[0]
    half = b[b.iloc[:, 0] <= 5]["Share of orders %"].sum()
    return "\n".join([
        f"- **{dense['Zone']}** has the most restaurants (**{dense['Restaurants']:,}**).",
        f"- The busiest 10% of restaurants take **{top['Share of orders %']:.1f}%** of all orders; the "
        f"busiest half take **{half:.1f}%**.",
        f"- Order-to-door time ranges from **{a['Avg order-to-door (min)'].min():.1f}** to "
        f"**{a['Avg order-to-door (min)'].max():.1f}** minutes across zones.",
    ])


def h_variability(a, b):
    wow_r = a["Rides WoW %"].dropna().abs()
    wow_f = a["Food WoW %"].dropna().abs()
    return "\n".join([
        f"- Week-over-week change stays within **±{wow_r.max():.1f}%** for rides and "
        f"**±{wow_f.max():.1f}%** for food: no structural growth trend in the period.",
        f"- Rain lifts weekday food orders by **{b['Rain effect on food %'].min():.1f}–"
        f"{b['Rain effect on food %'].max():.1f}%** and rides by **{b['Rain effect on rides %'].min():.1f}–"
        f"{b['Rain effect on rides %'].max():.1f}%** across zone types.",
    ])


HEADLINES = {"01_zone_demand_profile": h_profile, "02_time_of_day_patterns": h_time,
             "03_demand_pressure": h_pressure, "04_restaurant_density": h_restaurants,
             "05_demand_variability": h_variability}


def draw_charts(matrix: pd.DataFrame) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    zones, outline = load_zone_polygons()
    per_zone = matrix.groupby("zone_code")[["rides_per_day", "orders_per_day", "lost_per_day"]].sum()
    choropleth_panels(
        zones, outline,
        {"Ride requests": per_zone["rides_per_day"], "Food orders": per_zone["orders_per_day"],
         "Jobs lost (no partner)": per_zone["lost_per_day"]},
        "Demand Map of Bengaluru — weekday demand per zone", CHARTS / "demand_map.png",
        {"Ride requests": "Blues", "Food orders": "Oranges", "Jobs lost (no partner)": "Reds"})
    zone_hour_heatmap(matrix, "rides_per_day", "Ride requests per weekday — zone × hour",
                      CHARTS / "heatmap_rides.png", "Blues")
    zone_hour_heatmap(matrix, "orders_per_day", "Food orders per weekday — zone × hour",
                      CHARTS / "heatmap_food.png", "Oranges")
    zone_hour_heatmap(matrix, "lost_per_day", "Jobs lost to no partner per weekday — zone × hour",
                      CHARTS / "heatmap_lost.png", "Reds")


def main() -> None:
    with connect(load_settings()) as conn:
        for stem, doc in ANALYSES.items():
            frames = [clean(f) for f in run_query_all(conn, SQL / f"{stem}.sql")]
            path = PHASE / doc
            for letter, df in zip("ABCDEFG", frames):
                fill_block(path, letter, md(df))
            fill_block(path, "headline", HEADLINES[stem](*frames))
            print(f"Updated {path.relative_to(ROOT)}  ({len(frames)} result sets)")
        matrix = clean(run_query_all(conn, SQL / "06_zone_hour_matrix.sql")[0])
    draw_charts(matrix)
    print(f"Charts written to {CHARTS.relative_to(ROOT)} (demand map + 3 heatmaps)")


if __name__ == "__main__":
    main()
