"""Bengaluru zone geometry and travel times (Assumptions C-01 ... C-06)."""
from __future__ import annotations

import math
from pathlib import Path

import pandas as pd
import yaml

from pulse.utils.config import CONFIG_DIR

CITY_DIR = CONFIG_DIR / "bengaluru"


def load_city(config_dir: Path | str = CITY_DIR) -> dict:
    with open(Path(config_dir) / "zones.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def zones_frame(city: dict) -> pd.DataFrame:
    rows = [{"zone_id": zid, **z} for zid, z in city["zones"].items()]
    return pd.DataFrame(rows)


def road_km_matrix(city: dict) -> pd.DataFrame:
    """Road distance = straight line x detour factor (C-04). Same zone = 0."""
    z = city["zones"]
    f = city["travel"]["detour_factor"]
    ids = list(z)
    data = {j: [0.0 if i == j else round(
        haversine_km(z[i]["lat"], z[i]["lon"], z[j]["lat"], z[j]["lon"]) * f, 2)
        for i in ids] for j in ids}
    return pd.DataFrame(data, index=ids)


def speed_kmh(city: dict, hour: int, is_weekend: bool) -> float:
    t = city["travel"]
    peak = (not is_weekend) and hour in t["weekday_peak_hours"]
    return t["peak_speed_kmh"] if peak else t["offpeak_speed_kmh"]


def travel_minutes(city: dict, km: float, hour: int, is_weekend: bool) -> float:
    return 60.0 * km / speed_kmh(city, hour, is_weekend)


def max_reposition_km(city: dict, hour: int, is_weekend: bool) -> float:
    """Distance reachable within the repositioning time limit (C-06)."""
    return city["travel"]["max_reposition_minutes"] / 60.0 * speed_kmh(city, hour, is_weekend)
