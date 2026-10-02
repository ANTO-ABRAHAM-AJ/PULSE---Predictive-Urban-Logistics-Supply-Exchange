"""Stage 5a: the generated city must show the planted patterns (Assumptions.md §4, §8).

Every check reads REALIZED demand only, the same way later analytics will.
"""
import numpy as np
import pandas as pd
import pytest

from pulse.generation.city import (load_city, max_reposition_km, road_km_matrix,
                                   travel_minutes)
from pulse.generation.demand import generate_demand


@pytest.fixture(scope="module")
def city():
    return load_city()


@pytest.fixture(scope="module")
def data(city):
    calendar, truth, realized = generate_demand(weeks=6)
    d = realized.merge(calendar[["date", "is_weekend", "is_rain", "is_event"]], on="date")
    d["ztype"] = d["zone_id"].map({k: v["type"] for k, v in city["zones"].items()})
    return calendar, truth, d


def mean_demand(d, **filters):
    m = pd.Series(True, index=d.index)
    for col, val in filters.items():
        m &= d[col].isin(val) if isinstance(val, (list, range, set)) else d[col] == val
    return d.loc[m, "demand"].mean()


# --- geography -------------------------------------------------------------

def test_distance_matrix_is_symmetric_with_zero_diagonal(city):
    km = road_km_matrix(city)
    assert np.allclose(km.values, km.values.T)
    assert (np.diag(km.values) == 0).all()


def test_airport_is_out_of_reach_like_toy_zone_e(city):
    """KIA is >20 minutes from every other zone even off-peak, so supply can't
    be repositioned there - the real-city version of the toy's Zone E."""
    km = road_km_matrix(city)
    reach = max_reposition_km(city, hour=14, is_weekend=False)
    others = km.loc["KIA"].drop("KIA")
    assert (others > reach).all()


def test_peak_traffic_shrinks_reach(city):
    assert travel_minutes(city, 10, hour=9, is_weekend=False) > \
           travel_minutes(city, 10, hour=14, is_weekend=False)


# --- reproducibility & noise ----------------------------------------------

def test_same_seed_same_data():
    _, _, a = generate_demand(seed=1, weeks=1)
    _, _, b = generate_demand(seed=1, weeks=1)
    assert a.equals(b)


def test_realized_demand_is_poisson_around_truth(data):
    _, truth, d = data
    assert d["demand"].sum() == pytest.approx(truth["expected"].sum(), rel=0.01)


# --- planted demand truths --------------------------------------------------

def test_weekday_mobility_peaks_at_commute_hours(data):
    """D-01: the two busiest weekday mobility hours fall in 08-10 or 17-20."""
    _, _, d = data
    by_hour = d[(d.service == "mobility") & ~d.is_weekend].groupby("hour")["demand"].mean()
    top2 = set(by_hour.nlargest(2).index)
    assert top2 <= {8, 9, 10, 17, 18, 19, 20}


def test_food_has_lunch_and_dinner_peaks(data):
    """D-02: lunch and dinner are each far busier than mid-afternoon."""
    _, _, d = data
    food = d[d.service == "food"]
    lunch = mean_demand(food, hour=[12, 13])
    dinner = mean_demand(food, hour=[19, 20, 21])
    afternoon = mean_demand(food, hour=[15, 16])
    assert lunch > 2.5 * afternoon and dinner > 2.5 * afternoon


def test_office_lunch_rush_collapses_on_weekends(data):
    """D-03 / planted truth 1: office weekday lunch food >> weekend."""
    _, _, d = data
    f = d[(d.service == "food") & (d.ztype == "office") & d.hour.isin([12, 13])]
    assert f[~f.is_weekend]["demand"].mean() > 4 * f[f.is_weekend]["demand"].mean()


def test_office_evening_mobility_exodus(data):
    """Planted truth 2: office zones' weekday evening mobility beats morning."""
    _, _, d = data
    m = d[(d.service == "mobility") & (d.ztype == "office") & ~d.is_weekend]
    assert mean_demand(m, hour=[17, 18, 19]) > 1.5 * mean_demand(m, hour=[8, 9, 10])


def test_residential_food_is_dinner_heavy(data):
    """D-04 / planted truth 3."""
    _, _, d = data
    f = d[(d.service == "food") & (d.ztype == "residential") & ~d.is_weekend]
    assert mean_demand(f, hour=[19, 20, 21]) > 1.5 * mean_demand(f, hour=[12, 13])


def test_restaurant_clusters_peak_on_weekend_nights(data):
    """D-05 / planted truth 5."""
    _, _, d = data
    f = d[(d.service == "food") & (d.ztype == "restaurant_cluster") & d.hour.isin([22, 23])]
    assert f[f.is_weekend]["demand"].mean() > 1.5 * f[~f.is_weekend]["demand"].mean()


def test_rain_raises_food_demand(data):
    """D-08 / planted truth 4 (demand side): food +30% on rain days."""
    _, _, d = data
    daily = d[d.service == "food"].groupby(["date", "is_rain"])["demand"].sum().reset_index()
    weekday_dates = d.loc[~d.is_weekend, "date"].unique()
    daily = daily[daily.date.isin(weekday_dates)]
    ratio = daily[daily.is_rain]["demand"].mean() / daily[~daily.is_rain]["demand"].mean()
    assert ratio > 1.15


def test_event_nights_spike_cbd_mobility(data):
    """D-10: stadium nights more than double late CBD mobility."""
    _, _, d = data
    m = d[(d.service == "mobility") & (d.zone_id == "CBD") & d.hour.isin([21, 22, 23])]
    assert m[m.is_event]["demand"].mean() > 1.8 * m[~m.is_event]["demand"].mean()
