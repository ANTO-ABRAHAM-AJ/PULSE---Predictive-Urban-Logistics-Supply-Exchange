"""Stage 5b (part 1): the fleet must create the planted supply problems."""
import pandas as pd
import pytest

from pulse.generation.city import load_city
from pulse.generation.demand import generate_demand
from pulse.generation.supply import generate_supply, load_supply_rules, shift_hours


@pytest.fixture(scope="module")
def world():
    calendar, _, demand = generate_demand(weeks=6)
    partners, partner_days, supply = generate_supply(calendar)
    city = load_city()
    ztype = {k: v["type"] for k, v in city["zones"].items()}
    return calendar, demand, partners, partner_days, supply, ztype


def pressure(demand, supply, calendar, ztype):
    """Partner-hours needed (rides/2 + orders/3) vs baseline online partners."""
    need = demand.pivot_table(index=["date", "hour", "zone_id"], columns="service",
                              values="demand", aggfunc="sum").fillna(0)
    need = (need["mobility"] / 2 + need["food"] / 3).rename("needed")
    sup = supply.groupby(["date", "hour", "zone_id"])["online_partners"].sum()
    m = pd.concat([need, sup], axis=1).fillna(0).reset_index()
    m = m.merge(calendar[["date", "is_weekend", "is_rain"]], on="date")
    m["ztype"] = m["zone_id"].map(ztype)
    return m


def test_fleet_mix_is_about_70_30(world):
    _, _, partners, *_ = world
    share = (partners["vehicle_type"] == "two_wheeler").mean()
    assert 0.65 < share < 0.75


def test_four_wheelers_are_mobility_only(world):
    _, _, partners, *_ = world
    fw = partners[partners["vehicle_type"] == "four_wheeler"]
    assert (fw["eligible_services"] == "mobility").all()


def test_partners_live_in_residential_and_mixed_zones(world):
    """S-01: supply starts where partners live, not where offices are."""
    *_, ztype = world
    partners = world[2]
    t = partners["home_zone"].map(ztype)
    assert t.isin(["residential", "mixed"]).mean() > 0.6
    assert (t == "office").mean() < 0.10


def test_every_hour_has_some_supply(world):
    rules = load_supply_rules()
    covered = set().union(*shift_hours(rules).values())
    assert covered == set(range(24))


def test_rain_cuts_two_wheeler_supply_only(world):
    """S-04: rain reduces two-wheeler log-ins ~20%; four-wheelers unchanged."""
    calendar, _, _, _, supply, _ = world
    s = supply.merge(calendar[["date", "is_weekend", "is_rain"]], on="date")
    s = s[~s["is_weekend"]]
    daily = s.groupby(["date", "is_rain", "vehicle_type"])["online_partners"].sum().reset_index()
    avg = daily.groupby(["vehicle_type", "is_rain"])["online_partners"].mean()
    assert avg["two_wheeler", True] / avg["two_wheeler", False] == pytest.approx(0.8, abs=0.06)
    assert avg["four_wheeler", True] / avg["four_wheeler", False] == pytest.approx(1.0, abs=0.06)


def test_office_lunch_is_badly_undersupplied_at_home(world):
    """Planted truth 1: at weekday lunch, office zones need far more partners
    than live there, while residential zones have a surplus. This mismatch is
    what repositioning must fix."""
    calendar, demand, _, _, supply, ztype = world
    m = pressure(demand, supply, calendar, ztype)
    lunch = m[~m["is_weekend"] & m["hour"].isin([12, 13])].groupby("ztype")[["needed", "online_partners"]].sum()
    mpi = lunch["needed"] / lunch["online_partners"]
    assert mpi["office"] > 3
    assert mpi["residential"] < 1


def test_citywide_supply_is_tight_but_not_absurd_at_dinner(world):
    """City as a whole is roughly balanced at dinner: shortages are mostly about
    WHERE supply is, not how much exists."""
    calendar, demand, _, _, supply, ztype = world
    m = pressure(demand, supply, calendar, ztype)
    d = m[~m["is_weekend"] & m["hour"].isin([19, 20])]
    assert 0.8 < d["needed"].sum() / d["online_partners"].sum() < 1.3
