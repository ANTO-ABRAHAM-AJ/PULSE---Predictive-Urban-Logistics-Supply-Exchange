"""Phase 10: run repositioning scenarios on Bengaluru and shape the results.

Inputs
  * simulation data: data/processed/ (demand, calendar, partners, partner-days)
  * forecasts and economics: PULSE_DW (Phase 9 forecast table, Phase 5 views)
  * settings: config/bengaluru/policy.yaml
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pulse.generation.city import CITY_DIR
from pulse.optimization.policy import OptimizerPolicy
from pulse.optimization.simulation import PolicyRun, prepare_days, simulate_policy, summarize

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "data" / "processed"
SCENARIO_NAMES = {"status_quo": "Status quo",
                  "optimizer_profit": "Optimizer (profit)",
                  "optimizer_service": "Optimizer (service, ₹20 goodwill)",
                  "optimizer_perfect_forecast": "Optimizer, perfect forecast"}


def load_policy(path: Path | str = CITY_DIR / "policy.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_simulation_inputs(data_dir: Path = DATA) -> dict:
    return {"calendar": pd.read_csv(data_dir / "calendar.csv", parse_dates=["date"]),
            "demand": pd.read_csv(data_dir / "demand_hourly.csv", parse_dates=["date"]),
            "partners": pd.read_csv(data_dir / "partners.csv"),
            "partner_days": pd.read_csv(data_dir / "partner_days.csv", parse_dates=["date"])}


def economics(policy: dict, contribution: dict, penalty: float) -> dict:
    return {"contribution": contribution, "penalty": {"mobility": penalty, "food": penalty},
            "cost_per_km": policy["reposition_cost_per_km"],
            "jobs_per_partner": policy["jobs_per_partner_per_hour"]}


def actual_lookup(demand: pd.DataFrame) -> dict:
    return dict(zip(zip(demand["date"], demand["hour"], demand["zone_id"], demand["service"]),
                    demand["demand"].astype(float)))


def run_scenarios(inputs: dict, dates, forecast: dict, contribution: dict, policy: dict,
                  progress=print) -> dict[str, PolicyRun]:
    prep = prepare_days(inputs["demand"], inputs["calendar"], inputs["partners"],
                        inputs["partner_days"], dates, seed=policy["replay_seed"])
    runs = {"status_quo": simulate_policy(prep)}
    progress("  status quo replayed")
    actual = actual_lookup(inputs["demand"])
    for code, s in policy["scenarios"].items():
        lookup = actual if s["forecast"] == "actual" else forecast
        pol = OptimizerPolicy(lookup, economics(policy, contribution, s["penalty"]), prep.ctx,
                              lookahead=policy["lookahead"], max_move_km=policy["max_move_km"],
                              seed=policy["seed"], remote_efficiency=policy["remote_efficiency"])
        runs[code] = simulate_policy(prep, pol)
        progress(f"  {code} simulated")
    return runs


def comparison(runs: dict[str, PolicyRun]) -> pd.DataFrame:
    base = summarize(runs["status_quo"])
    rows = []
    for code, run in runs.items():
        s = summarize(run)
        days = run.jobs["date"].nunique()
        rows.append({"Scenario": SCENARIO_NAMES.get(code, code),
                     "Contribution (INR)": s["contribution"],
                     "Change vs status quo %": 100 * (s["contribution"] / base["contribution"] - 1),
                     "Jobs lost to no partner": s["lost_no_partner"],
                     "Lost jobs change %": 100 * (s["lost_no_partner"] / base["lost_no_partner"] - 1),
                     "Ride completion %": 100 * s["mobility_completion"],
                     "Food delivered %": 100 * s["food_completion"],
                     "Moves per day": s["moves"] / days,
                     "Repositioning cost (INR)": s["reposition_cost"]})
    return pd.DataFrame(rows)


def daily_contribution(run: PolicyRun) -> pd.Series:
    rev = run.jobs.groupby("date")["revenue"].sum()
    cost = run.moves.groupby("date")["cost"].sum() if len(run.moves) else pd.Series(dtype=float)
    return rev.sub(cost, fill_value=0.0)


def uplift_ranges(runs: dict[str, PolicyRun]) -> pd.DataFrame:
    """Paired daily differences vs the status quo, with a 95% interval (t, df = days - 1)."""
    from scipy import stats
    base = daily_contribution(runs["status_quo"])
    rows = []
    for code, run in runs.items():
        if code == "status_quo":
            continue
        d = (daily_contribution(run) - base).dropna()
        half = stats.t.ppf(0.975, len(d) - 1) * d.std(ddof=1) / np.sqrt(len(d))
        done = lambda r: r.jobs.assign(c=r.jobs["status"] == "completed").groupby("date")["c"].sum()
        lost = done(run) - done(runs["status_quo"])
        rows.append({"Scenario": SCENARIO_NAMES.get(code, code),
                     "Contribution uplift per day (INR)": d.mean(),
                     "95% range low (INR)": d.mean() - half, "95% range high (INR)": d.mean() + half,
                     "Days better than status quo": f"{int((d > 0).sum())} of {len(d)}",
                     "Extra completed jobs per day": lost.mean()})
    return pd.DataFrame(rows)


def zone_hour_table(code: str, run: PolicyRun, keys: dict) -> pd.DataFrame:
    """Aggregate a run to scenario x hour x zone x service for the warehouse."""
    j = run.jobs.assign(requests=1,
                        completed=lambda d: (d["status"] == "completed").astype(int),
                        lost_no_partner=lambda d: (d["status"] == "cancelled_no_partner").astype(int),
                        cancelled_customer=lambda d: (d["status"] == "cancelled_customer").astype(int))
    out = (j.groupby(["date", "hour", "zone_id", "service"])
           [["requests", "completed", "lost_no_partner", "cancelled_customer", "revenue"]]
           .sum().reset_index())
    out["revenue"] = out["revenue"].round(2)
    out["time_key"] = (out["date"].dt.strftime("%Y%m%d").astype(int) * 100 + out["hour"]).astype(int)
    out["zone_key"] = out["zone_id"].map(keys["zone"])
    out["service_key"] = out["service"].map(keys["service"])
    out["scenario_code"] = code
    return out[["scenario_code", "time_key", "zone_key", "service_key", "requests", "completed",
                "lost_no_partner", "cancelled_customer", "revenue"]]
