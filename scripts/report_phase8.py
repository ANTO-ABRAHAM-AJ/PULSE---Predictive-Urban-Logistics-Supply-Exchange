"""Phase 8: build the Marketplace Pressure Index and regenerate every document.

1. Rebuilds dw.Agg_Pressure_ZoneHour (sql/00_build_pressure_table.sql).
2. Runs each analysis and writes its result sets and headline into the
   matching document.
3. Draws the Pressure Map, the MPI heatmap, the calibration chart and the
   lost-jobs-by-shortage-type chart.

Needs PULSE_DW with the Phase 5 KPI views and the zone polygons.

Usage:
    python scripts/report_phase8.py
"""
import importlib.util
from pathlib import Path

import pandas as pd

from pulse.geo.plots import bar_chart, choropleth_panels, stacked_bars, zone_hour_heatmap
from pulse.geo.zones import load_zone_polygons
from pulse.reporting import fill_block
from pulse.warehouse.load import connect, load_settings, run_query_all, run_script

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "08_Supply_Demand_Imbalance"
SQL = PHASE / "sql"
CHARTS = PHASE / "images" / "charts"

_spec = importlib.util.spec_from_file_location("report_phase5", ROOT / "scripts" / "report_phase5.py")
_p5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p5)
clean, md = _p5.clean, _p5.md

ANALYSES = {
    "01_pressure_index_validation": "01_Pressure_Index_Validation.md",
    "02_pressure_by_zone_hour": "02_Pressure_by_Zone_and_Hour.md",
    "03_shortage_types": "03_Shortage_Types.md",
    "04_service_pressure": "04_Service_Pressure.md",
    "05_rain_pressure": "05_Rain_and_Pressure.md",
}


# ---------------- generated headline summaries ----------------
def h_validation(a, b):
    by = a.set_index("Pressure state")
    under = by.loc["Under-supplied"] if "Under-supplied" in by.index else by.iloc[0]
    low, high = b.iloc[0], b[b["MPI band"] != "No supply present"].iloc[-1]
    return "\n".join([
        f"- Under-supplied zone-hours are **{under['Share of zone-hours %']:.1f}%** of all zone-hours but hold "
        f"**{under['Share of lost jobs %']:.1f}%** of all lost jobs.",
        f"- The loss rate rises from **{low['Loss rate %']:.1f}%** at MPI {low['MPI band']} to "
        f"**{high['Loss rate %']:.1f}%** at MPI {high['MPI band']}: the index predicts failure.",
    ])


def h_zone_hour(a, b):
    top = a.iloc[0]
    peak = b.loc[b["Zones under-supplied"].idxmax()]
    return "\n".join([
        f"- **{top['Zone']}** is under-supplied in **{top['Under-supplied hours %']:.1f}%** of its active "
        f"weekday hours, the most of any zone.",
        f"- At **{int(peak['Hour']):02d}:00** on weekdays, **{peak['Zones under-supplied']:.1f}** of 24 zones are "
        f"under-supplied on an average day (city MPI **{peak['City MPI']:.2f}**).",
    ])


def h_shortage(a, b):
    by = a.set_index("Shortage type")
    rep = by.loc["Reposition ahead"]["Share of lost jobs %"] if "Reposition ahead" in by.index else 0
    city = by.loc["Citywide shortage"]["Share of lost jobs %"] if "Citywide shortage" in by.index else 0
    fix = by.loc["Fix now"]["Share of lost jobs %"] if "Fix now" in by.index else 0
    top = b.iloc[0]
    return "\n".join([
        f"- **{rep:.1f}%** of lost jobs happen where supply exists elsewhere in the city but not within reach — "
        f"fixable only by **repositioning ahead** of demand (Phase 10).",
        f"- **{city:.1f}%** happen when the whole city is short — a **citywide shortage** that needs more "
        f"partners online (Phase 11).",
        f"- Only **{fix:.1f}%** could be fixed by better same-hour dispatch.",
        f"- **{top['Zone']}** loses the most jobs (**{top['Lost per day: total']:.1f}** per day).",
    ])


def h_service(a, b):
    m = a.loc[a["Mobility MPI"].idxmax()]
    f = a.loc[a["Food MPI"].idxmax()]
    return "\n".join([
        f"- City-level mobility pressure peaks at **{int(m['Hour']):02d}:00** (MPI **{m['Mobility MPI']:.2f}**); "
        f"food pressure peaks at **{int(f['Hour']):02d}:00** (MPI **{f['Food MPI']:.2f}**).",
        f"- **{b.iloc[0]['Zone type']}** zones are short of mobility supply in "
        f"**{b.iloc[0]['Mobility short hours %']:.1f}%** of their weekday ride hours.",
    ])


def h_rain(a, b):
    worst = a.assign(d=a["Lost per rain weekday"] - a["Lost per dry weekday"]).sort_values("d").iloc[-1]
    return "\n".join([
        f"- Rain raises pressure most in the **{worst['Time band'][2:]}** band: lost jobs go from "
        f"**{worst['Lost per dry weekday']:.1f}** to **{worst['Lost per rain weekday']:.1f}** per weekday.",
        f"- Total weekday losses rise from **{a['Lost per dry weekday'].sum():,.0f}** on dry days to "
        f"**{a['Lost per rain weekday'].sum():,.0f}** on rain days.",
    ])


HEADLINES = {"01_pressure_index_validation": h_validation, "02_pressure_by_zone_hour": h_zone_hour,
             "03_shortage_types": h_shortage, "04_service_pressure": h_service,
             "05_rain_pressure": h_rain}


def draw_charts(matrix: pd.DataFrame, zone_table: pd.DataFrame, calibration: pd.DataFrame) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    zones, outline = load_zone_polygons()
    zt = zone_table.set_index("Zone")
    choropleth_panels(
        zones, outline,
        {"Under-supplied weekday hours": zt["Under-supplied hours %"],
         "Evening pressure (MPI 17–20)": zt["MPI 17-20"],
         "Jobs lost needing repositioning": matrix.groupby("zone_code")["lost_reposition_ahead"].sum()},
        "Pressure Map of Bengaluru — where supply falls short of demand",
        CHARTS / "pressure_map.png",
        {"Under-supplied weekday hours": "Reds", "Evening pressure (MPI 17–20)": "OrRd",
         "Jobs lost needing repositioning": "Purples"},
        {"Under-supplied weekday hours": "% of active weekday hours",
         "Evening pressure (MPI 17–20)": "work ÷ supply (1 = balanced)",
         "Jobs lost needing repositioning": "lost jobs per weekday"})
    zone_hour_heatmap(matrix, "mpi", "Marketplace Pressure Index — zone × hour (weekdays)",
                      CHARTS / "heatmap_mpi.png", "RdYlGn_r", center=1.0, vmax=3.0,
                      label="MPI (green < 1 < red; capped at 3)")
    by_hour = matrix.groupby("hour_of_day")[["lost_reposition_ahead", "lost_citywide", "lost_fix_now"]].sum()
    by_hour = by_hour.reset_index().rename(columns={
        "hour_of_day": "Hour of day (weekdays)", "lost_reposition_ahead": "Reposition ahead",
        "lost_citywide": "Citywide shortage", "lost_fix_now": "Fix now"})
    stacked_bars(by_hour, "Hour of day (weekdays)", ["Reposition ahead", "Citywide shortage", "Fix now"],
                 "Lost jobs by shortage type — what kind of fix each needs", CHARTS / "lost_by_shortage_type.png",
                 ["#6a3d9a", "#e31a1c", "#33a02c"], "lost jobs per weekday")
    cal = calibration[calibration["MPI band"] != "No supply present"]
    bar_chart(cal["MPI band"].tolist(), cal["Loss rate %"].astype(float).tolist(),
              "The Pressure Index predicts failure — loss rate by MPI band",
              CHARTS / "mpi_calibration.png", "jobs lost to no partner (%)")


def main() -> None:
    with connect(load_settings()) as conn:
        run_script(conn, SQL / "00_build_pressure_table.sql")
        print("dw.Agg_Pressure_ZoneHour rebuilt")
        results = {}
        for stem, doc in ANALYSES.items():
            frames = [clean(f) for f in run_query_all(conn, SQL / f"{stem}.sql")]
            results[stem] = frames
            path = PHASE / doc
            for letter, df in zip("ABCDEFG", frames):
                fill_block(path, letter, md(df))
            fill_block(path, "headline", HEADLINES[stem](*frames))
            print(f"Updated {path.relative_to(ROOT)}  ({len(frames)} result sets)")
        matrix = clean(run_query_all(conn, SQL / "06_pressure_matrix.sql")[0])
    draw_charts(matrix, results["02_pressure_by_zone_hour"][0], results["01_pressure_index_validation"][1])
    print(f"Charts written to {CHARTS.relative_to(ROOT)} (pressure map, MPI heatmap, calibration, shortage types)")


if __name__ == "__main__":
    main()
