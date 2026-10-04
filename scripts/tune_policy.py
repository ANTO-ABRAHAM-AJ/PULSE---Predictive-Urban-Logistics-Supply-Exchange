"""Phase 10: choose the repositioning-policy settings on VALIDATION weeks.

Validation = history weeks 9-12 (every second day, 14 days), with demand
forecast as the history profile of weeks 1-8 — the holdout weeks 13-16 are
never touched. Writes the grid to 10_Optimization/01_City_Optimizer_Design.md
and 10_Optimization/tuning_results.csv. The chosen settings are recorded by
hand in config/bengaluru/policy.yaml.

Takes about 10 minutes.

Usage:
    python scripts/tune_policy.py
"""
from pathlib import Path

import pandas as pd

from pulse.optimization.city import economics, load_policy, load_simulation_inputs
from pulse.optimization.policy import OptimizerPolicy
from pulse.optimization.simulation import prepare_days, simulate_policy, summarize
from pulse.reporting import fill_block, table

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "10_Optimization" / "01_City_Optimizer_Design.md"
GRID = [(pen, km, w) for pen in (0, 20, 40) for km in (8, 12, 16) for w in (0.0, 0.5, 1.0)]


def main() -> None:
    policy = load_policy()
    inp = load_simulation_inputs()
    cal, dem = inp["calendar"], inp["demand"]
    cal = cal.assign(week=(cal["date"] - cal["date"].min()).dt.days // 7 + 1)
    val_dates = list(cal.loc[cal["week"].between(9, 12), "date"])[::2]
    hist = dem.merge(cal[["date", "week", "is_weekend"]])
    profile = (hist[hist["week"] <= 8].groupby(["zone_id", "service", "hour", "is_weekend"])["demand"].mean())
    v = dem[dem["date"].isin(val_dates)].merge(cal[["date", "is_weekend"]]).join(
        profile.rename("f"), on=["zone_id", "service", "hour", "is_weekend"])
    forecast = dict(zip(zip(v["date"], v["hour"], v["zone_id"], v["service"]), v["f"].fillna(0)))

    prep = prepare_days(dem, cal, inp["partners"], inp["partner_days"], val_dates, seed=policy["replay_seed"])
    base_run = simulate_policy(prep)
    base = summarize(base_run)
    j = base_run.jobs
    contribution = {s: float(j[(j["service"] == s) & (j["status"] == "completed")]["revenue"].mean())
                    for s in ("mobility", "food")}

    rows = []
    for pen, km, w in GRID:
        pol = OptimizerPolicy(forecast, economics(policy, contribution, pen), prep.ctx, lookahead=w,
                              max_move_km=km, seed=policy["seed"], remote_efficiency=policy["remote_efficiency"],
                              record=False)
        r = summarize(simulate_policy(prep, pol))
        rows.append({"Penalty (INR)": pen, "Max move km": km, "Look-ahead": w,
                     "Contribution change %": 100 * (r["contribution"] / base["contribution"] - 1),
                     "Lost jobs change %": 100 * (r["lost_no_partner"] / base["lost_no_partner"] - 1),
                     "Moves per day": r["moves"] / len(val_dates)})
        print(f"  penalty {pen:2d}  max km {km:2d}  look-ahead {w:.1f}: "
              f"contribution {rows[-1]['Contribution change %']:+.2f}%  lost {rows[-1]['Lost jobs change %']:+.1f}%")
    grid = pd.DataFrame(rows)
    grid.to_csv(ROOT / "10_Optimization" / "tuning_results.csv", index=False)
    fill_block(DOC, "tuning", table(grid, {"Contribution change %": "{:+.2f}", "Lost jobs change %": "{:+.1f}",
                                           "Moves per day": "{:.0f}", "Look-ahead": "{:.1f}"}))
    print(f"Validation grid written ({len(grid)} settings); see {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
