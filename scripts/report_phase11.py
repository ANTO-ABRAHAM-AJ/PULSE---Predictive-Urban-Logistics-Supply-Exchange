"""Phase 11: incentive programmes and stress scenarios — simulate, store, report.

1. Chooses incentive targets from VALIDATION weekdays (shadow prices, Phase 10 policy).
2. Holdout weeks: status quo, profit policy, and profit policy + each programme.
3. Every second holdout day: each stress scenario under status quo, profit,
   service, and profit + the middle-price programme.
4. Writes dw.Agg_Scenario_Summary, dw.Fact_Incentives and the incentive rows of
   dw.Agg_Policy_ZoneHour; fills the documents and draws the charts.

Needs Phase 9 forecasts and Phase 10 results in PULSE_DW. Takes about 10 minutes.

Usage:
    python scripts/report_phase11.py
"""
import importlib.util
from pathlib import Path

import pandas as pd

from pulse.geo.plots import grouped_bars
from pulse.optimization.city import load_policy, load_simulation_inputs, zone_hour_table
from pulse.optimization.incentives import partner_hours_per_day
from pulse.optimization.phase11 import incentive_study, ladder, programmes, stress_study, validation_targets
from pulse.reporting import fill_block, table
from pulse.warehouse.load import connect, insert_table, load_settings, run_query_all, run_script

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "11_Incentive_Economics"
SQL = PHASE / "sql"
CHARTS = PHASE / "images" / "charts"
P10 = ROOT / "10_Optimization" / "sql"

_spec = importlib.util.spec_from_file_location("report_phase10", ROOT / "scripts" / "report_phase10.py")
_p10 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p10)
clean, md, query, rupees = _p10.clean, _p10.md, _p10.query, _p10.rupees

PHASE10_SERVICE = """
SELECT p.scenario_code, SUM(p.requests - p.lost_no_partner) AS not_lost, SUM(p.revenue) AS revenue,
       (SELECT ISNULL(SUM(reposition_cost), 0) FROM dw.Fact_Repositioning r WHERE r.scenario_code = p.scenario_code) AS cost
FROM dw.Agg_Policy_ZoneHour p
WHERE p.scenario_code IN ('status_quo', 'optimizer_service')
GROUP BY p.scenario_code
"""


def incentive_rows(progs: dict, dates, calendar: pd.DataFrame, keys: dict) -> pd.DataFrame:
    weekend = dict(zip(calendar["date"], calendar["is_weekend"]))
    rows = []
    for bonus, prog in progs.items():
        for w in prog:
            for d in dates:
                if weekend[d]:
                    continue
                for h in w["hours"]:
                    rows.append({"scenario_code": f"incentive_{bonus}",
                                 "time_key": int(d.strftime("%Y%m%d")) * 100 + h,
                                 "zone_key": keys["zone"][w["zone_id"]], "service_key": keys["service"]["mobility"],
                                 "driver_key": None, "incentive_type": "guaranteed_hour",
                                 "incentive_amount": round(bonus * w["partners"], 2),
                                 "extra_partner_hours": w["partners"]})
    df = pd.DataFrame(rows)
    df.insert(0, "incentive_key", range(1, len(df) + 1))
    return df


def targets_table(progs: dict) -> pd.DataFrame:
    rows = []
    for bonus, prog in progs.items():
        by_zone = {}
        for w in prog:
            by_zone[w["zone_id"]] = by_zone.get(w["zone_id"], 0) + w["partners"] * len(w["hours"])
        top = sorted(by_zone.items(), key=lambda kv: -kv[1])[:5]
        rows.append({"Bonus per partner-hour": f"₹{bonus}", "Zone-hours targeted": sum(len(w["hours"]) for w in prog),
                     "Partner-hours per weekday": partner_hours_per_day(prog),
                     "Largest targets (partner-hours)": ", ".join(f"{z} ({n})" for z, n in top)})
    return pd.DataFrame(rows)


def h_incentives(lad: pd.DataFrame, a: pd.DataFrame) -> str:
    inc = lad[lad["Lever"].str.startswith("Incentives")]
    best = inc.sort_values("Net cost per extra job (INR)").iloc[0]
    rev = a[a["Bonus per partner-hour (INR)"] > 0].copy()
    rev["per_hour"] = (rev["Revenue gain per day (INR)"] / rev["Partner-hours bought per weekday"]).astype(float)
    return "\n".join([
        f"- Every incentive programme **loses money**: each guaranteed partner-hour brings back only "
        f"₹{rev['per_hour'].min():.0f}–₹{rev['per_hour'].max():.0f} of revenue, against a bonus of "
        f"₹{int(rev['Bonus per partner-hour (INR)'].min())}–₹{int(rev['Bonus per partner-hour (INR)'].max())}.",
        f"- They do serve many more customers: the cheapest rung, **{best['Lever'].lower()}**, serves "
        f"**{best['Extra jobs served per day']:.0f}** more jobs per day at about **₹{best['Net cost per extra job (INR)']:.0f}** per job.",
        "- Cost-per-job ladder: profit repositioning (free) → service repositioning → incentives. Use incentives "
        "only if a lost customer is worth more than the incentive's cost per job.",
    ])


def h_stress(a: pd.DataFrame, b: pd.DataFrame) -> str:
    sq = a[a["Policy"] == "status_quo"].set_index("Stress case")
    worst = sq.drop(index="normal", errors="ignore")["Lost jobs vs normal status quo %"].idxmax()
    bb = b.set_index("Stress case")
    top = bb["Break-even bonus per partner-hour (INR)"].idxmax()
    return "\n".join([
        f"- The hardest stress case is **{worst.replace('_', ' ')}**: lost jobs rise "
        f"**{sq.loc[worst, 'Lost jobs vs normal status quo %']:.0f}%** above a normal day under the status quo.",
        f"- Repositioning recovers **{bb.loc['normal', 'Recovered by profit policy %']:.1f}%** of losses on a normal "
        f"day but only **{bb.drop(index='normal')['Recovered by profit policy %'].min():.1f}–"
        f"{bb.drop(index='normal')['Recovered by profit policy %'].max():.1f}%** under stress: less idle supply to move.",
        f"- Incentives are worth most under stress: break-even rises from "
        f"**₹{bb.loc['normal', 'Break-even bonus per partner-hour (INR)']:.0f}** per partner-hour on a normal day to "
        f"**₹{bb.loc[top, 'Break-even bonus per partner-hour (INR)']:.0f}** on **{top.replace('_', ' ')}** days.",
    ])


def main() -> None:
    policy = load_policy()
    inp = load_simulation_inputs()
    cal = inp["calendar"]
    holdout = list(cal.loc[cal["split"] == "holdout", "date"])
    stress_days = holdout[::2]
    with connect(load_settings()) as conn:
        run_script(conn, SQL / "00_create_tables.sql")
        econ = clean(run_query_all(conn, P10 / "05_economics_inputs.sql")[0])
        contribution = dict(zip(econ["service_code"], econ["Contribution per job (INR)"].astype(float)))
        fc = clean(run_query_all(conn, P10 / "06_forecast_input.sql")[0])
        forecast = dict(zip(zip(pd.to_datetime(fc["date_value"]), fc["hour_of_day"].astype(int), fc["zone_code"],
                                fc["service_code"]), fc["forecast_demand"].astype(float)))
        keys = {"zone": dict(query(conn, "SELECT zone_code, zone_key FROM dw.Dim_Zone").values),
                "service": dict(query(conn, "SELECT service_code, service_key FROM dw.Dim_Service").values)}
        p10 = clean(query(conn, PHASE10_SERVICE)).set_index("scenario_code")

        duals, lost, n_val = validation_targets(inp, policy, contribution)
        progs = programmes(duals, lost, n_val, policy)
        print(f"Targets chosen on {n_val} validation weekdays: "
              + ", ".join(f"₹{b}: {partner_hours_per_day(p)} partner-hours/day" for b, p in progs.items()))

        inc, runs = incentive_study(inp, holdout, forecast, policy, contribution, progs)
        mid = policy["incentives"]["bonus_levels"][len(policy["incentives"]["bonus_levels"]) // 2]
        st = stress_study(inp, stress_days, forecast, policy, contribution, progs[mid], mid)

        insert_table(conn, "Agg_Scenario_Summary", pd.concat([inc, st], ignore_index=True))
        insert_table(conn, "Fact_Incentives", incentive_rows(progs, holdout, cal, keys))
        insert_table(conn, "Agg_Policy_ZoneHour", pd.concat(
            [zone_hour_table(c, r, keys) for c, r in runs.items() if c.startswith("incentive_")], ignore_index=True))
        print("Stored: Agg_Scenario_Summary, Fact_Incentives, incentive rows of Agg_Policy_ZoneHour")

        a1, b1 = [clean(f) for f in run_query_all(conn, SQL / "01_incentive_programmes.sql")]
        a2, b2 = [clean(f) for f in run_query_all(conn, SQL / "02_stress_scenarios.sql")]

    days = len(holdout)
    service = {"extra_jobs_per_day": (p10.loc["optimizer_service", "not_lost"] - p10.loc["status_quo", "not_lost"]) / days,
               "uplift_per_day": ((p10.loc["optimizer_service", "revenue"] - p10.loc["optimizer_service", "cost"])
                                  - (p10.loc["status_quo", "revenue"] - p10.loc["status_quo", "cost"])) / days}
    lad = ladder(inc, service)

    fill_block(PHASE / "01_Incentive_Design.md", "targets", table(targets_table(progs), {}))
    doc = PHASE / "02_Incentive_Results.md"
    fill_block(doc, "A", md(a1))
    fill_block(doc, "B", md(b1))
    fill_block(doc, "ladder", table(lad, {"Extra jobs served per day": "{:.0f}", "Net cost per day (INR)": rupees,
                                         "Net cost per extra job (INR)": rupees}))
    fill_block(doc, "headline", h_incentives(lad, a1))
    doc = PHASE / "03_Stress_Scenarios.md"
    fill_block(doc, "A", md(a2))
    fill_block(doc, "B", md(b2))
    fill_block(doc, "headline", h_stress(a2, b2))

    CHARTS.mkdir(parents=True, exist_ok=True)
    grouped_bars(a2.rename(columns={"Lost jobs per day": "lost"}), "Stress case", "Policy", "lost",
                 "Jobs lost per day under stress — by policy", CHARTS / "stress_lost_jobs.png", "jobs lost per day",
                 {"status_quo": "#444444", "profit": "#1b9e77", "service": "#d95f02", "profit + incentive": "#7570b3"})
    grouped_bars(lad.assign(metric="Net cost per extra job (INR)"), "Lever", "metric", "Net cost per extra job (INR)",
                 "Cost per extra job served — the lever ladder", CHARTS / "lever_ladder.png", "INR per extra job",
                 {"Net cost per extra job (INR)": "#6a3d9a"})
    print("Updated 3 documents in 11_Incentive_Economics and 2 charts in images/charts")


if __name__ == "__main__":
    main()
