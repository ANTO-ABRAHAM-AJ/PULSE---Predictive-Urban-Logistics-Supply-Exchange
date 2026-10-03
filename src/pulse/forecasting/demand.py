"""Week-ahead demand forecasts by zone x hour x service.

Validation design: models are fitted on the 12 history weeks and score the
4 holdout weeks. The benchmarks use demand 7-28 days earlier; the gradient-
boosting models use only what is known in advance — zone, service, hour,
day of week and scheduled events. Rain is an optional feature, and its model
is labelled separately, because a week-ahead rain forecast is not perfect in
reality. Recent-demand lags were tested as GBM features and made accuracy
worse (they add noise in a marketplace without trend), so they are left out.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

SERIES = ["zone_code", "service_code", "hour_of_day"]
LAGS = (7, 14, 21, 28)
CALENDAR_FEATURES = ["zone_code", "zone_type", "service_code", "hour_of_day", "day_of_week",
                     "is_weekend", "is_event_day"]
MODELS = ["Seasonal naive", "4-week mean", "History profile", "GBM calendar", "GBM + rain"]
BENCHMARK = "Seasonal naive"


def add_lag_features(df: pd.DataFrame, value: str = "demand", keys: list[str] = SERIES) -> pd.DataFrame:
    """Same-hour demand 7, 14, 21 and 28 days earlier, and their mean.
    Needs one row per series per day (a complete grid, zeros included)."""
    out = df.sort_values(keys + ["date_value"]).copy()
    g = out.groupby(keys, sort=False)[value]
    for k in LAGS:
        out[f"lag_{k}"] = g.shift(k)
    out["mean_4w"] = out[[f"lag_{k}" for k in LAGS]].mean(axis=1)
    return out


def _matrix(df: pd.DataFrame, features: list[str]) -> pd.DataFrame:
    X = df[features].copy()
    for c in X.columns:
        if X[c].dtype == object or c in ("zone_code", "zone_type", "service_code"):
            X[c] = X[c].astype("category")
        elif X[c].dtype == bool:
            X[c] = X[c].astype(int)
    return X


def fit_gbm(train: pd.DataFrame, features: list[str]):
    from sklearn.ensemble import HistGradientBoostingRegressor
    model = HistGradientBoostingRegressor(loss="poisson", max_iter=300, learning_rate=0.08,
                                          categorical_features="from_dtype", random_state=0)
    model.fit(_matrix(train, features), train["demand"])
    return model


def forecast_demand(history: pd.DataFrame) -> pd.DataFrame:
    """Return the holdout rows with one forecast column per model."""
    df = add_lag_features(history)
    for c in ("is_weekend", "is_rain_day", "is_event_day"):
        df[c] = df[c].astype(int)
    train = df[df["data_split"] == "history"].copy()
    test = df[df["data_split"] == "holdout"].copy()

    test["Seasonal naive"] = test["lag_7"]
    test["4-week mean"] = test["mean_4w"]
    profile = (df[df["data_split"] == "history"]
               .groupby(SERIES + ["is_weekend"])["demand"].mean().rename("History profile"))
    test = test.join(profile, on=SERIES + ["is_weekend"])

    # Categories must match between train and test.
    cats = {c: sorted(df[c].unique()) for c in ("zone_code", "zone_type", "service_code")}
    for frame in (train, test):
        for c, values in cats.items():
            frame[c] = pd.Categorical(frame[c], categories=values)

    gbm_cal = fit_gbm(train, CALENDAR_FEATURES)
    test["GBM calendar"] = gbm_cal.predict(_matrix(test, CALENDAR_FEATURES))
    rain_features = CALENDAR_FEATURES + ["is_rain_day"]
    gbm_rain = fit_gbm(train, rain_features)
    test["GBM + rain"] = gbm_rain.predict(_matrix(test, rain_features))
    for m in MODELS:
        test[m] = test[m].astype(float).clip(lower=0)
    for c in cats:                                   # back to plain text for downstream use
        test[c] = test[c].astype(str)
    return test
