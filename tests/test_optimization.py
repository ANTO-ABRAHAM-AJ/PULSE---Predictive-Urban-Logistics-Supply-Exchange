"""Stage 1: the solver must reproduce the hand-calculated toy answer.

Hand calculation (toy_lunch.yaml):
  - A needs 30 food orders = 10 two-wheelers (3 orders each). A has 2,
    so 8 must come in. B is closest (2 km, INR 10/move) with surplus.
  - Four-wheelers are food-ineligible, so they can only do mobility.
  - E is > 4 km from every zone, so it gets no help: its 2 two-wheelers
    cover 6 of 12 food orders -> 6 unserved (penalty 6 x 25 = 150).
  - Contribution: mobility 26 x 60 + food 63 x 40 = 1560 + 2520 = 4080.
  - Objective: 4080 - 80 (8 moves x 2 km x 5) - 150 = 3850.

Stage 2 stress tests are at the bottom of this file.
"""
import copy
from pathlib import Path

import pytest

from pulse.optimization import solve_allocation
from pulse.utils import load_instance

TOY = Path(__file__).resolve().parents[1] / "data" / "sample" / "toy_lunch.yaml"


@pytest.fixture(scope="module")
def result():
    return solve_allocation(load_instance(TOY))


def moved(result, frm, to, ptype, service):
    return sum(f["partners"] for f in result.flows
               if (f["from"], f["to"], f["partner_type"], f["service"])
               == (frm, to, ptype, service))


def test_solves_optimally(result):
    assert result.ok


def test_b_two_wheelers_move_to_a_for_food(result):
    assert moved(result, "B", "A", "two_wheeler", "food") == pytest.approx(8)


def test_four_wheelers_never_serve_food(result):
    assert not [f for f in result.flows
                if f["partner_type"] == "four_wheeler" and f["service"] == "food"]


def test_zone_e_receives_no_external_supply(result):
    assert not [f for f in result.flows if f["to"] == "E" and f["from"] != "E"]


def test_service_outcomes(result):
    assert result.unserved["A", "food"] == pytest.approx(0)
    assert result.unserved["E", "food"] == pytest.approx(6)


def test_objective_matches_hand_calculation(result):
    c = result.components
    assert c["contribution"] == pytest.approx(4080)
    assert c["reposition_cost"] == pytest.approx(80)
    assert c["unserved_penalty"] == pytest.approx(150)
    assert result.objective == pytest.approx(3850)


# ---------------------------------------------------------------------------
# Stage 2: stress tests. Each test states the expected behavior first.
# ---------------------------------------------------------------------------
@pytest.fixture(scope="module")
def base():
    return load_instance(TOY)


def solve_variant(base, change):
    inst = copy.deepcopy(base)
    change(inst)
    return solve_allocation(inst)


def total_demand(inst, service):
    return sum(inst["demand"][z][service] for z in inst["zones"])


def test_no_supply_leaves_all_demand_unserved(base):
    """Expected: still solvable; nothing moves; every unit is unserved,
    so the objective is the full penalty: -(26 x 30 + 69 x 25) = -2505."""
    def change(inst):
        for z in inst["zones"]:
            for k in inst["partner_types"]:
                inst["supply"][z][k] = 0
    r = solve_variant(base, change)
    assert r.ok
    assert r.flows == []
    for (z, s), u in r.unserved.items():
        assert u == pytest.approx(base["demand"][z][s])
    assert r.objective == pytest.approx(-2505)


def test_excess_supply_serves_everything_without_moving(base):
    """Expected: with 10x supply every zone covers itself, so no partner
    repositions (staying is free) and nothing is unserved.
    Objective = 26 x 60 + 69 x 40 = 4320."""
    def change(inst):
        for z in inst["zones"]:
            for k in inst["partner_types"]:
                inst["supply"][z][k] *= 10
    r = solve_variant(base, change)
    assert r.ok
    assert r.components["reposition_cost"] == pytest.approx(0)
    assert all(u == pytest.approx(0) for u in r.unserved.values())
    assert r.objective == pytest.approx(4320)


def test_impossible_demand_uses_all_reachable_two_wheelers(base):
    """Expected: A food = 1000 can't be met, but it must not break the
    model. Food is worth more per two-wheeler (3 x 65 = 195) than mobility
    (2 x 90 = 180), and four-wheelers can cover mobility, so all 23
    two-wheelers in A-D do food: 69 orders. The other zones' 27 orders are
    served first, leaving 42 for A -> 958 unserved."""
    def change(inst):
        inst["demand"]["A"]["food"] = 1000
    r = solve_variant(base, change)
    assert r.ok
    tw_food_from_ad = sum(f["partners"] for f in r.flows
                          if f["partner_type"] == "two_wheeler"
                          and f["service"] == "food" and f["from"] in "ABCD")
    assert tw_food_from_ad == pytest.approx(23)
    assert r.unserved["A", "food"] == pytest.approx(958)


def test_zero_repositioning_cost_only_removes_move_cost(base):
    """Expected: with free moves the optimum may not be unique (ties), so we
    test the objective, not specific flows. Same service outcome as the
    base case, minus the INR 80 move cost: 3850 + 80 = 3930."""
    def change(inst):
        inst["cost_per_km"] = {k: 0 for k in inst["partner_types"]}
    r = solve_variant(base, change)
    assert r.ok
    assert r.objective == pytest.approx(3930)


def test_mobility_spike_does_not_steal_from_food(base):
    """Expected: C mobility 8 -> 80. Services now compete for two-wheelers.
    Since a two-wheeler earns more on food, A's food must stay fully served;
    only spare partners go to C: C's own 3 four-wheelers + 1 spare
    two-wheeler, and B's 2 spare four-wheelers + 3 spare two-wheelers
    = 9 partners x 2 trips = 18 served -> 62 unserved."""
    def change(inst):
        inst["demand"]["C"]["mobility"] = 80
    r = solve_variant(base, change)
    assert r.ok
    assert r.unserved["A", "food"] == pytest.approx(0)
    assert r.unserved["C", "mobility"] == pytest.approx(62)


def test_impossible_service_floor_is_reported_as_infeasible(base):
    """Expected: 80% food service everywhere is impossible because E (out of
    reach) can serve only 6 of 12 orders. The model must say so clearly,
    not crash or return a fake allocation."""
    def change(inst):
        inst["min_service_level"]["food"] = 0.8
    r = solve_variant(base, change)
    assert r.status == "INFEASIBLE"
    assert not r.ok
    assert r.flows == []
    assert "minimum service" in r.message


def test_achievable_service_floor_is_met(base):
    """Expected: 100% mobility service is achievable, so the floor holds and
    no mobility demand is left unserved."""
    def change(inst):
        inst["min_service_level"]["mobility"] = 1.0
    r = solve_variant(base, change)
    assert r.ok
    assert all(r.unserved[z, "mobility"] == pytest.approx(0) for z in base["zones"])
