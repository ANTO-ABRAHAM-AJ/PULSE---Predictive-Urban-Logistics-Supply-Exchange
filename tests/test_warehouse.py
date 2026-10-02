"""Phase 4: star-schema transforms (no database needed for these tests)."""
import datetime as dt
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pulse.generation.demand import generate_demand
from pulse.generation.entities import assign_entities
from pulse.generation.events import simulate
from pulse.generation.supply import generate_supply
from pulse.generation.city import load_city, zones_frame
from pulse.warehouse import TABLE_ORDER, build_tables, check_integrity
from pulse.warehouse.load import connection_string, rows_for_insert, split_batches

SQL = Path(__file__).resolve().parents[1] / "04_Data_Warehouse" / "sql" / "02_create_tables.sql"


@pytest.fixture(scope="module")
def tables():
    calendar, _, demand = generate_demand(weeks=1)
    days = calendar.head(2)
    partners, partner_days, _ = generate_supply(calendar)
    demand = demand[demand["date"].isin(days["date"])]
    rides, orders, hourly = simulate(demand, days, partners,
                                     partner_days[partner_days["date"].isin(days["date"])])
    rides, orders, customers, restaurants = assign_entities(rides, orders)
    src = {"calendar": days, "zones": zones_frame(load_city()), "partners": partners,
           "customers": customers, "restaurants": restaurants, "rides": rides,
           "food_orders": orders, "partner_hourly": hourly}
    return build_tables(src), rides, orders


def sql_columns():
    """Column names per table, read from the CREATE TABLE statements."""
    text = SQL.read_text(encoding="utf-8")
    out = {}
    for name, body in re.findall(r"CREATE TABLE dw\.(\w+) \((.*?)\n\);", text, flags=re.S):
        cols = []
        for line in body.splitlines():
            m = re.match(r"\s+(\w+)\s+(INT|BIGINT|SMALLINT|TINYINT|DATE|DATETIME2|DECIMAL|VARCHAR|CHAR|BIT)", line)
            if m:
                cols.append(m.group(1))
        out[name] = cols
    return out


def test_every_table_matches_its_sql_definition(tables):
    t, *_ = tables
    defs = sql_columns()
    for name in TABLE_ORDER:
        assert list(t[name].columns) == defs[name], name


def test_keys_unique_and_foreign_keys_resolve(tables):
    t, *_ = tables
    assert check_integrity(t) == []


def test_row_counts_match_source(tables):
    t, rides, orders = tables
    assert len(t["Fact_Ride_Requests"]) == len(rides)
    assert len(t["Fact_Rides"]) == (rides["status"] == "completed").sum()
    assert len(t["Fact_Food_Orders"]) == len(orders)


def test_every_order_has_a_placed_event_and_one_ending(tables):
    t, *_ = tables
    ev = t["Fact_Delivery_Events"]
    per = ev.groupby("order_key")["event_type"].apply(set)
    assert per.apply(lambda s: "placed" in s).all()
    assert per.apply(lambda s: ("delivered" in s) != ("cancelled" in s)).all()


def test_platform_revenue_is_fare_minus_payout(tables):
    t, *_ = tables
    r = t["Fact_Rides"]
    assert np.allclose(r["platform_revenue"], r["fare"] - r["partner_payout"], atol=0.01)


def test_idle_plus_busy_equals_online(tables):
    t, *_ = tables
    a = t["Fact_Driver_Availability"]
    assert np.allclose(a["idle_minutes"] + a["busy_minutes"], a["online_minutes"], atol=0.01)


def test_rows_for_insert_turns_missing_values_into_none():
    df = pd.DataFrame({"a": pd.array([1, None], dtype="Int64"), "b": [1.5, np.nan],
                       "c": pd.to_datetime(["2026-06-01 10:00", None]), "d": [True, False]})
    rows = rows_for_insert(df)
    assert rows[1][:3] == (None, None, None)
    assert isinstance(rows[0][0], int) and isinstance(rows[0][3], bool)
    assert isinstance(rows[0][2], dt.datetime)


def test_sql_scripts_split_on_go():
    assert split_batches("SELECT 1;\nGO\nSELECT 2;\n  go  \nSELECT 3;") == \
        ["SELECT 1;", "SELECT 2;", "SELECT 3;"]


def test_connection_string_trusts_local_certificate():
    s = connection_string({"driver": "ODBC Driver 18 for SQL Server", "server": "localhost",
                           "database": "PULSE_DW", "trusted_connection": True,
                           "trust_server_certificate": True})
    assert "TrustServerCertificate=yes" in s and "Trusted_Connection=yes" in s
