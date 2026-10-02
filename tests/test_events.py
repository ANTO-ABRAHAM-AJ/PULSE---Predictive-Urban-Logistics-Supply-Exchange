"""Stage 5b (part 2): event records must be internally consistent and show the
planted operational problems."""
import numpy as np
import pandas as pd
import pytest

from pulse.generation.city import load_city
from pulse.generation.demand import generate_demand
from pulse.generation.events import simulate
from pulse.generation.supply import generate_supply


@pytest.fixture(scope="module")
def sim():
    calendar, _, demand = generate_demand(weeks=1)
    partners, partner_days, _ = generate_supply(calendar)
    days = calendar.head(3)          # Mon-Wed keeps the test fast
    demand = demand[demand["date"].isin(days["date"])]
    rides, orders, hourly = simulate(demand, days, partners,
                                     partner_days[partner_days["date"].isin(days["date"])])
    ztype = {k: v["type"] for k, v in load_city()["zones"].items()}
    return demand, partners, rides, orders, hourly, ztype


def test_every_demand_unit_becomes_one_event(sim):
    demand, _, rides, orders, *_ = sim
    by = demand.groupby("service")["demand"].sum()
    assert len(rides) == by["mobility"] and len(orders) == by["food"]


def test_ride_timestamps_are_in_order(sim):
    rides = sim[2]
    c = rides[rides["status"] == "completed"]
    assert (c["assigned_ts"] >= c["request_ts"]).all()
    assert (c["pickup_ts"] >= c["assigned_ts"]).all()
    assert (c["dropoff_ts"] > c["pickup_ts"]).all()


def test_order_timestamps_are_in_order(sim):
    orders = sim[3]
    d = orders[orders["status"] == "delivered"]
    assert (d["picked_ts"] >= d["ready_ts"]).all()
    assert (d["delivered_ts"] > d["picked_ts"]).all()
    assert (d["ready_ts"] > d["placed_ts"]).all()


def test_four_wheelers_never_deliver_food(sim):
    _, partners, _, orders, *_ = sim
    fw = set(partners.loc[partners["vehicle_type"] == "four_wheeler", "partner_id"])
    assert not set(orders["partner_id"].dropna()) & fw


def test_no_partner_is_double_booked(sim):
    """A partner's completed jobs must never overlap in time."""
    _, _, rides, orders, *_ = sim
    jobs = pd.concat([
        rides.loc[rides.status == "completed", ["partner_id", "assigned_ts", "dropoff_ts"]]
             .rename(columns={"dropoff_ts": "end"}),
        orders.loc[orders.status == "delivered", ["partner_id", "assigned_ts", "delivered_ts"]]
              .rename(columns={"delivered_ts": "end"}),
    ]).sort_values(["partner_id", "assigned_ts"])
    prev_end = jobs.groupby("partner_id")["end"].shift()
    has_prev = prev_end.notna()
    assert (jobs.loc[has_prev, "assigned_ts"]
            >= prev_end[has_prev] - pd.Timedelta(seconds=1)).all()


def test_only_cancelled_jobs_lack_a_partner(sim):
    _, _, rides, orders, *_ = sim
    assert rides.loc[rides.status == "completed", "partner_id"].notna().all()
    assert orders.loc[orders.status == "delivered", "partner_id"].notna().all()
    assert rides.loc[rides.status == "cancelled_no_partner", "partner_id"].isna().all()


def test_economics_are_sane(sim):
    _, _, rides, orders, *_ = sim
    c = rides[rides.status == "completed"]
    assert (c["partner_payout"] < c["fare"]).all() and (c["fare"] > 0).all()
    d = orders[orders.status == "delivered"]
    assert (d["order_value"] > 0).all() and (d["partner_payout"] > 0).all()


def test_completion_rates_are_plausible(sim):
    _, _, rides, orders, *_ = sim
    assert 0.6 < (rides.status == "completed").mean() < 0.9
    assert 0.85 < (orders.status == "delivered").mean() < 0.98


def test_busy_time_never_exceeds_online_time(sim):
    hourly = sim[4]
    assert (hourly["busy_min"] <= hourly["online_min"]).all()


def test_office_evening_rides_fail_far_more_than_residential(sim):
    """Planted truth 2: the weekday evening exodus from office zones is badly
    under-served by status-quo dispatch."""
    *_, ztype = sim
    rides = sim[2].copy()
    rides["ztype"] = rides["zone_id"].map(ztype)
    eve = rides[rides["request_ts"].dt.hour.isin([17, 18, 19])]
    rate = eve.groupby("ztype")["status"].apply(lambda s: (s == "completed").mean())
    assert rate["office"] < rate["residential"] - 0.3


def test_idle_supply_coexists_with_cancellations(sim):
    """The core PULSE story: partners sit idle while requests elsewhere go
    unserved - a WHERE problem, not only a HOW-MANY problem."""
    _, _, rides, _, hourly, _ = sim
    eve = hourly[hourly["hour"].isin([17, 18, 19])]
    idle_share = 1 - eve["busy_min"].sum() / eve["online_min"].sum()
    no_partner = rides[rides["request_ts"].dt.hour.isin([17, 18, 19])]
    no_partner_share = (no_partner["status"] == "cancelled_no_partner").mean()
    assert idle_share > 0.2 and no_partner_share > 0.1
