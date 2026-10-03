"""Week-ahead baseline supply forecasts: partners online by HOME zone x hour x vehicle.

Baseline supply is where partners start, before any dispatch or
repositioning — the starting point Phase 10 moves partners from.
"""
from __future__ import annotations

import pandas as pd

SERIES = ["zone_code", "vehicle_code", "hour_of_day"]
MODELS = ["Seasonal naive", "History profile", "History profile + rain"]


def forecast_supply(history: pd.DataFrame) -> pd.DataFrame:
    df = history.sort_values(SERIES + ["date_value"]).copy()
    for c in ("is_weekend", "is_rain_day"):
        df[c] = df[c].astype(int)
    df["lag_7"] = df.groupby(SERIES, sort=False)["partners"].shift(7)
    hist = df[df["data_split"] == "history"]
    test = df[df["data_split"] == "holdout"].copy()
    test["Seasonal naive"] = test["lag_7"]
    p = hist.groupby(SERIES + ["is_weekend"])["partners"].mean().rename("History profile")
    pr = hist.groupby(SERIES + ["is_weekend", "is_rain_day"])["partners"].mean().rename("History profile + rain")
    test = test.join(p, on=SERIES + ["is_weekend"]).join(pr, on=SERIES + ["is_weekend", "is_rain_day"])
    test["History profile + rain"] = test["History profile + rain"].fillna(test["History profile"])
    for m in MODELS:
        test[m] = test[m].astype(float).fillna(0)
    return test
