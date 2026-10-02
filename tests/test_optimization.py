"""Stage 1: the solver must reproduce the hand-calculated toy answer.

Hand calculation (toy_lunch.yaml):
  - A needs 30 food orders = 10 two-wheelers (3 orders each). A has 2,
    so 8 must come in. B is closest (2 km, INR 10/move) with surplus.
  - Four-wheelers are food-ineligible, so they can only do mobility.
  - E is > 4 km from every zone, so it gets no help: its 2 two-wheelers
    cover 6 of 12 food orders -> 6 unserved (penalty 6 x 25 = 150).
  - Contribution: mobility 26 x 60 + food 63 x 40 = 1560 + 2520 = 4080.
  - Objective: 4080 - 80 (8 moves x 2 km x 5) - 150 = 3850.

Stage 2 stress tests will be added to this file.
"""
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
