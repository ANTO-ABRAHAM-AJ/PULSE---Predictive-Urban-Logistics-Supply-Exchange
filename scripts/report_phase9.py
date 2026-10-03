"""Phase 9: demand, supply and pressure forecasts — build, store and report.

1. Reads demand, baseline-supply and pressure history from PULSE_DW.
2. Fits the models on the 12 history weeks and forecasts the 4 holdout weeks.
3. Writes the forecasts to dw.Fact_Demand_Forecast, dw.Fact_Supply_Forecast
   and dw.Fact_Pressure_Forecast (inputs to Phase 10 and Power BI).
4. Fills the four findings documents and draws the charts.

Needs PULSE_DW with the Phase 5 views and the Phase 8 pressure table.

Usage:
    python scripts/report_phase9.py
"""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd

from pulse.forecasting import bias, skill, wape
from pulse.forecasting.demand import BENCHMARK, MODELS as DEMAND_MODELS, forecast_demand
from pulse.forecasting.pressure import forecast_pressure
from pulse.forecasting.supply import MODELS as SUPPLY_MODELS, forecast_supply
from pulse.geo.plots import line_panels
from pulse.reporting import fill_block, table
from pulse.warehouse.load import connect, insert_table, load_settings, run_query_all, run_script

ROOT = Path(__file__).resolve().parents[1]
PHASE = ROOT / "09_Forecasting"
SQL = PHASE / "sql"
CHARTS = PHASE / "images" / "charts"
TRUTH = ROOT / "data" / "processed" / "_truth_demand_hourly.csv"
PRESSURE_MODEL = "GBM calendar"            # week-ahead: no weather assumed
PEAK_HOURS = [8, 9, 10, 17, 18, 19, 20]

_spec = importlib.util.spec_from_file_location("report_phase5", ROOT / "scripts" / "report_phase5.py")
_p5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_p5)
clean, md = _p5.clean, _p5.md


def prepare(df: pd.DataFrame) -> pd.DataFrame:
    df = clean(df)
    df["date_value"] = pd.to_datetime(df["date_value"])
    for c in ("is_weekend", "is_rain_day", "is_event_day"):
        if c in df:
            df[c] = df[c].astype(int)
    return df


# ---------------- Python-side result tables ----------------
def noise_floor(fc: pd.DataFrame) -> float | None:
    """WAPE of the TRUE expected demand — the error no model can beat
    (available only because the data is synthetic)."""
    if not TRUTH.exists():
        return None
    truth = pd.read_csv(TRUTH, parse_dates=["date"]).rename(columns={
        "date": "date_value", "hour": "hour_of_day", "zone_id": "zone_code", "service": "service_code"})
    m = fc.merge(truth[["date_value", "hour_of_day", "zone_code", "service_code", "expected"]],
                 on=["date_value", "hour_of_day", "zone_code", "service_code"])
    return wape(m["demand"], m["expected"]) if len(m) == len(fc) else None


def demand_tables(fc: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, float | None]:
    peak = fc[fc["hour_of_day"].isin(PEAK_HOURS) & (fc["is_weekend"] == 0)]
    bench = wape(fc["demand"], fc[BENCHMARK])
    rows = [{"Model": m, "WAPE %": wape(fc["demand"], fc[m]), "Bias %": bias(fc["demand"], fc[m]),
             "Weekday peak WAPE %": wape(peak["demand"], peak[m]),
             "Skill vs seasonal naive %": skill(wape(fc["demand"], fc[m]), bench)} for m in DEMAND_MODELS]
    floor = noise_floor(fc)
    if floor is not None:
        rows.append({"Model": "Noise floor (true expected demand)", "WAPE %": floor, "Bias %": np.nan,
                     "Weekday peak WAPE %": np.nan, "Skill vs seasonal naive %": skill(floor, bench)})
    models = pd.DataFrame(rows)
    by_service = pd.DataFrame([{"Service": s, **{m: wape(g["demand"], g[m]) for m in DEMAND_MODELS}}
                               for s, g in fc.groupby("service_code")])
    return models, by_service, floor


def supply_table(sf: pd.DataFrame) -> pd.DataFrame:
    bench = wape(sf["partners"], sf["Seasonal naive"])
    city = sf.groupby("time_key")[["partners"] + SUPPLY_MODELS].sum()
    return pd.DataFrame([{"Model": m, "WAPE % (home zone x hour x vehicle)": wape(sf["partners"], sf[m]),
                          "Bias %": bias(sf["partners"], sf[m]),
                          "WAPE % (city x hour)": wape(city["partners"], city[m]),
                          "Skill vs seasonal naive %": skill(wape(sf["partners"], sf[m]), bench)}
                         for m in SUPPLY_MODELS])


def reconcile(py: pd.DataFrame, sql: pd.DataFrame) -> str:
    """Python WAPE by service and model must equal the warehouse's (to 0.1 pp)."""
    names = {"mobility": "Mobility", "food": "Food Delivery"}
    rows = []
    for _, r in py.iterrows():
        for m in DEMAND_MODELS:
            s = sql[(sql["Service"] == names.get(r["Service"], r["Service"])) & (sql["Model"] == m)]
            sql_v = float(s["WAPE %"].iloc[0]) if len(s) else np.nan
            rows.append({"Service": names.get(r["Service"], r["Service"]), "Model": m,
                         "Python WAPE %": round(r[m], 1), "SQL WAPE %": sql_v,
                         "Match": "✅" if abs(round(r[m], 1) - sql_v) <= 0.1 else "❌"})
    return table(pd.DataFrame(rows), {"Python WAPE %": "{:.1f}", "SQL WAPE %": "{:.1f}"})


def pct(df: pd.DataFrame) -> str:
    f = {c: "{:.1f}" for c in df.columns if "%" in c}
    return table(df, f)


# ---------------- headlines ----------------
def h_demand(models: pd.DataFrame, floor: float | None) -> str:
    m = models.set_index("Model")
    best = m.loc[DEMAND_MODELS].sort_values("WAPE %").iloc[0]
    naive = m.loc[BENCHMARK, "WAPE %"]
    lines = [f"- Best model: **{best.name}** with WAPE **{best['WAPE %']:.1f}%** against "
             f"**{naive:.1f}%** for the seasonal naive benchmark (skill **{best['Skill vs seasonal naive %']:.1f}%**).",
             f"- Its bias is **{best['Bias %']:+.1f}%**: it neither over- nor under-forecasts total demand."]
    if floor is not None:
        closed = 100 * (naive - best["WAPE %"]) / (naive - floor)
        lines.append(f"- Pure randomness puts a floor of **{floor:.1f}%** under any zone-hour forecast; the best "
                     f"model closes **{closed:.0f}%** of the gap between the benchmark and that floor.")
    return "\n".join(lines)


def h_supply(st: pd.DataFrame) -> str:
    best = st.sort_values("WAPE % (home zone x hour x vehicle)").iloc[0]
    return "\n".join([
        f"- Best model: **{best['Model']}**, WAPE **{best['WAPE % (home zone x hour x vehicle)']:.1f}%** per home "
        f"zone, hour and vehicle (skill **{best['Skill vs seasonal naive %']:.1f}%** over seasonal naive).",
        f"- Summed over the city it is accurate to **{best['WAPE % (city x hour)']:.1f}%** per hour.",
    ])


def h_pressure(a: pd.DataFrame) -> str:
    by = a.set_index("Prediction")
    tp = by.loc["Predicted short", "Actually short"]
    fp = by.loc["Predicted short", "Actually not short"]
    fn = by.loc["Predicted not short", "Actually short"]
    flagged = (tp + fp) / (by["Actually short"].sum() + by["Actually not short"].sum())
    return "\n".join([
        f"- A week ahead, the forecast flags **{100 * flagged:.1f}%** of zone-hours as short; those zone-hours "
        f"contain **{by.loc['Predicted short', 'Share of lost jobs %']:.1f}%** of all jobs later lost to no partner.",
        f"- Precision **{100 * tp / (tp + fp):.1f}%** (flagged zone-hours that really were short) and recall "
        f"**{100 * tp / (tp + fn):.1f}%** (short zone-hours that were flagged).",
    ])


# ---------------- charts ----------------
def draw_charts(fc: pd.DataFrame, sf: pd.DataFrame) -> None:
    CHARTS.mkdir(parents=True, exist_ok=True)
    days = pd.Series(sorted(fc["date_value"].dt.normalize().unique()))
    mondays = days[days.dt.dayofweek == 0]
    start = mondays.iloc[1] if len(mondays) > 1 else days.iloc[0]        # second holdout Monday
    span = (fc["date_value"] >= start) & (fc["date_value"] < start + pd.Timedelta(days=7))
    panels = []
    for zone, service, label in [("WHF", "mobility", "Whitefield — ride requests"),
                                 ("KOR", "food", "Koramangala — food orders")]:
        g = fc[span & (fc["zone_code"] == zone) & (fc["service_code"] == service)].sort_values("time_key")
        if len(g):
            g = g.assign(hour_index=range(len(g))).rename(columns={"demand": "Actual"})
            panels.append((label, g, "hour_index", ["Actual", "GBM + rain", BENCHMARK]))
    if panels:
        line_panels(panels, f"Forecast vs actual — holdout week from {start:%d %b %Y}, hour by hour",
                    CHARTS / "forecast_vs_actual.png", "jobs per hour", xlabel="hours from Monday 00:00",
                    styles={"Actual": {"color": "black", "linewidth": 1.4},
                                      "GBM + rain": {"color": "#d95f02"},
                                      BENCHMARK: {"color": "#7570b3", "alpha": 0.6, "linestyle": "--"}})
    by_hour = pd.DataFrame([{"Hour": h, **{m: wape(g["demand"], g[m]) for m in DEMAND_MODELS}}
                            for h, g in fc.groupby("hour_of_day")])
    line_panels([("WAPE % by hour of day (all holdout days)", by_hour, "Hour", DEMAND_MODELS)],
                "Where forecasts are hardest", CHARTS / "wape_by_hour.png", "WAPE %", xlabel="hour of day")
    city = (sf[sf["vehicle_code"] == "two_wheeler"].groupby("time_key")[["partners", "History profile + rain"]]
            .sum().reset_index().rename(columns={"partners": "Actual"}))
    city = city.sort_values("time_key").head(24 * 14).assign(hour_index=lambda d: range(len(d)))
    line_panels([("Two-wheelers online across the city — first two holdout weeks", city, "hour_index",
                  ["Actual", "History profile + rain"])],
                "Baseline supply forecast", CHARTS / "supply_forecast.png", "partners online",
                {"Actual": {"color": "black"}, "History profile + rain": {"color": "#1b9e77"}},
                xlabel="hours from the start of the holdout period")


def main() -> None:
    with connect(load_settings()) as conn:
        run_script(conn, SQL / "00_create_forecast_tables.sql")
        demand = prepare(run_query_all(conn, SQL / "01_demand_history.sql")[0])
        supply = prepare(run_query_all(conn, SQL / "02_supply_history.sql")[0])
        pressure = prepare(run_query_all(conn, SQL / "03_pressure_history.sql")[0])
        print(f"History read: {len(demand):,} demand rows, {len(supply):,} supply rows, {len(pressure):,} pressure rows")

        fc = forecast_demand(demand)
        sf = forecast_supply(supply)
        pf = forecast_pressure(fc, pressure, PRESSURE_MODEL)
        print("Models fitted and holdout forecast")

        long = fc.melt(id_vars=["time_key", "zone_key", "service_key", "demand"], value_vars=DEMAND_MODELS,
                       var_name="model_name", value_name="forecast_demand")
        insert_table(conn, "Fact_Demand_Forecast", pd.DataFrame({
            "time_key": long["time_key"].astype(int), "zone_key": long["zone_key"].astype(int),
            "service_key": long["service_key"].astype(int), "model_name": long["model_name"],
            "forecast_demand": long["forecast_demand"].round(3), "actual_demand": long["demand"].astype(int)}))
        slong = sf.melt(id_vars=["time_key", "zone_key", "vehicle_key", "partners"], value_vars=SUPPLY_MODELS,
                        var_name="model_name", value_name="forecast_partners")
        insert_table(conn, "Fact_Supply_Forecast", pd.DataFrame({
            "time_key": slong["time_key"].astype(int), "zone_key": slong["zone_key"].astype(int),
            "vehicle_key": slong["vehicle_key"].astype(int), "model_name": slong["model_name"],
            "forecast_partners": slong["forecast_partners"].round(3), "actual_partners": slong["partners"].astype(int)}))
        insert_table(conn, "Fact_Pressure_Forecast", pd.DataFrame({
            "time_key": pf["time_key"].astype(int), "zone_key": pf["zone_key"].astype(int),
            "forecast_work_hours": pf["forecast_work_hours"].round(3),
            "forecast_supply_hours": pf["forecast_supply_hours"].round(3),
            "forecast_mpi": pf["forecast_mpi"].round(3).astype(object).where(pf["forecast_mpi"].notna(), None),
            "predicted_short": pf["predicted_short"].astype(int), "actual_short": pf["actual_short"].astype(int),
            "lost_jobs": pf["lost_jobs"].astype(int)}))
        print(f"Forecast tables written: {len(long):,} demand, {len(slong):,} supply, {len(pf):,} pressure rows")

        acc_a, acc_b = [clean(f) for f in run_query_all(conn, SQL / "04_forecast_accuracy.sql")]
        pr_a, pr_b = [clean(f) for f in run_query_all(conn, SQL / "05_pressure_forecast.sql")]

    models, by_service, floor = demand_tables(fc)
    st = supply_table(sf)

    doc = PHASE / "01_Forecasting_Approach.md"
    fill_block(doc, "data", table(pd.DataFrame([
        {"Dataset": "Demand (zone x hour x service)", "History rows": int((demand["data_split"] == "history").sum()),
         "Holdout rows": len(fc)},
        {"Dataset": "Baseline supply (home zone x hour x vehicle)",
         "History rows": int((supply["data_split"] == "history").sum()), "Holdout rows": len(sf)},
        {"Dataset": "Pressure (zone x hour)", "History rows": int((pressure["data_split"] == "history").sum()),
         "Holdout rows": len(pf)}]), {"History rows": "{:,}", "Holdout rows": "{:,}"}))

    doc = PHASE / "02_Demand_Forecast_Accuracy.md"
    fill_block(doc, "models", pct(models))
    fill_block(doc, "service", pct(by_service.rename(columns={m: f"{m} WAPE %" for m in DEMAND_MODELS})))
    fill_block(doc, "A", md(acc_a))
    fill_block(doc, "reconciliation", reconcile(by_service, acc_a))
    fill_block(doc, "headline", h_demand(models, floor))

    doc = PHASE / "03_Supply_Forecast.md"
    fill_block(doc, "models", pct(st))
    fill_block(doc, "B", md(acc_b))
    fill_block(doc, "headline", h_supply(st))

    doc = PHASE / "04_Pressure_Forecast.md"
    fill_block(doc, "A", md(pr_a))
    fill_block(doc, "B", md(pr_b))
    fill_block(doc, "headline", h_pressure(pr_a))

    draw_charts(fc, sf)
    print("Updated 4 documents in 09_Forecasting and 3 charts in images/charts")


if __name__ == "__main__":
    main()
