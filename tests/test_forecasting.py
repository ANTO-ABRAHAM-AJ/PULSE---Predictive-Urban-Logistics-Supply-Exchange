"""Phase 9: forecasting logic on small synthetic series (no database needed)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pulse.forecasting import bias, skill, wape
from pulse.forecasting.demand import MODELS, add_lag_features, forecast_demand
from pulse.forecasting.pressure import forecast_pressure
from pulse.forecasting.supply import MODELS as SUPPLY_MODELS, forecast_supply

ROOT = Path(__file__).resolve().parents[1]


def test_metrics():
    assert wape([10, 10], [12, 8]) == pytest.approx(20.0)
    assert bias([10, 10], [12, 12]) == pytest.approx(20.0)
    assert skill(25.0, 50.0) == pytest.approx(50.0)


def _demand_frame(days=56, holdout_from=42, seed=0):
    """Two zones x two services x 24 hours; demand = hourly pattern x zone factor + noise."""
    rng = np.random.default_rng(seed)
    dates = pd.date_range("2026-06-01", periods=days, freq="D")
    rows = []
    for zi, zone in enumerate(["AAA", "BBB"]):
        for si, svc in enumerate(["mobility", "food"]):
            for d_i, d in enumerate(dates):
                for h in range(24):
                    rate = (3 + 5 * (h in (9, 18)) + 2 * zi) * (1 + si)
                    rows.append({"time_key": int(d.strftime("%Y%m%d")) * 100 + h, "date_value": d,
                                 "hour_of_day": h, "day_of_week": d.dayofweek + 1,
                                 "is_weekend": int(d.dayofweek >= 5), "is_rain_day": int(d_i % 5 == 0),
                                 "is_event_day": 0,
                                 "data_split": "history" if d_i < holdout_from else "holdout",
                                 "zone_key": zi + 1, "zone_code": zone, "zone_type": "mixed",
                                 "service_key": si + 1, "service_code": svc,
                                 "demand": int(rng.poisson(rate))})
    return pd.DataFrame(rows)


def test_lags_look_back_exactly_one_week():
    df = add_lag_features(_demand_frame(days=21, holdout_from=14))
    one = df[(df.zone_code == "AAA") & (df.service_code == "food") & (df.hour_of_day == 9)].reset_index()
    assert one.loc[7, "lag_7"] == one.loc[0, "demand"]
    assert np.isnan(one.loc[6, "lag_7"])


def test_models_forecast_only_holdout_and_beat_naive():
    fc = forecast_demand(_demand_frame())
    assert set(fc["data_split"]) == {"holdout"}
    for m in MODELS:
        assert fc[m].notna().all() and (fc[m] >= 0).all(), m
    # Learning the stable pattern must beat copying last week's noisy value.
    assert wape(fc["demand"], fc["History profile"]) < wape(fc["demand"], fc["Seasonal naive"])
    assert wape(fc["demand"], fc["GBM calendar"]) < wape(fc["demand"], fc["Seasonal naive"])


def test_supply_forecast_learns_shift_pattern():
    dates = pd.date_range("2026-06-01", periods=28, freq="D")
    rows = [{"time_key": int(d.strftime("%Y%m%d")) * 100 + h, "date_value": d, "hour_of_day": h,
             "day_of_week": d.dayofweek + 1, "is_weekend": int(d.dayofweek >= 5), "is_rain_day": 0,
             "data_split": "history" if i < 21 else "holdout", "zone_key": 1, "zone_code": "AAA",
             "vehicle_key": 1, "vehicle_code": "two_wheeler", "partners": 10 if 8 <= h <= 20 else 2}
            for i, d in enumerate(dates) for h in range(24)]
    sf = forecast_supply(pd.DataFrame(rows))
    for m in SUPPLY_MODELS:
        assert wape(sf["partners"], sf[m]) == pytest.approx(0.0), m


def test_pressure_flags_zone_hours_above_threshold():
    fc = pd.DataFrame({"time_key": [1, 1, 2], "zone_code": ["AAA", "AAA", "AAA"],
                       "service_code": ["mobility", "food", "mobility"], "GBM calendar": [6.0, 3.0, 2.0]})
    hist = pd.DataFrame({"time_key": [0, 0, 1, 2], "zone_key": 1, "zone_code": "AAA",
                         "hour_of_day": [5, 6, 5, 6], "is_weekend": 0,
                         "data_split": ["history", "history", "holdout", "holdout"],
                         "supply_hours": [3, 3, 3, 3], "work_hours": 0,
                         "pressure_state": ["x", "x", "Under-supplied", "Over-supplied"], "lost_jobs": [0, 0, 4, 0]})
    out = forecast_pressure(fc, hist).set_index("time_key")
    assert out.loc[1, "forecast_work_hours"] == pytest.approx(4.0)       # 6/2 + 3/3
    assert out.loc[1, "predicted_short"] == 1 and out.loc[1, "actual_short"] == 1   # 4/3 > 1.10
    assert out.loc[2, "predicted_short"] == 0                                        # 1/3


def test_report_documents_have_their_blocks():
    spec = importlib.util.spec_from_file_location("r9", ROOT / "scripts" / "report_phase9.py")
    r9 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(r9)
    docs = {"01_Forecasting_Approach.md": ["data"],
            "02_Demand_Forecast_Accuracy.md": ["models", "service", "A", "reconciliation", "headline"],
            "03_Supply_Forecast.md": ["models", "B", "headline"],
            "04_Pressure_Forecast.md": ["A", "B", "headline"]}
    for doc, blocks in docs.items():
        text = (ROOT / "09_Forecasting" / doc).read_text(encoding="utf-8")
        for b in blocks:
            assert f"<!-- AUTO:{b} -->" in text, (doc, b)
    a = pd.DataFrame({"Prediction": ["Predicted short", "Predicted not short"], "Actually short": [70, 30],
                      "Actually not short": [20, 880], "Jobs lost": [900, 100], "Share of lost jobs %": [90.0, 10.0]})
    assert "Precision **77.8%**" in r9.h_pressure(a) and "recall **70.0%**" in r9.h_pressure(a)
