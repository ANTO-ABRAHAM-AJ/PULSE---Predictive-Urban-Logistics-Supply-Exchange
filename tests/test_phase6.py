"""Phase 6: zone geometry, charts, and report headlines (no database needed)."""
import importlib.util
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from pulse.generation.city import load_city
from pulse.geo.plots import choropleth_panels, zone_hour_heatmap
from pulse.geo.zones import load_zone_polygons

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("report_phase6", ROOT / "scripts" / "report_phase6.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


@pytest.fixture(scope="module")
def geo():
    return load_zone_polygons()


def test_every_zone_has_a_valid_polygon(geo):
    zones, outline = geo
    assert set(zones["zone_id"]) == set(load_city()["zones"])
    assert zones.geometry.is_valid.all() and (zones.to_crs(32643).geometry.area > 0).all()
    assert outline.geometry.is_valid.all()


def test_only_the_airport_is_drawn_as_a_circle(geo):
    zones, _ = geo
    assert zones.loc[zones["source"] == "circle", "zone_id"].tolist() == ["KIA"]


def test_zone_centres_fall_inside_or_near_their_polygon(geo):
    """A zone's centre should be in, or within 2 km of, its own polygon."""
    import geopandas as gpd
    zones, _ = geo
    z = load_city()["zones"]
    pts = gpd.GeoSeries(gpd.points_from_xy([z[k]["lon"] for k in zones.zone_id],
                                           [z[k]["lat"] for k in zones.zone_id]), crs=4326).to_crs(32643)
    polys = zones.to_crs(32643).geometry.reset_index(drop=True)
    assert (pts.reset_index(drop=True).distance(polys) <= 2000).all()


def _matrix():
    z = load_city()["zones"]
    rows = [{"zone_code": k, "zone_type": v["type"], "hour_of_day": h,
             "rides_per_day": float(h % 7), "orders_per_day": float(h % 5), "lost_per_day": float(h % 3)}
            for k, v in z.items() for h in range(24)]
    return pd.DataFrame(rows)


def test_charts_are_drawn(tmp_path, geo):
    zones, outline = geo
    m = _matrix()
    per_zone = m.groupby("zone_code")[["rides_per_day", "orders_per_day"]].sum()
    choropleth_panels(zones, outline, {"Rides": per_zone["rides_per_day"],
                                       "Food": per_zone["orders_per_day"]}, "t", tmp_path / "map.png")
    zone_hour_heatmap(m, "rides_per_day", "t", tmp_path / "hm.png")
    assert (tmp_path / "map.png").stat().st_size > 10_000
    assert (tmp_path / "hm.png").stat().st_size > 10_000


def sql_aliases(stem):
    text = (ROOT / "06_Demand_Intelligence" / "sql" / f"{stem}.sql").read_text(encoding="utf-8")
    return [list(dict.fromkeys(re.findall(r"\bAS \[([^\]]+)\]", part)))
            for part in re.split(r"/\* -+ Result Set [A-Z]", text)[1:]]


def test_every_analysis_has_its_blocks():
    for stem, doc in rp.ANALYSES.items():
        text = (ROOT / "06_Demand_Intelligence" / doc).read_text(encoding="utf-8")
        for letter in "AB"[:len(sql_aliases(stem))]:
            assert f"<!-- AUTO:{letter} -->" in text, (doc, letter)
        assert "<!-- AUTO:headline -->" in text


def test_headlines_run_on_frames_shaped_like_the_sql():
    texts = {"Zone": ["WHF", "KOR", "JAY"], "Zone name": ["a", "b", "c"],
             "Zone type": ["office", "restaurant_cluster", "residential"],
             "Service": ["Mobility", "Food Delivery", "Mobility"], "Split": ["history"] * 3}
    for stem, fn in rp.HEADLINES.items():
        frames = []
        for cols in sql_aliases(stem):
            df = pd.DataFrame({c: texts.get(c, [10.0, 12.0, 11.0]) for c in cols})
            for c in ("Hour", "Restaurants"):
                if c in df:
                    df[c] = [8, 9, 18]
            if cols and cols[0].startswith("Restaurant decile"):
                df[cols[0]] = [1, 2, 3]
            frames.append(df)
        text = fn(*frames)
        assert text.startswith("- ") and "nan" not in text.lower(), stem
