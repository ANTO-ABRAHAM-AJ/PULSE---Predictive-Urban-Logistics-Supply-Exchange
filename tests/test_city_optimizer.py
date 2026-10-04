"""Phase 10: LP dispatch-reach extension, fair replay simulator and policy (no database)."""
import numpy as np
import pandas as pd
import pytest

from pulse.optimization.model import solve_allocation
from pulse.optimization.policy import OptimizerPolicy
from pulse.optimization.simulation import prepare_days, simulate_policy, summarize


def _two_zone_instance(reach: bool) -> dict:
    inst = {"zones": ["A", "B"], "services": ["mobility", "food"],
            "partner_types": ["two_wheeler", "four_wheeler"],
            "distance_km": {"A": {"A": 0.0, "B": 3.0}, "B": {"A": 3.0, "B": 0.0}},
            "max_reposition_km": 12.0,
            "eligibility": {"two_wheeler": {"mobility": True, "food": True},
                            "four_wheeler": {"mobility": True, "food": False}},
            "jobs_per_partner": {"mobility": 2, "food": 3},
            "contribution": {"mobility": 27.0, "food": 49.0}, "penalty": {"mobility": 0.0, "food": 0.0},
            "cost_per_km": {"two_wheeler": 6.0, "four_wheeler": 12.0},
            "supply": {"A": {"two_wheeler": 10.0, "four_wheeler": 0.0}, "B": {"two_wheeler": 0.0, "four_wheeler": 0.0}},
            "demand": {"A": {"mobility": 0.0, "food": 0.0}, "B": {"mobility": 4.0, "food": 0.0}},
            "min_service_level": {"mobility": 0.0, "food": 0.0}}
    if reach:
        inst["service_reach_km"] = {"mobility": 5.0, "food": 8.0}
        inst["remote_efficiency"] = {"mobility": 0.6, "food": 0.8}
    return inst


def test_without_reach_the_lp_pays_to_move():
    res = solve_allocation(_two_zone_instance(reach=False))
    moves = [f for f in res.flows if f["from"] != f["to"]]
    assert res.ok and sum(f["partners"] for f in moves) == pytest.approx(2.0)   # 4 rides / 2 per partner


def test_with_reach_neighbours_serve_without_moving():
    res = solve_allocation(_two_zone_instance(reach=True))
    assert res.ok
    assert not [f for f in res.flows if f["from"] != f["to"]]                  # no paid moves
    assert res.served["B", "mobility"] == pytest.approx(4.0)                    # still fully served


def test_reach_does_not_apply_beyond_its_distance():
    inst = _two_zone_instance(reach=True)
    inst["distance_km"] = {"A": {"A": 0.0, "B": 9.0}, "B": {"A": 9.0, "B": 0.0}}
    inst["penalty"] = {"mobility": 50.0, "food": 50.0}       # make the move clearly worth its cost
    res = solve_allocation(inst)
    assert [f for f in res.flows if f["from"] != f["to"]]                       # too far: must move


@pytest.fixture(scope="module")
def tiny_city():
    """60 partners spread over real Bengaluru zones, two days of modest demand."""
    from pulse.generation.city import load_city
    zones = list(load_city()["zones"])
    rng = np.random.default_rng(0)
    partners = pd.DataFrame({
        "partner_id": [f"P{i:05d}" for i in range(60)],
        "vehicle_type": ["two_wheeler" if i % 3 else "four_wheeler" for i in range(60)],
        "home_zone": [zones[i % len(zones)] for i in range(60)],
        "shift_type": ["full_day"] * 60, "eligible_services": "mobility"})
    dates = list(pd.to_datetime(["2026-08-24", "2026-08-25"]))
    calendar = pd.DataFrame({"date": dates, "is_weekend": [0, 0]})
    rows = [{"date": d, "hour": h, "zone_id": z, "service": s, "demand": int(rng.poisson(0.4))}
            for d in dates for h in range(8, 20) for z in zones for s in ("mobility", "food")]
    demand = pd.DataFrame(rows)
    partner_days = pd.DataFrame([{"date": d, "partner_id": p} for d in dates for p in partners["partner_id"]])
    return demand, calendar, partners, partner_days, dates


def test_replay_is_identical_for_the_same_policy(tiny_city):
    demand, calendar, partners, partner_days, dates = tiny_city
    a = prepare_days(demand, calendar, partners, partner_days, dates, seed=1)
    b = prepare_days(demand, calendar, partners, partner_days, dates, seed=1)
    pd.testing.assert_frame_equal(a.days[0][3], b.days[0][3])                  # same requests, same draws
    assert summarize(simulate_policy(a)) == summarize(simulate_policy(b))


class _MoveOnce:
    """Moves partner 0 to a fixed zone at 08:00 on each day."""
    cost_per_km_by_type = {True: 6.0, False: 12.0}

    def __init__(self, to):
        self.to = to

    def __call__(self, day, hour, state, ctx):
        return [(0, self.to)] if hour == 8 else []


def test_moves_are_costed_and_requests_unchanged(tiny_city):
    demand, calendar, partners, partner_days, dates = tiny_city
    prep = prepare_days(demand, calendar, partners, partner_days, dates, seed=1)
    base = simulate_policy(prep)
    to = (prep.ctx["home_idx"][0] + 5) % len(prep.ctx["zone_ids"])
    run = simulate_policy(prep, _MoveOnce(to))
    assert len(run.moves) == 2                                                 # one per day
    km = prep.ctx["km"][prep.ctx["home_idx"][0], to]
    assert run.moves["km"].iloc[0] == pytest.approx(km)
    assert run.moves["cost"].iloc[0] == pytest.approx(km * 12.0)               # partner 0 is a cab
    assert len(run.jobs) == len(base.jobs)                                     # identical customers


def test_optimizer_policy_runs_and_only_moves_idle_partners(tiny_city):
    demand, calendar, partners, partner_days, dates = tiny_city
    prep = prepare_days(demand, calendar, partners, partner_days, dates, seed=1)
    forecast = dict(zip(zip(demand["date"], demand["hour"], demand["zone_id"], demand["service"]),
                        demand["demand"].astype(float)))
    econ = {"contribution": {"mobility": 27.0, "food": 49.0}, "penalty": {"mobility": 20.0, "food": 20.0},
            "cost_per_km": {"two_wheeler": 6.0, "four_wheeler": 12.0},
            "jobs_per_partner": {"mobility": 2, "food": 3}}
    run = simulate_policy(prep, OptimizerPolicy(forecast, econ, prep.ctx))
    s = summarize(run)
    assert s["requests"] == summarize(simulate_policy(prep))["requests"]
    if len(run.moves):
        assert (run.moves["km"] <= 12.0 + 1e-9).all()                         # respects the move limit
        assert run.moves.groupby(["date", "hour", "partner_idx"]).size().max() == 1
