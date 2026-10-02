"""Stage 4: shadow prices must be consistent with re-solving."""
from pathlib import Path

import pytest

from pulse.optimization import marginal_value_table, top_bottlenecks
from pulse.utils import load_instance

TOY = Path(__file__).resolve().parents[1] / "data" / "sample" / "toy_lunch.yaml"


@pytest.fixture(scope="module")
def rows():
    return marginal_value_table(load_instance(TOY))


def row(rows, zone, ptype):
    return next(r for r in rows if r["zone"] == zone and r["partner_type"] == ptype)


def test_dual_is_bracketed_by_resolve_values(rows):
    """The LP objective is concave in supply, so for every zone/type:
    gain from +1  <=  dual  <=  loss from -1."""
    for r in rows:
        assert r["gain_plus_one"] <= r["dual"] + 1e-6
        if r["loss_minus_one"] is not None:
            assert r["dual"] <= r["loss_minus_one"] + 1e-6


def test_extra_two_wheeler_in_e_is_worth_195(rows):
    """E has 6 unserved food orders and no reachable help. One more
    two-wheeler serves 3 of them: 3 x (40 contribution + 25 avoided
    penalty) = 195. Dual and re-solve must agree."""
    r = row(rows, "E", "two_wheeler")
    assert r["dual"] == pytest.approx(195)
    assert r["gain_plus_one"] == pytest.approx(195)


def test_extra_two_wheeler_in_a_saves_one_move(rows):
    """A's food is already covered by partners moved from B. A local
    two-wheeler replaces one of those moves: saves 2 km x INR 5 = 10."""
    assert row(rows, "A", "two_wheeler")["gain_plus_one"] == pytest.approx(10)


def test_spare_supply_has_no_marginal_value(rows):
    """B already has idle partners, so one more is worth nothing."""
    for ptype in ("two_wheeler", "four_wheeler"):
        assert row(rows, "B", ptype)["gain_plus_one"] == pytest.approx(0)


def test_four_wheeler_in_e_is_worthless_to_add_but_costly_to_lose(rows):
    """Four-wheelers can't do food, and E's mobility is already met, so
    adding one is worth 0. But losing one leaves 2 rides unserved:
    2 x (60 + 30) = 180. The dual alone can't show this asymmetry."""
    r = row(rows, "E", "four_wheeler")
    assert r["gain_plus_one"] == pytest.approx(0)
    assert r["loss_minus_one"] == pytest.approx(180)
    assert r["degenerate"]


def test_top_bottleneck_is_zone_e_two_wheeler(rows):
    top = top_bottlenecks(rows)
    assert (top[0]["zone"], top[0]["partner_type"]) == ("E", "two_wheeler")
