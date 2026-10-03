"""Regenerate the result tables in 03_Data_Engineering/Generation_Results.md.

Needs the full dataset (python scripts/build_all.py).

Usage:
    python scripts/report_generation.py      (about 30 seconds)
"""
from pathlib import Path

import numpy as np
import pandas as pd

from pulse.reporting import fill_block, inr, table

ROOT = Path(__file__).resolve().parents[1]
P = ROOT / "data" / "processed"
DOC = ROOT / "03_Data_Engineering" / "Generation_Results.md"


def load():
    cal = pd.read_csv(P / "calendar.csv", parse_dates=["date"])
    zones = pd.read_csv(P / "zones.csv")
    ztype = dict(zip(zones["zone_id"], zones["type"]))
    demand = pd.read_csv(P / "demand_hourly.csv", parse_dates=["date"]).merge(
        cal[["date", "is_weekend", "is_rain", "is_event"]], on="date")
    demand["ztype"] = demand["zone_id"].map(ztype)
    rides = pd.read_csv(P / "rides.csv", parse_dates=["request_ts", "assigned_ts", "pickup_ts", "dropoff_ts"],
                        low_memory=False)
    orders = pd.read_csv(P / "food_orders.csv", parse_dates=["placed_ts", "assigned_ts", "delivered_ts"],
                         low_memory=False)
    hourly = pd.read_csv(P / "partner_hourly.csv")
    supply = pd.read_csv(P / "supply_hourly.csv", parse_dates=["date"])
    other = {f: len(pd.read_csv(P / f"{f}.csv")) for f in ("partners", "customers", "restaurants")}
    return cal, zones, ztype, demand, rides, orders, hourly, supply, other


def overview(cal, zones, demand, rides, orders, other):
    rows = [("Simulated period", f"{cal['date'].min():%d %b %Y} – {cal['date'].max():%d %b %Y} "
                                 f"({len(cal)} days: {(cal['split'] == 'history').sum()} history, "
                                 f"{(cal['split'] == 'holdout').sum()} holdout)"),
            ("Zones", f"{len(zones)} Bengaluru zones"),
            ("Ride requests", f"{len(rides):,}"),
            ("Food orders", f"{len(orders):,}"),
            ("Jobs per day (average)", f"{(len(rides) + len(orders)) / len(cal):,.0f}"),
            ("Partners", f"{other['partners']:,}"),
            ("Customers", f"{other['customers']:,}"),
            ("Restaurants", f"{other['restaurants']:,}"),
            ("Rain days / event days", f"{int(cal['is_rain'].sum())} / {int(cal['is_event'].sum())}")]
    return table(pd.DataFrame(rows, columns=["Item", "Value"]))


def _mean(d, **f):
    m = pd.Series(True, index=d.index)
    for c, v in f.items():
        m &= d[c].isin(v) if isinstance(v, list) else d[c] == v
    return d.loc[m, "demand"].mean()


def planted(demand):
    wk, we = demand[~demand.is_weekend], demand[demand.is_weekend]
    food, mob = demand[demand.service == "food"], demand[demand.service == "mobility"]
    off_food = food[(food.ztype == "office") & food.hour.isin([12, 13])]
    off_mob = mob[(mob.ztype == "office") & ~mob.is_weekend]
    res_food = food[(food.ztype == "residential") & ~food.is_weekend]
    rc = food[(food.ztype == "restaurant_cluster") & food.hour.isin([22, 23])]
    daily = food[~food.is_weekend].groupby(["date", "is_rain"])["demand"].sum().reset_index()
    cbd = mob[(mob.zone_id == "CBD") & mob.hour.isin([21, 22, 23])]
    wk_mob = wk[wk.service == "mobility"].groupby("hour")["demand"].mean()

    checks = [
        ("Weekday commute peaks (D-01)", "Two busiest weekday ride hours",
         ", ".join(f"{h}:00" for h in sorted(wk_mob.nlargest(2).index)), "in 08–10 or 17–20",
         set(wk_mob.nlargest(2).index) <= {8, 9, 10, 17, 18, 19, 20}),
        ("Office lunch rush (D-03)", "Office lunch orders, weekday ÷ weekend",
         f"{off_food[~off_food.is_weekend].demand.mean() / off_food[off_food.is_weekend].demand.mean():.1f}×",
         "> 4×", None),
        ("Office evening exodus (D-03)", "Office rides, 17–19 ÷ 08–10 (weekday)",
         f"{_mean(off_mob, hour=[17, 18, 19]) / _mean(off_mob, hour=[8, 9, 10]):.1f}×", "> 1.5×", None),
        ("Residential dinner (D-04)", "Residential orders, 19–21 ÷ 12–13 (weekday)",
         f"{_mean(res_food, hour=[19, 20, 21]) / _mean(res_food, hour=[12, 13]):.1f}×", "> 1.5×", None),
        ("Restaurant-cluster nights (D-05)", "Late-night orders, weekend ÷ weekday",
         f"{rc[rc.is_weekend].demand.mean() / rc[~rc.is_weekend].demand.mean():.1f}×", "> 1.5×", None),
        ("Rain lifts food (D-08)", "Weekday food orders, rain ÷ dry day",
         f"{daily[daily.is_rain].demand.mean() / daily[~daily.is_rain].demand.mean():.2f}×", "> 1.15×", None),
        ("Stadium nights (D-10)", "CBD rides 21–24, event ÷ normal night",
         f"{cbd[cbd.is_event].demand.mean() / cbd[~cbd.is_event].demand.mean():.1f}×", "> 1.8×", None),
    ]
    rows = []
    for name, metric, value, threshold, ok in checks:
        if ok is None:
            ok = float(value.rstrip("×")) > float(threshold.strip("> ×"))
        rows.append({"Pattern": name, "Measure": metric, "Observed": value,
                     "Required": threshold, "Recovered": "✅" if ok else "❌"})
    return table(pd.DataFrame(rows))


def operations(rides, orders, hourly):
    c = rides[rides.status == "completed"]
    d = orders[orders.status == "delivered"]
    ride_busy = ((c.dropoff_ts - c.assigned_ts).dt.total_seconds() / 60).mean()
    food_busy = ((d.delivered_ts - d.assigned_ts).dt.total_seconds() / 60).mean()
    rows = [
        ("Ride completion rate", f"{(rides.status == 'completed').mean():.1%}"),
        ("Rides cancelled — no partner", f"{(rides.status == 'cancelled_no_partner').mean():.1%}"),
        ("Rides cancelled — customer", f"{(rides.status == 'cancelled_customer').mean():.1%}"),
        ("Average pickup ETA (completed rides)", f"{c.pickup_eta_min.mean():.1f} min"),
        ("Average trip distance", f"{c.trip_km.mean():.1f} km"),
        ("Food delivery rate", f"{(orders.status == 'delivered').mean():.1%}"),
        ("Average order-to-door time", f"{((d.delivered_ts - d.placed_ts).dt.total_seconds() / 60).mean():.1f} min"),
        ("Average order value", inr(orders.order_value.mean())),
        ("Partner utilization (busy ÷ online)", f"{hourly.busy_min.sum() / hourly.online_min.sum():.1%}"),
        ("Partner busy time per ride / delivery", f"{ride_busy:.0f} min / {food_busy:.0f} min"),
    ]
    return table(pd.DataFrame(rows, columns=["KPI", "Value"]))


def lunch_pressure(demand, supply, cal, ztype):
    need = demand.pivot_table(index=["date", "hour", "zone_id"], columns="service",
                              values="demand", aggfunc="sum").fillna(0)
    need = (need["mobility"] / 2 + need["food"] / 3).rename("needed")
    sup = supply.groupby(["date", "hour", "zone_id"])["online_partners"].sum()
    m = pd.concat([need, sup], axis=1).fillna(0).reset_index().merge(
        cal[["date", "is_weekend"]], on="date")
    m = m[~m.is_weekend & m.hour.isin([12, 13])]
    m["Zone type"] = m["zone_id"].map(ztype)
    g = m.groupby("Zone type")[["needed", "online_partners"]].sum()
    days = m["date"].nunique()
    g = (g / (days * 2)).rename(columns={"needed": "Partners needed / hour",
                                         "online_partners": "Partners living there / hour"})
    g["Pressure (needed ÷ available)"] = g.iloc[:, 0] / g.iloc[:, 1]
    g["State"] = np.select([g.iloc[:, 2] > 1.10, g.iloc[:, 2] < 0.80],
                           ["Under-supplied", "Over-supplied"], "Balanced")
    g = g.sort_values("Pressure (needed ÷ available)", ascending=False)
    city = g.iloc[:, 0].sum() / g.iloc[:, 1].sum()
    return (table(g, {"Partners needed / hour": "{:,.0f}", "Partners living there / hour": "{:,.0f}",
                      "Pressure (needed ÷ available)": "{:.2f}"}, index=True)
            + f"\n\nCitywide pressure at lunch: **{city:.2f}** (thresholds from KPI_Dictionary.md: "
              f"> 1.10 under-supplied, < 0.80 over-supplied).")


def evening_rides(rides, cal, ztype):
    r = rides.copy()
    r["date"] = r.request_ts.dt.normalize()
    r = r.merge(cal[["date", "is_weekend"]], on="date")
    r = r[~r.is_weekend & r.request_ts.dt.hour.isin([17, 18, 19])]
    r["Zone type"] = r.zone_id.map(ztype)
    g = r.groupby("Zone type").agg(
        **{"Ride requests": ("status", "size"),
           "Completed": ("status", lambda s: (s == "completed").mean()),
           "No partner": ("status", lambda s: (s == "cancelled_no_partner").mean())})
    g = g.sort_values("Completed")
    return table(g, {"Ride requests": "{:,}", "Completed": "{:.1%}", "No partner": "{:.1%}"}, index=True)


def main() -> None:
    cal, zones, ztype, demand, rides, orders, hourly, supply, other = load()
    fill_block(DOC, "overview", overview(cal, zones, demand, rides, orders, other))
    fill_block(DOC, "planted", planted(demand))
    fill_block(DOC, "operations", operations(rides, orders, hourly))
    fill_block(DOC, "lunch_pressure", lunch_pressure(demand, supply, cal, ztype))
    fill_block(DOC, "evening_rides", evening_rides(rides, cal, ztype))
    print(f"Updated {DOC.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
