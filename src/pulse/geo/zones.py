"""Zone polygons built from public Bengaluru ward boundaries (Assumption C-03).

Source: DataMeet Municipal Spatial Data — 243 BBMP wards, 2022 delimitation,
scraped from KSRSAC. Licence: CC BY-SA 2.5 India. Pinned to one commit so the
build is reproducible.

Method: each ward is assigned to the nearest PULSE zone centre (within
`max_km`); wards are dissolved into one polygon per zone. Zones with no ward
inside BBMP limits (Kempegowda Airport) get a circle around their centre.
"""
from __future__ import annotations

import urllib.request
from pathlib import Path

import numpy as np

from pulse.generation.city import CITY_DIR, load_city

WARDS_URL = ("https://raw.githubusercontent.com/datameet/Municipal_Spatial_Data/"
             "9b4d1c2ece54cdeb6f5e8bad9ccad7844f783b17/Bangalore/BBMP.geojson")
ATTRIBUTION = ("Ward boundaries: BBMP wards (2022) from DataMeet Municipal Spatial Data, "
               "scraped from KSRSAC — CC BY-SA 2.5 India")
ZONES_FILE = CITY_DIR / "zone_boundaries.geojson"
OUTLINE_FILE = CITY_DIR / "city_outline.geojson"
METRIC_CRS = 32643          # UTM 43N, metres — correct for Bengaluru distances


def download_wards(dest: Path | str) -> Path:
    dest = Path(dest)
    if not dest.exists():
        dest.parent.mkdir(parents=True, exist_ok=True)
        urllib.request.urlretrieve(WARDS_URL, dest)
    return dest


def build_zone_polygons(wards, city: dict | None = None, max_km: float = 6.0,
                        fallback_radius_km: float = 2.5):
    """Return (zones, outline) GeoDataFrames in EPSG:4326."""
    import geopandas as gpd

    city = city or load_city()
    z = city["zones"]
    wards = wards.copy()
    wards["geometry"] = wards.geometry.make_valid().buffer(0)
    wm = wards.to_crs(METRIC_CRS)

    centres = gpd.GeoDataFrame(
        {"zone_id": list(z)},
        geometry=gpd.points_from_xy([v["lon"] for v in z.values()], [v["lat"] for v in z.values()]),
        crs=4326).to_crs(METRIC_CRS)

    pts = wm.geometry.representative_point()
    dist = np.array([[p.distance(c) for c in centres.geometry] for p in pts]) / 1000
    wm["zone_id"] = np.array(list(z))[dist.argmin(axis=1)]
    wm["km_to_centre"] = dist.min(axis=1)
    assigned = wm[wm["km_to_centre"] <= max_km]

    zones = assigned.dissolve("zone_id", aggfunc={"KGISWardID": "count"}).reset_index()
    zones = zones.rename(columns={"KGISWardID": "n_wards"})[["zone_id", "n_wards", "geometry"]]
    zones["source"] = "wards"

    missing = [zid for zid in z if zid not in set(zones["zone_id"])]
    if missing:
        extra = centres[centres["zone_id"].isin(missing)].copy()
        extra["geometry"] = extra.geometry.buffer(fallback_radius_km * 1000)
        extra["n_wards"] = 0
        extra["source"] = "circle"
        zones = gpd.GeoDataFrame(
            __import__("pandas").concat([zones, extra[["zone_id", "n_wards", "geometry", "source"]]],
                                        ignore_index=True), crs=METRIC_CRS)

    zones["zone_name"] = zones["zone_id"].map(lambda k: z[k]["name"])
    zones["zone_type"] = zones["zone_id"].map(lambda k: z[k]["type"])
    zones["area_km2"] = (zones.geometry.area / 1e6).round(1)
    zones = zones.sort_values("zone_id").reset_index(drop=True)
    zones["geometry"] = zones.geometry.simplify(15)          # ~15 m: smaller file, same map

    outline = gpd.GeoDataFrame({"name": ["BBMP"]}, geometry=[wm.geometry.union_all().simplify(15)],
                               crs=METRIC_CRS)
    return zones.to_crs(4326), outline.to_crs(4326)


def load_zone_polygons():
    import geopandas as gpd
    return gpd.read_file(ZONES_FILE), gpd.read_file(OUTLINE_FILE)
