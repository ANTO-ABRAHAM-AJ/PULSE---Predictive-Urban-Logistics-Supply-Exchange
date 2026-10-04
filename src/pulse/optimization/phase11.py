"""Phase 11 studies: incentive programmes and stress scenarios (replay simulator).

  * targets  — shadow prices from the profit policy on VALIDATION weekdays
  * incentive study — profit policy alone vs + programme at each bonus, holdout weeks
  * stress study — status quo / profit / service / profit + incentive under each
    stress scenario, on every second holdout day (14 days) to keep run time short
"""
from __future__ import annotations

import pandas as pd

from pulse.optimization.city import economics
from pulse.optimization.incentives import (add_incentive_partners, choose_targets, partner_hours_per_day,
                                           programme_cost, stress, windows)
from pulse.optimization.policy import OptimizerPolicy
from pulse.optimization.simulation import prepare_days, simulate_policy, summarize


def _policy(prep, forecast, policy, contribution, penalty, record=False):
    return OptimizerPolicy(forecast, economics(policy, contribution, penalty), prep.ctx,
                           lookahead=policy["lookahead"], max_move_km=policy["max_move_km"],
                           seed=policy["seed"], remote_efficiency=policy["remote_efficiency"], record=record)


def validation_targets(inp, policy, contribution):
    """Shadow prices and remaining losses from the profit policy on validation weekdays 9-12."""
    cal, dem = inp["calendar"], inp["demand"]
    cal = cal.assign(week=(cal["date"] - cal["date"].min()).dt.days // 7 + 1)
    val = list(cal.loc[cal["week"].between(9, 12) & ~cal["is_weekend"].astype(bool), "date"])
    hist = dem.merge(cal[["date", "week", "is_weekend"]])
    prof = hist[hist["week"] <= 8].groupby(["zone_id", "service", "hour", "is_weekend"])["demand"].mean()
    v = dem[dem["date"].isin(val)].merge(cal[["date", "is_weekend"]]).join(
        prof.rename("f"), on=["zone_id", "service", "hour", "is_weekend"])
    fc = dict(zip(zip(v["date"], v["hour"], v["zone_id"], v["service"]), v["f"].fillna(0)))
    prep = prepare_days(dem, cal, inp["partners"], inp["partner_days"], val, seed=policy["replay_seed"])
    run = simulate_policy(prep, _policy(prep, fc, policy, contribution, 0, record=True))
    duals = pd.DataFrame(run.duals)
    lost = (run.jobs[run.jobs["status"] == "cancelled_no_partner"].groupby(["zone_id", "hour"]).size()
            .div(len(val)).rename("lost").reset_index())
    return duals, lost, len(val)


def programmes(duals, lost, n_val, policy) -> dict[int, list[dict]]:
    cfg = policy["incentives"]
    return {b: windows(choose_targets(duals, lost, b, n_val, cfg["max_partners_per_window"]))
            for b in cfg["bonus_levels"]}


def _row(study, code, case, pol_name, bonus, s, days, ph_day=0, inc_cost=0.0):
    return {"study": study, "scenario_code": code, "stress_case": case, "policy": pol_name, "bonus": bonus,
            "days": days, "requests": s["requests"], "completed": s["completed"],
            "lost_no_partner": s["lost_no_partner"], "revenue": round(s["revenue"], 2),
            "reposition_cost": round(s["reposition_cost"], 2), "incentive_partner_hours": ph_day,
            "incentive_cost": round(inc_cost, 2),
            "contribution": round(s["revenue"] - s["reposition_cost"] - inc_cost, 2)}


def incentive_study(inp, dates, forecast, policy, contribution, progs, progress=print):
    """Holdout: status quo, profit policy, and profit policy + each programme."""
    cal = inp["calendar"].set_index("date")
    weekdays = sum(1 for d in dates if not cal.loc[d, "is_weekend"])
    prep = prepare_days(inp["demand"], inp["calendar"], inp["partners"], inp["partner_days"], dates,
                        seed=policy["replay_seed"])
    rows, runs = [], {}
    runs["status_quo"] = simulate_policy(prep)
    rows.append(_row("incentive", "status_quo", "normal", "status_quo", 0, summarize(runs["status_quo"]), len(dates)))
    runs["optimizer_profit"] = simulate_policy(prep, _policy(prep, forecast, policy, contribution, 0))
    rows.append(_row("incentive", "optimizer_profit", "normal", "profit", 0, summarize(runs["optimizer_profit"]), len(dates)))
    progress("  incentive study: baselines replayed")
    for bonus, prog in progs.items():
        p2 = add_incentive_partners(prep, prog, policy["incentives"]["weekdays_only"])
        code = f"incentive_{bonus}"
        runs[code] = simulate_policy(p2, _policy(p2, forecast, policy, contribution, 0))
        rows.append(_row("incentive", code, "normal", "profit + incentive", bonus, summarize(runs[code]), len(dates),
                         partner_hours_per_day(prog), programme_cost(prog, bonus, weekdays)))
        progress(f"  incentive study: ₹{bonus} programme simulated")
    return pd.DataFrame(rows), runs


def stress_study(inp, dates, forecast, policy, contribution, prog, bonus, progress=print):
    """Every stress case (plus normal) under status quo, profit, service and profit + incentive."""
    cal = inp["calendar"].set_index("date")
    weekdays = sum(1 for d in dates if not cal.loc[d, "is_weekend"])
    rows = []
    for case in ["normal"] + list(policy["stress_scenarios"]):
        if case == "normal":
            dem, pdays = inp["demand"], inp["partner_days"]
        else:
            dem, pdays = stress(inp["demand"], inp["partner_days"], inp["partners"], inp["calendar"], case,
                                policy["stress_scenarios"])
        prep = prepare_days(dem, inp["calendar"], inp["partners"], pdays, dates, seed=policy["replay_seed"])
        rows.append(_row("stress", f"{case}:status_quo", case, "status_quo", 0, summarize(simulate_policy(prep)), len(dates)))
        for name, pen in (("profit", 0), ("service", 20)):
            s = summarize(simulate_policy(prep, _policy(prep, forecast, policy, contribution, pen)))
            rows.append(_row("stress", f"{case}:{name}", case, name, 0, s, len(dates)))
        p2 = add_incentive_partners(prep, prog, policy["incentives"]["weekdays_only"])
        s = summarize(simulate_policy(p2, _policy(p2, forecast, policy, contribution, 0)))
        rows.append(_row("stress", f"{case}:profit_incentive", case, "profit + incentive", bonus, s, len(dates),
                         partner_hours_per_day(prog), programme_cost(prog, bonus, weekdays)))
        progress(f"  stress study: {case} done")
    return pd.DataFrame(rows)


def ladder(inc: pd.DataFrame, phase10: dict | None = None) -> pd.DataFrame:
    """Cost per recovered job for each lever, relative to the previous rung."""
    i = inc.set_index("scenario_code")
    days = i["days"].iloc[0]
    sq, prof = i.loc["status_quo"], i.loc["optimizer_profit"]
    rows = [{"Lever": "Profit repositioning (Phase 10)", "Compared with": "status quo",
             "Extra jobs served per day": (sq["lost_no_partner"] - prof["lost_no_partner"]) / days,
             "Net cost per day (INR)": (sq["contribution"] - prof["contribution"]) / days}]
    if phase10:
        rows.append({"Lever": "Service repositioning, ₹20 goodwill (Phase 10)", "Compared with": "status quo",
                     "Extra jobs served per day": phase10["extra_jobs_per_day"],
                     "Net cost per day (INR)": -phase10["uplift_per_day"]})
    for code, r in i.iterrows():
        if code.startswith("incentive_"):
            rows.append({"Lever": f"Incentives at ₹{int(r['bonus'])} per partner-hour", "Compared with": "profit repositioning",
                         "Extra jobs served per day": (prof["lost_no_partner"] - r["lost_no_partner"]) / days,
                         "Net cost per day (INR)": (prof["contribution"] - r["contribution"]) / days})
    out = pd.DataFrame(rows)
    out["Net cost per extra job (INR)"] = out["Net cost per day (INR)"] / out["Extra jobs served per day"]
    return out
