"""Phase 6: build PULSE zone polygons from public BBMP ward boundaries.

Downloads the ward file once to data/raw/ (gitignored), then writes
config/bengaluru/zone_boundaries.geojson and city_outline.geojson
(committed, so maps work without downloading again).

Usage:
    python scripts/build_zone_geometry.py
"""
from pathlib import Path

import geopandas as gpd

from pulse.geo.zones import ATTRIBUTION, OUTLINE_FILE, ZONES_FILE, build_zone_polygons, download_wards

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    wards_path = download_wards(ROOT / "data" / "raw" / "BBMP.geojson")
    wards = gpd.read_file(wards_path)
    zones, outline = build_zone_polygons(wards)
    zones.to_file(ZONES_FILE, driver="GeoJSON")
    outline.to_file(OUTLINE_FILE, driver="GeoJSON")
    print(f"Wards read: {len(wards)}")
    print(f"Zones built: {len(zones)}  ({(zones['source'] == 'circle').sum()} drawn as a circle: "
          f"{', '.join(zones.loc[zones['source'] == 'circle', 'zone_id'])})")
    print(f"Written: {ZONES_FILE.relative_to(ROOT)}, {OUTLINE_FILE.relative_to(ROOT)}")
    print(ATTRIBUTION)


if __name__ == "__main__":
    main()
