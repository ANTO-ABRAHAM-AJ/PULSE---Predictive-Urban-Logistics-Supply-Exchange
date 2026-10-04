"""Phase 10: city-scale optimization — simulate, store and report.

1. Reads optimizer economics (history weeks) and the Phase 9 forecast from PULSE_DW.
2. Replays the 4 holdout weeks under the status quo and three optimizer
   scenarios with common random numbers (config/bengaluru/policy.yaml).
3. Writes dw.Agg_Policy_ZoneHour, dw.Fact_Repositioning, dw.Fact_Supply_Allocation
   and dw.Agg_Supply_Value.
4. Fills the five findings documents and draws the charts.

Run scripts/tune_policy.py first (once) to fill the validation table.
Takes a few minutes.

Usage:
    python scripts/report_phase10.py
"""
import importlib.util
from datetime import datetime
from pathlib import Path

import pandas as pd

from pulse.geo.plots import flow_map, line_panels, scatter_points
from pulse.geo.zones import load_zone_polygons
from pulse.optimization.city import (SCENARIO_NAMES, comparison, load_policy, load_simulation_inputs,
                                     run_scenarios, uplift_ranges, zone_hour_table)
from pulse.reporting import fill_block, table
from pulse.warehouse.load import connect, insert_table, load_settings, run_query_all, run_script

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "10_Optimization"
SQL = PHASE / "sql"
CHARTS = PHASE / "images" / "charts"

_spec = importlib.util.spec_from_file_location("report_phase5", ROOT / "scripts" / "report_phase5.py")
_p5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p5)
clean, md = _p5.clean, _p5.md

DOCS = {"01_policy_comparison": "02_Policy_Comparison.md",
        "02_where_gains_come_from": "03_Where_Gains_Come_From.md",
        "03_repositioning_activity": "04_Repositioning_Activity.md",
        "04_marginal_value_of_supply": "05_Marginal_Value_of_Supply.md"}


def query(conn, sql: str) -> pd.DataFrame:
    cur = conn.cursor().execute(sql)
    return pd.DataFrame([tuple(r) for r in cur.fetchall()], columns=[c[0] for c in cur.description])


def rupees(x: float) -> str:
    return f"−₹{abs(x):,.0f}" if x < 0 else f"₹{x:,.0f}"


def time_key(dates: pd.Series, hours: pd.Series) -> pd.Series:
    return (pd.to_datetime(dates).dt.strftime("%Y%m%d").astype(int) * 100 + hours.astype(int)).astype(int)


def store(conn, runs: dict, keys: dict) -> dict:
    run_ts = datetime.now().replace(microsecond=0)
    counts = {}
    agg = pd.concat([zone_hour_table(code, r, keys) for code, r in runs.items()], ignore_index=True)
    insert_table(conn, "Agg_Policy_ZoneHour", agg)
    counts["Agg_Policy_ZoneHour"] = len(agg)

    moves = pd.concat([r.moves.assign(scenario_code=c) for c, r in runs.items() if len(r.moves)],
                      ignore_index=True)
    if len(moves):
        insert_table(conn, "Fact_Repositioning", pd.DataFrame({
            "repositioning_key": range(1, len(moves) + 1), "scenario_code": moves["scenario_code"],
            "time_key": time_key(moves["date"], moves["hour"]),
            "driver_key": moves["partner_id"].map(keys["driver"]).astype(int),
            "origin_zone_key": moves["from_zone"].map(keys["zone"]).astype(int),
            "dest_zone_key": moves["to_zone"].map(keys["zone"]).astype(int),
            "reposition_km": moves["km"].round(2), "reposition_minutes": moves["minutes"].round(2),
            "reposition_cost": moves["cost"].round(2)}))
    counts["Fact_Repositioning"] = len(moves)

    plans = pd.concat([pd.DataFrame(r.plans).assign(scenario_code=c) for c, r in runs.items() if r.plans],
                      ignore_index=True)
    if len(plans):
        insert_table(conn, "Fact_Supply_Allocation", pd.DataFrame({
            "allocation_key": range(1, len(plans) + 1), "scenario_code": plans["scenario_code"],
            "run_ts": run_ts, "time_key": time_key(plans["date"], plans["hour"]),
            "origin_zone_key": plans["from"].map(keys["zone"]).astype(int),
            "dest_zone_key": plans["to"].map(keys["zone"]).astype(int),
            "vehicle_key": plans["partner_type"].map(keys["vehicle"]).astype(int),
            "service_key": plans["service"].map(keys["service"]).astype(int),
            "partners": plans["partners"].round(2), "reposition_cost": plans["cost"].round(2)}))
    counts["Fact_Supply_Allocation"] = len(plans)

    duals = pd.concat([pd.DataFrame(r.duals).assign(scenario_code=c) for c, r in runs.items() if r.duals],
                      ignore_index=True)
    if len(duals):
        insert_table(conn, "Agg_Supply_Value", pd.DataFrame({
            "scenario_code": duals["scenario_code"], "time_key": time_key(duals["date"], duals["hour"]),
            "zone_key": duals["zone_id"].map(keys["zone"]).astype(int),
            "vehicle_key": duals["partner_type"].map(keys["vehicle"]).astype(int),
            "shadow_price": duals["dual"].round(2)}))
    counts["Agg_Supply_Value"] = len(duals)
    return counts


# ---------------- headlines ----------------
def h_comparison(comp: pd.DataFrame, ranges: pd.DataFrame) -> str:
    c, r = comp.set_index("Scenario"), ranges.set_index("Scenario")
    p, s = SCENARIO_NAMES["optimizer_profit"], SCENARIO_NAMES["optimizer_service"]
    pf = SCENARIO_NAMES["optimizer_perfect_forecast"]
    extra_jobs = r.loc[s, "Extra completed jobs per day"] - r.loc[p, "Extra completed jobs per day"]
    extra_cost = r.loc[p, "Contribution uplift per day (INR)"] - r.loc[s, "Contribution uplift per day (INR)"]
    lines = [
        f"- The **profit policy** cuts jobs lost to no partner by **{-c.loc[p, 'Lost jobs change %']:.1f}%** "
        f"({r.loc[p, 'Extra completed jobs per day']:.0f} more completed jobs per day) and changes contribution by "
        f"**{c.loc[p, 'Change vs status quo %']:+.2f}%** — {rupees(r.loc[p, 'Contribution uplift per day (INR)'])} per "
        f"day, 95% range {rupees(r.loc[p, '95% range low (INR)'])} to {rupees(r.loc[p, '95% range high (INR)'])}.",
        f"- The **service policy** cuts lost jobs by **{-c.loc[s, 'Lost jobs change %']:.1f}%** at a contribution "
        f"change of **{c.loc[s, 'Change vs status quo %']:+.2f}%**.",
        f"- Choosing service over profit buys about **{extra_jobs:.0f}** more completed jobs per day for about "
        f"**₹{extra_cost:,.0f}** per day: worth it if a failed job costs more than about "
        f"**₹{extra_cost / max(extra_jobs, 1e-9):,.0f}** in future business.",
        f"- With a **perfect** forecast the profit policy would cut lost jobs by "
        f"{-c.loc[pf, 'Lost jobs change %']:.1f}% (vs {-c.loc[p, 'Lost jobs change %']:.1f}%): forecast accuracy is "
        f"not the limiting factor.",
    ]
    return "\n".join(lines)


def h_gains(a: pd.DataFrame, b: pd.DataFrame) -> str:
    top = a.iloc[0]
    best = a[a["Lost per day: status quo"] >= 5].sort_values("Recovered by profit policy %", ascending=False).iloc[0]
    return "\n".join([
        f"- The zone losing the most jobs, **{top['Zone']}**, goes from **{top['Lost per day: status quo']:.1f}** to "
        f"**{top['Lost per day: profit policy']:.1f}** lost per day under the profit policy "
        f"(**{top['Recovered by profit policy %']:.1f}%** recovered).",
        f"- Among zones losing at least 5 jobs a day, **{best['Zone']}** gains most "
        f"(**{best['Recovered by profit policy %']:.1f}%** recovered).",
    ])


def h_moves(a: pd.DataFrame, b: pd.DataFrame) -> str:
    top = a.iloc[0]
    peak = b.loc[b["Moves per day: profit"].idxmax()]
    return "\n".join([
        f"- The busiest corridor is **{top['Corridor']}** ({top['Zone types']}): **{top['Moves per day']:.1f}** moves "
        f"per day, **{top['Avg move km']:.1f} km** on average.",
        f"- Moves peak at **{int(peak['Hour']):02d}:00** with **{peak['Moves per day: profit']:.1f}** per day under "
        f"the profit policy.",
    ])


def h_value(a: pd.DataFrame, b: pd.DataFrame) -> str:
    top = a.iloc[0]
    zt = b.iloc[0]
    return "\n".join([
        f"- One more two-wheeler is worth most in **{top['Zone']} at {int(top['Hour']):02d}:00** on weekdays: "
        f"**₹{top['Avg value of one more two-wheeler (INR)']:.1f}** for that hour on average.",
        f"- **{zt['Zone']}** has the highest average value per two-wheeler-hour "
        f"(**₹{zt['Two-wheeler: avg value per hour (INR)']:.1f}**) — a first candidate for Phase 11 incentives.",
    ])


HEADLINES = {"02_where_gains_come_from": h_gains, "03_repositioning_activity": h_moves,
             "04_marginal_value_of_supply": h_value}


def draw_charts(runs: dict, gains_by_hour: pd.DataFrame, comp: pd.DataFrame) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    line_panels([("Jobs lost to no partner per weekday, by hour (holdout weeks)", gains_by_hour, "Hour",
                  ["Lost: status quo", "Lost: profit policy", "Lost: service policy"])],
                "Where the optimizer recovers demand", CHARTS / "lost_by_hour.png", "lost jobs per weekday",
                {"Lost: status quo": {"color": "black"}, "Lost: profit policy": {"color": "#1b9e77"},
                 "Lost: service policy": {"color": "#d95f02"}}, xlabel="hour of day")
    moves = runs["optimizer_profit"].moves
    if len(moves):
        days = runs["optimizer_profit"].jobs["date"].nunique()
        flows = (moves.groupby(["from_zone", "to_zone"]).size() / days).rename("value").reset_index()
        zones, outline = load_zone_polygons()
        flow_map(zones, outline, flows, "Repositioning corridors — profit policy (moves per day)",
                 CHARTS / "repositioning_flows.png")
    grid_file = PHASE / "tuning_results.csv"
    if grid_file.exists():
        grid = pd.read_csv(grid_file)
        grid["label"] = grid.apply(lambda r: f"₹{r['Penalty (INR)']:.0f}/{r['Max move km']:.0f}km/{r['Look-ahead']:.1f}", axis=1)
        grid["Lost jobs recovered %"] = -grid["Lost jobs change %"]
        hold = comp[comp["Scenario"] != SCENARIO_NAMES["status_quo"]].assign(
            **{"Lost jobs recovered %": lambda d: -d["Lost jobs change %"],
               "Contribution change %": lambda d: d["Change vs status quo %"], "label": lambda d: d["Scenario"]})
        scatter_points(grid, "Lost jobs recovered %", "Contribution change %", "label",
                       "Trade-off: service recovered vs contribution", CHARTS / "tradeoff_frontier.png", hold)


def main() -> None:
    policy = load_policy()
    inp = load_simulation_inputs()
    holdout = list(inp["calendar"].loc[inp["calendar"]["split"] == "holdout", "date"])
    with connect(load_settings()) as conn:
        run_script(conn, SQL / "00_create_policy_tables.sql")
        econ = clean(run_query_all(conn, SQL / "05_economics_inputs.sql")[0])
        contribution = dict(zip(econ["service_code"], econ["Contribution per job (INR)"].astype(float)))
        fc = clean(run_query_all(conn, SQL / "06_forecast_input.sql")[0])
        forecast = dict(zip(zip(pd.to_datetime(fc["date_value"]), fc["hour_of_day"].astype(int), fc["zone_code"],
                                fc["service_code"]), fc["forecast_demand"].astype(float)))
        keys = {"zone": dict(query(conn, "SELECT zone_code, zone_key FROM dw.Dim_Zone").values),
                "service": dict(query(conn, "SELECT service_code, service_key FROM dw.Dim_Service").values),
                "vehicle": dict(query(conn, "SELECT vehicle_code, vehicle_key FROM dw.Dim_Vehicle").values),
                "driver": dict(query(conn, "SELECT partner_code, driver_key FROM dw.Dim_Driver").values)}
        print(f"Economics: ₹{contribution['mobility']:.2f} per ride, ₹{contribution['food']:.2f} per order; "
              f"{len(forecast):,} forecast values read")

        runs = run_scenarios(inp, holdout, forecast, contribution, policy)
        counts = store(conn, runs, keys)
        print("Stored: " + ", ".join(f"{k} {v:,}" for k, v in counts.items()))

        results = {stem: [clean(f) for f in run_query_all(conn, SQL / f"{stem}.sql")] for stem in DOCS}

    comp, ranges = comparison(runs), uplift_ranges(runs)
    design = PHASE / "01_City_Optimizer_Design.md"
    fill_block(design, "economics", md(econ.drop(columns="service_code")))
    settings = pd.DataFrame([
        {"Setting": "Jobs per partner-hour (rides / food)", "Value": f"{policy['jobs_per_partner_per_hour']['mobility']} / {policy['jobs_per_partner_per_hour']['food']}"},
        {"Setting": "Repositioning cost per km (two-wheeler / cab)", "Value": f"₹{policy['reposition_cost_per_km']['two_wheeler']} / ₹{policy['reposition_cost_per_km']['four_wheeler']}"},
        {"Setting": "Remote-service efficiency (rides / food)", "Value": f"{policy['remote_efficiency']['mobility']} / {policy['remote_efficiency']['food']}"},
        {"Setting": "Look-ahead weight on next hour", "Value": str(policy["lookahead"])},
        {"Setting": "Maximum move", "Value": f"{policy['max_move_km']} km"},
        {"Setting": "Scenarios (penalty per lost job)", "Value": "; ".join(f"{k}: ₹{v['penalty']}" for k, v in policy["scenarios"].items())}])
    fill_block(design, "settings", table(settings, {}))

    doc = PHASE / "02_Policy_Comparison.md"
    pct = {c: "{:+.2f}" if "change" in c.lower() else "{:.1f}" for c in comp.columns if "%" in c}
    fill_block(doc, "python", table(comp, {**pct, "Contribution (INR)": "₹{:,.0f}", "Jobs lost to no partner": "{:,}",
                                          "Moves per day": "{:.0f}", "Repositioning cost (INR)": "₹{:,.0f}"}))
    fill_block(doc, "ranges", table(ranges, {"Contribution uplift per day (INR)": rupees,
                                             "95% range low (INR)": rupees, "95% range high (INR)": rupees,
                                             "Extra completed jobs per day": "{:.0f}"}))
    a, b = results["01_policy_comparison"]
    fill_block(doc, "A", md(a))
    fill_block(doc, "B", md(b))
    fill_block(doc, "headline", h_comparison(comp, ranges))
    for stem, docname in DOCS.items():
        if stem == "01_policy_comparison":
            continue
        a, b = results[stem]
        fill_block(PHASE / docname, "A", md(a))
        fill_block(PHASE / docname, "B", md(b))
        fill_block(PHASE / docname, "headline", HEADLINES[stem](a, b))

    draw_charts(runs, results["02_where_gains_come_from"][1], comp)
    print("Updated 5 documents in 10_Optimization and the charts in images/charts")


if __name__ == "__main__":
    main()
