"""Phase 11: incentive targeting, extra partners, stress transforms, ladder (no database)."""
import importlib.util
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pulse.optimization.incentives import (add_incentive_partners, choose_targets, partner_hours_per_day,
                                           programme_cost, scale_counts, stress, windows)
from pulse.optimization.phase11 import ladder
from pulse.optimization.simulation import prepare_days, simulate_policy

ROOT = Path(__file__).resolve().parents[1]


def test_targets_need_value_above_the_bonus():
    duals = pd.DataFrame({"zone_id": ["A", "A", "B"], "hour": [9, 10, 9],
                          "partner_type": ["two_wheeler"] * 3, "dual": [500.0, 100.0, 900.0]})
    lost = pd.DataFrame({"zone_id": ["A", "B"], "hour": [9, 9], "lost": [7.0, 30.0]})
    t = choose_targets(duals, lost, bonus=40, weekdays=10)          # values: A9 50, A10 10, B9 90
    assert set(zip(t.zone_id, t.hour)) == {("A", 9), ("B", 9)}
    assert dict(zip(t.zone_id, t.partners)) == {"A": 4, "B": 6}      # ceil(7/2)=4; ceil(30/2)=15 -> cap 6


def test_windows_group_consecutive_hours():
    t = pd.DataFrame({"zone_id": ["A"] * 4, "hour": [7, 8, 9, 18], "partners": [1, 3, 2, 1]})
    w = windows(t)
    assert [(x["hours"], x["partners"]) for x in w] == [([7, 8, 9], 3), ([18], 1)]
    assert partner_hours_per_day(w) == 10 and programme_cost(w, 40, 2) == 800


def test_scale_counts_moves_totals_in_the_right_direction():
    rng = np.random.default_rng(0)
    c = np.full(20000, 5)
    assert scale_counts(c, np.full(20000, 1.4), rng).mean() == pytest.approx(7.0, rel=0.03)
    assert scale_counts(c, np.full(20000, 0.5), rng).mean() == pytest.approx(2.5, rel=0.03)
    assert (scale_counts(c, np.ones(20000), rng) == 5).all()


def test_stress_scenarios_change_the_right_side():
    dates = pd.to_datetime(["2026-08-24", "2026-08-25"])
    cal = pd.DataFrame({"date": dates, "is_rain": [False, True], "is_weekend": [0, 0]})
    dem = pd.DataFrame({"date": np.repeat(dates, 2), "hour": [18, 9] * 2, "zone_id": "CBD",
                        "service": ["food", "mobility"] * 2, "demand": [1000] * 4})
    partners = pd.DataFrame({"partner_id": ["P1", "P2"], "vehicle_type": ["two_wheeler", "four_wheeler"]})
    pdays = pd.DataFrame({"date": np.repeat(dates, 2), "partner_id": ["P1", "P2"] * 2})
    rules = {"fest": {"type": "demand", "multiplier": 1.5, "hours": [18]},
             "short": {"type": "supply", "keep_share": 0.0},
             "rain": {"type": "rain", "demand_multiplier": {"mobility": 1.15, "food": 1.3},
                      "two_wheeler_supply_multiplier": 0.0}}
    d, _ = stress(dem, pdays, partners, cal, "fest", rules)
    assert d.loc[d.hour == 18, "demand"].mean() > 1300 and (d.loc[d.hour == 9, "demand"] == 1000).all()
    _, p = stress(dem, pdays, partners, cal, "short", rules)
    assert p.empty
    d, p = stress(dem, pdays, partners, cal, "rain", rules)
    rainy = d["date"] == dates[1]
    assert (d.loc[rainy, "demand"] == 1000).all()                          # already-rainy day unchanged
    assert set(p.loc[p.date == dates[0], "partner_id"]) == {"P2"}          # two-wheeler dropped on the dry day


def test_incentive_partners_are_added_only_for_their_window():
    from pulse.generation.city import load_city
    zones = list(load_city()["zones"])
    partners = pd.DataFrame({"partner_id": ["P1"], "vehicle_type": ["two_wheeler"], "home_zone": [zones[0]],
                             "shift_type": ["full_day"], "eligible_services": ["mobility"]})
    dates = list(pd.to_datetime(["2026-08-24", "2026-08-29"]))                # Monday, Saturday
    cal = pd.DataFrame({"date": dates, "is_weekend": [0, 1]})
    dem = pd.DataFrame({"date": dates, "hour": 18, "zone_id": "KIA", "service": "mobility", "demand": [3, 3]})
    pdays = pd.DataFrame({"date": dates, "partner_id": ["P1", "P1"]})
    prep = prepare_days(dem, cal, partners, pdays, dates)
    p2 = add_incentive_partners(prep, [{"zone_id": "KIA", "hours": [18, 19], "partners": 2}])
    n = len(prep.ctx["home_idx"])
    assert len(p2.ctx["home_idx"]) == n + 2
    assert p2.ctx["online_by_hour"][:, n:].sum(axis=0).tolist() == [2, 2]  # two hours each
    assert p2.days[0][2][n:].all() and not p2.days[1][2][n:].any()          # weekday only
    assert len(prep.ctx["home_idx"]) == n                                   # original untouched
    run = simulate_policy(p2)
    assert (run.jobs.status == "completed").sum() >= (simulate_policy(prep).jobs.status == "completed").sum()


def test_ladder_costs_each_rung():
    inc = pd.DataFrame({"scenario_code": ["status_quo", "optimizer_profit", "incentive_40"],
                        "bonus": [0, 0, 40], "days": [10, 10, 10], "lost_no_partner": [1000, 800, 500],
                        "contribution": [10000.0, 10100.0, 7100.0]})
    lad = ladder(inc).set_index("Lever")
    assert lad.loc["Profit repositioning (Phase 10)", "Extra jobs served per day"] == 20
    assert lad.loc["Profit repositioning (Phase 10)", "Net cost per extra job (INR)"] == pytest.approx(-0.5)
    assert lad.loc["Incentives at ₹40 per partner-hour", "Net cost per extra job (INR)"] == pytest.approx(10.0)


def test_report_documents_have_their_blocks():
    docs = {"01_Incentive_Design.md": ["targets"], "02_Incentive_Results.md": ["A", "B", "ladder", "headline"],
            "03_Stress_Scenarios.md": ["A", "B", "headline"]}
    for doc, blocks in docs.items():
        text = (ROOT / "11_Incentive_Economics" / doc).read_text(encoding="utf-8")
        for b in blocks:
            assert f"<!-- AUTO:{b} -->" in text, (doc, b)


def test_headlines_run_on_frames_shaped_like_the_sql():
    spec = importlib.util.spec_from_file_location("r11", ROOT / "scripts" / "report_phase11.py")
    r11 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r11)
    a1 = pd.DataFrame({"Bonus per partner-hour (INR)": [0, 0, 40, 60], "Partner-hours bought per weekday": [0, 0, 800, 400],
                       "Revenue gain per day (INR)": [0, 0, 6000, 5000]})
    lad = pd.DataFrame({"Lever": ["Profit repositioning (Phase 10)", "Incentives at ₹40 per partner-hour"],
                        "Extra jobs served per day": [100, 300], "Net cost per extra job (INR)": [0.0, 50.0]})
    assert r11.h_incentives(lad, a1).startswith("- ")
    cases = ["normal", "rain_every_day", "partner_shortage"]
    a2 = pd.DataFrame({"Stress case": cases, "Policy": "status_quo", "Lost jobs vs normal status quo %": [0.0, 48.0, 20.0]})
    b2 = pd.DataFrame({"Stress case": cases, "Recovered by profit policy %": [15.7, 8.0, 10.2],
                       "Break-even bonus per partner-hour (INR)": [13.0, 26.0, 20.0]})
    text = r11.h_stress(a2, b2)
    assert "rain every day" in text and "₹26" in text
