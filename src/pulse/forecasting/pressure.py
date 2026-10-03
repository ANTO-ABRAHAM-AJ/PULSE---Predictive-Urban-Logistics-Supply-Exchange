"""Week-ahead pressure prediction: which zone-hours will be under-supplied?

forecast work hours   = forecast rides / 2 + forecast orders / 3 (Assumption O-01)
forecast supply hours = history profile of partners PRESENT in the zone
                        (location at hour start, as in Phase 8)
predicted short       = forecast MPI > 1.10, or forecast work with almost no supply
"""
from __future__ import annotations

import numpy as np
import pandas as pd

THRESHOLD = 1.10                       # KPI_Dictionary.md: Under-supplied above 1.10
JOBS_PER_HOUR = {"mobility": 2, "food": 3}


def forecast_pressure(demand_fc: pd.DataFrame, pressure_hist: pd.DataFrame,
                      model: str = "GBM calendar") -> pd.DataFrame:
    work = (demand_fc.assign(w=demand_fc[model] / demand_fc["service_code"].map(JOBS_PER_HOUR))
            .groupby(["time_key", "zone_code"], observed=True)["w"].sum().rename("forecast_work_hours"))
    ph = pressure_hist.copy()
    ph["is_weekend"] = ph["is_weekend"].astype(int)
    profile = (ph[ph["data_split"] == "history"]
               .groupby(["zone_code", "hour_of_day", "is_weekend"])["supply_hours"].mean()
               .rename("forecast_supply_hours"))
    out = (ph[ph["data_split"] == "holdout"]
           .join(work, on=["time_key", "zone_code"])
           .join(profile, on=["zone_code", "hour_of_day", "is_weekend"]))
    out["forecast_work_hours"] = out["forecast_work_hours"].fillna(0)
    out["forecast_supply_hours"] = out["forecast_supply_hours"].fillna(0)
    sup = out["forecast_supply_hours"]
    out["forecast_mpi"] = np.where(sup > 0, out["forecast_work_hours"] / sup.where(sup > 0), np.nan)
    out["predicted_short"] = (((sup < 0.5) & (out["forecast_work_hours"] > 0.3))
                              | (out["forecast_mpi"] > THRESHOLD)).astype(int)
    out["actual_short"] = (out["pressure_state"] == "Under-supplied").astype(int)
    return out
