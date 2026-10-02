"""Turn the generated CSVs into star-schema tables (pure pandas, no database).

Every function returns a DataFrame whose columns match 02_create_tables.sql
exactly, in the same order. Surrogate keys are assigned here, deterministically,
so loads are reproducible.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from pulse.generation.city import CITY_DIR

TABLE_ORDER = [  # load order respects foreign keys
    "Dim_Time", "Dim_Zone", "Dim_Service", "Dim_Vehicle", "Dim_Driver",
    "Dim_Customer", "Dim_Restaurant",
    "Fact_Ride_Requests", "Fact_Rides", "Fact_Food_Orders",
    "Fact_Delivery_Events", "Fact_Driver_Availability",
]

SERVICES = {"mobility": (1, "Mobility"), "food": (2, "Food Delivery")}
VEHICLES = {"two_wheeler": (1, "Two-wheeler", True, True),
            "four_wheeler": (2, "Four-wheeler cab", True, False)}

# (table, column) -> (referenced table, referenced key). Mirrors the SQL FKs.
FOREIGN_KEYS = {
    ("Dim_Driver", "vehicle_key"): ("Dim_Vehicle", "vehicle_key"),
    ("Dim_Driver", "home_zone_key"): ("Dim_Zone", "zone_key"),
    ("Dim_Customer", "home_zone_key"): ("Dim_Zone", "zone_key"),
    ("Dim_Restaurant", "zone_key"): ("Dim_Zone", "zone_key"),
    ("Fact_Ride_Requests", "time_key"): ("Dim_Time", "time_key"),
    ("Fact_Ride_Requests", "customer_key"): ("Dim_Customer", "customer_key"),
    ("Fact_Ride_Requests", "pickup_zone_key"): ("Dim_Zone", "zone_key"),
    ("Fact_Ride_Requests", "dropoff_zone_key"): ("Dim_Zone", "zone_key"),
    ("Fact_Ride_Requests", "driver_key"): ("Dim_Driver", "driver_key"),
    ("Fact_Ride_Requests", "vehicle_key"): ("Dim_Vehicle", "vehicle_key"),
    ("Fact_Rides", "ride_request_key"): ("Fact_Ride_Requests", "ride_request_key"),
    ("Fact_Rides", "time_key"): ("Dim_Time", "time_key"),
    ("Fact_Rides", "customer_key"): ("Dim_Customer", "customer_key"),
    ("Fact_Rides", "driver_key"): ("Dim_Driver", "driver_key"),
    ("Fact_Rides", "vehicle_key"): ("Dim_Vehicle", "vehicle_key"),
    ("Fact_Rides", "pickup_zone_key"): ("Dim_Zone", "zone_key"),
    ("Fact_Rides", "dropoff_zone_key"): ("Dim_Zone", "zone_key"),
    ("Fact_Food_Orders", "time_key"): ("Dim_Time", "time_key"),
    ("Fact_Food_Orders", "customer_key"): ("Dim_Customer", "customer_key"),
    ("Fact_Food_Orders", "customer_zone_key"): ("Dim_Zone", "zone_key"),
    ("Fact_Food_Orders", "restaurant_key"): ("Dim_Restaurant", "restaurant_key"),
    ("Fact_Food_Orders", "restaurant_zone_key"): ("Dim_Zone", "zone_key"),
    ("Fact_Food_Orders", "driver_key"): ("Dim_Driver", "driver_key"),
    ("Fact_Delivery_Events", "order_key"): ("Fact_Food_Orders", "order_key"),
    ("Fact_Delivery_Events", "time_key"): ("Dim_Time", "time_key"),
    ("Fact_Delivery_Events", "zone_key"): ("Dim_Zone", "zone_key"),
    ("Fact_Delivery_Events", "driver_key"): ("Dim_Driver", "driver_key"),
    ("Fact_Driver_Availability", "time_key"): ("Dim_Time", "time_key"),
    ("Fact_Driver_Availability", "driver_key"): ("Dim_Driver", "driver_key"),
    ("Fact_Driver_Availability", "zone_key"): ("Dim_Zone", "zone_key"),
    ("Fact_Driver_Availability", "vehicle_key"): ("Dim_Vehicle", "vehicle_key"),
}


def check_integrity(tables: dict[str, pd.DataFrame]) -> list[str]:
    """Return a list of problems (empty = clean): PK duplicates and orphan FKs."""
    problems = []
    for name in TABLE_ORDER:
        pk = tables[name].columns[0]
        if tables[name][pk].duplicated().any():
            problems.append(f"{name}.{pk} has duplicates")
    for (tbl, col), (ref, rcol) in FOREIGN_KEYS.items():
        vals = tables[tbl][col].dropna()
        missing = ~vals.isin(tables[ref][rcol])
        if missing.any():
            problems.append(f"{tbl}.{col}: {int(missing.sum())} values not in {ref}.{rcol}")
    return problems


TS = {"rides": ["request_ts", "assigned_ts", "pickup_ts", "dropoff_ts"],
      "food_orders": ["placed_ts", "assigned_ts", "ready_ts", "picked_ts", "delivered_ts"]}


def read_sources(folder: Path | str) -> dict[str, pd.DataFrame]:
    folder = Path(folder)
    src = {
        "calendar": pd.read_csv(folder / "calendar.csv", parse_dates=["date"]),
        "zones": pd.read_csv(folder / "zones.csv"),
        "partners": pd.read_csv(folder / "partners.csv"),
        "customers": pd.read_csv(folder / "customers.csv"),
        "restaurants": pd.read_csv(folder / "restaurants.csv"),
        "rides": pd.read_csv(folder / "rides.csv", parse_dates=TS["rides"], low_memory=False),
        "food_orders": pd.read_csv(folder / "food_orders.csv", parse_dates=TS["food_orders"],
                                   low_memory=False),
        "partner_hourly": pd.read_csv(folder / "partner_hourly.csv", parse_dates=["date"]),
    }
    return src


def time_key(ts: pd.Series) -> pd.Series:
    """yyyymmddhh as int; NaT stays missing."""
    return (ts.dt.year * 1_000_000 + ts.dt.month * 10_000 + ts.dt.day * 100
            + ts.dt.hour).astype("Int64")


def _minutes(a: pd.Series, b: pd.Series) -> pd.Series:
    return ((b - a).dt.total_seconds() / 60).round(2)


def _key_map(codes: pd.Series) -> dict:
    return {c: i for i, c in enumerate(codes, start=1)}


def build_tables(src: dict[str, pd.DataFrame], config_dir: Path | str = CITY_DIR) -> dict[str, pd.DataFrame]:
    with open(Path(config_dir) / "zones.yaml", encoding="utf-8") as f:
        peak_hours = set(yaml.safe_load(f)["travel"]["weekday_peak_hours"])

    t = {}

    # ---------------- dimensions ----------------
    cal = src["calendar"].copy()
    # One extra "spill" day so jobs that finish after midnight on the last
    # simulated day still have a valid time_key.
    spill = cal.iloc[[-1]].copy()
    spill["date"] = spill["date"] + pd.Timedelta(days=1)
    spill["day_of_week"] = spill["date"].dt.dayofweek
    spill["is_weekend"] = spill["day_of_week"] >= 5
    spill[["is_rain", "is_event"]] = False
    spill["split"] = "spill"
    cal = pd.concat([cal, spill], ignore_index=True)
    dt = cal.loc[cal.index.repeat(24)].reset_index(drop=True)
    dt["hour_of_day"] = np.tile(np.arange(24), len(cal))
    stamp = dt["date"] + pd.to_timedelta(dt["hour_of_day"], unit="h")
    start = cal["date"].min()
    t["Dim_Time"] = pd.DataFrame({
        "time_key": time_key(stamp).astype(int),
        "date_value": dt["date"].dt.date,
        "hour_of_day": dt["hour_of_day"],
        "day_of_week": dt["day_of_week"] + 1,
        "day_name": dt["date"].dt.day_name(),
        "week_number": ((dt["date"] - start).dt.days // 7 + 1),
        "is_weekend": dt["is_weekend"].astype(bool),
        "is_peak_hour": (~dt["is_weekend"].astype(bool)) & dt["hour_of_day"].isin(peak_hours),
        "is_rain_day": dt["is_rain"].astype(bool),
        "is_event_day": dt["is_event"].astype(bool),
        "data_split": dt["split"],
    })

    z = src["zones"]
    zone_key = _key_map(z["zone_id"])
    t["Dim_Zone"] = pd.DataFrame({
        "zone_key": z["zone_id"].map(zone_key), "zone_code": z["zone_id"], "zone_name": z["name"],
        "zone_type": z["type"], "latitude": z["lat"], "longitude": z["lon"], "city": "Bengaluru"})

    t["Dim_Service"] = pd.DataFrame(
        [{"service_key": k, "service_code": c, "service_name": n} for c, (k, n) in SERVICES.items()])
    t["Dim_Vehicle"] = pd.DataFrame(
        [{"vehicle_key": k, "vehicle_code": c, "vehicle_name": n, "can_mobility": m, "can_food": f}
         for c, (k, n, m, f) in VEHICLES.items()])
    vehicle_key = {c: v[0] for c, v in VEHICLES.items()}

    p = src["partners"]
    driver_key = _key_map(p["partner_id"])
    t["Dim_Driver"] = pd.DataFrame({
        "driver_key": p["partner_id"].map(driver_key), "partner_code": p["partner_id"],
        "vehicle_key": p["vehicle_type"].map(vehicle_key), "home_zone_key": p["home_zone"].map(zone_key),
        "shift_type": p["shift_type"]})
    partner_vehicle = dict(zip(p["partner_id"], p["vehicle_type"].map(vehicle_key)))

    c = src["customers"]
    customer_key = _key_map(c["customer_id"])
    t["Dim_Customer"] = pd.DataFrame({
        "customer_key": c["customer_id"].map(customer_key), "customer_code": c["customer_id"],
        "home_zone_key": c["home_zone_id"].map(zone_key)})

    r = src["restaurants"]
    restaurant_key = _key_map(r["restaurant_id"])
    t["Dim_Restaurant"] = pd.DataFrame({
        "restaurant_key": r["restaurant_id"].map(restaurant_key), "restaurant_code": r["restaurant_id"],
        "zone_key": r["zone_id"].map(zone_key), "cuisine": r["cuisine"]})

    # ---------------- mobility facts ----------------
    rd = src["rides"]
    req_key = pd.Series(np.arange(1, len(rd) + 1), index=rd.index)
    completed = rd["status"] == "completed"
    t["Fact_Ride_Requests"] = pd.DataFrame({
        "ride_request_key": req_key,
        "request_code": rd["request_id"],
        "time_key": time_key(rd["request_ts"]),
        "customer_key": rd["customer_id"].map(customer_key),
        "pickup_zone_key": rd["zone_id"].map(zone_key),
        "dropoff_zone_key": rd["dest_zone_id"].map(zone_key),
        "driver_key": rd["partner_id"].map(driver_key).astype("Int64"),
        "vehicle_key": rd["vehicle_type"].map(vehicle_key).astype("Int64"),
        "request_ts": rd["request_ts"], "assigned_ts": rd["assigned_ts"],
        "request_status": rd["status"], "is_completed": completed,
        "requested_trip_km": rd["trip_km"], "pickup_km": rd["pickup_km"],
        "pickup_eta_min": rd["pickup_eta_min"]})

    cr = rd[completed]
    t["Fact_Rides"] = pd.DataFrame({
        "ride_key": np.arange(1, len(cr) + 1),
        "ride_request_key": req_key[completed].to_numpy(),
        "time_key": time_key(cr["request_ts"]).to_numpy(),
        "customer_key": cr["customer_id"].map(customer_key).to_numpy(),
        "driver_key": cr["partner_id"].map(driver_key).to_numpy(),
        "vehicle_key": cr["vehicle_type"].map(vehicle_key).to_numpy(),
        "pickup_zone_key": cr["zone_id"].map(zone_key).to_numpy(),
        "dropoff_zone_key": cr["dest_zone_id"].map(zone_key).to_numpy(),
        "pickup_ts": cr["pickup_ts"].to_numpy(), "dropoff_ts": cr["dropoff_ts"].to_numpy(),
        "trip_km": cr["trip_km"].to_numpy(),
        "trip_minutes": _minutes(cr["pickup_ts"], cr["dropoff_ts"]).to_numpy(),
        "pickup_km": cr["pickup_km"].to_numpy(),
        "fare": cr["fare"].to_numpy(), "partner_payout": cr["partner_payout"].to_numpy(),
        "platform_revenue": (cr["fare"] - cr["partner_payout"]).round(2).to_numpy()})

    # ---------------- food facts ----------------
    fo = src["food_orders"]
    order_key = pd.Series(np.arange(1, len(fo) + 1), index=fo.index)
    delivered = fo["status"] == "delivered"
    revenue = (fo["commission"] + fo["delivery_fee"] - fo["partner_payout"]).round(2)
    t["Fact_Food_Orders"] = pd.DataFrame({
        "order_key": order_key, "order_code": fo["order_id"],
        "time_key": time_key(fo["placed_ts"]),
        "customer_key": fo["customer_id"].map(customer_key),
        "customer_zone_key": fo["zone_id"].map(zone_key),
        "restaurant_key": fo["restaurant_id"].map(restaurant_key),
        "restaurant_zone_key": fo["restaurant_zone_id"].map(zone_key),
        "driver_key": fo["partner_id"].map(driver_key).astype("Int64"),
        "placed_ts": fo["placed_ts"], "assigned_ts": fo["assigned_ts"], "ready_ts": fo["ready_ts"],
        "picked_ts": fo["picked_ts"], "delivered_ts": fo["delivered_ts"],
        "order_status": fo["status"], "is_delivered": delivered,
        "order_value": fo["order_value"], "commission": fo["commission"],
        "delivery_fee": fo["delivery_fee"], "partner_payout": fo["partner_payout"],
        "platform_revenue": revenue.where(delivered),
        "pickup_km": fo["pickup_km"], "delivery_km": fo["delivery_km"],
        "prep_minutes": _minutes(fo["placed_ts"], fo["ready_ts"]),
        "delivery_minutes": _minutes(fo["placed_ts"], fo["delivered_ts"])})

    t["Fact_Delivery_Events"] = _delivery_events(fo, order_key, zone_key, driver_key)

    # ---------------- supply fact ----------------
    ph = src["partner_hourly"]
    stamp = ph["date"] + pd.to_timedelta(ph["hour"], unit="h")
    t["Fact_Driver_Availability"] = pd.DataFrame({
        "availability_key": np.arange(1, len(ph) + 1, dtype=np.int64),
        "time_key": time_key(stamp).astype(int),
        "driver_key": ph["partner_id"].map(driver_key),
        "zone_key": ph["zone_id"].map(zone_key),
        "vehicle_key": ph["partner_id"].map(partner_vehicle),
        "online_minutes": ph["online_min"], "busy_minutes": ph["busy_min"],
        "idle_minutes": (ph["online_min"] - ph["busy_min"]).round(2),
        "empty_km": ph["empty_km"]})
    return t


def _delivery_events(fo, order_key, zone_key, driver_key) -> pd.DataFrame:
    """Long table of order milestones. A cancellation is stamped at the last
    known milestone before it (approximation: exact cancel time isn't simulated)."""
    cust_zone = fo["zone_id"].map(zone_key)
    rest_zone = fo["restaurant_zone_id"].map(zone_key)
    drv = fo["partner_id"].map(driver_key).astype("Int64")
    no_drv = pd.Series(pd.NA, index=fo.index, dtype="Int64")
    cancelled = fo["status"] != "delivered"
    cancel_ts = fo["assigned_ts"].fillna(fo["ready_ts"]).fillna(fo["placed_ts"])

    parts = [
        ("placed", 1, fo["placed_ts"], cust_zone, no_drv, fo["placed_ts"].notna()),
        ("assigned", 2, fo["assigned_ts"], rest_zone, drv, fo["assigned_ts"].notna()),
        ("food_ready", 3, fo["ready_ts"], rest_zone, no_drv, fo["ready_ts"].notna()),
        ("picked_up", 4, fo["picked_ts"], rest_zone, drv, fo["picked_ts"].notna()),
        ("delivered", 5, fo["delivered_ts"], cust_zone, drv, fo["delivered_ts"].notna()),
        ("cancelled", 6, cancel_ts, cust_zone, drv, cancelled),
    ]
    frames = []
    for name, seq, ts, zone, d, mask in parts:
        frames.append(pd.DataFrame({
            "order_key": order_key[mask].to_numpy(), "event_type": name, "event_seq": seq,
            "event_ts": ts[mask].to_numpy(), "zone_key": zone[mask].to_numpy(),
            "driver_key": d[mask].to_numpy()}))
    ev = pd.concat(frames, ignore_index=True).sort_values(["order_key", "event_seq"], ignore_index=True)
    ev["driver_key"] = ev["driver_key"].astype("Int64")
    ev.insert(0, "delivery_event_key", np.arange(1, len(ev) + 1, dtype=np.int64))
    ev.insert(5, "time_key", time_key(pd.to_datetime(ev["event_ts"])).astype(int))
    return ev[["delivery_event_key", "order_key", "event_type", "event_seq", "event_ts",
               "time_key", "zone_key", "driver_key"]]
