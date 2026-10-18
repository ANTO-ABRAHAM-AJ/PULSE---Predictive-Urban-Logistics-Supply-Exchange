"""Convert the zone GeoJSON into TopoJSON for the Power BI Shape Map visual.

Power BI's Shape Map only accepts TopoJSON. This is a small, dependency-free
encoder: every polygon ring becomes one arc, coordinates are quantized to a
grid (default 100,000 x 100,000 over the bounding box, about 0.5 m here) and
delta-encoded, as the TopoJSON specification describes. Arcs are not shared
between neighbouring zones; that only costs file size, not correctness.

The map key Power BI matches on is the `zone_code` property, which equals
`Dim_Zone[zone_code]` in the warehouse (e.g. WHF, KIA).
"""
from __future__ import annotations

import json
from pathlib import Path

from pulse.geo.zones import ZONES_FILE



def _rings(geometry: dict) -> list[list[list[list[float]]]]:
    """Return polygons as lists of rings, for Polygon and MultiPolygon."""
    if geometry["type"] == "Polygon":
        return [geometry["coordinates"]]
    if geometry["type"] == "MultiPolygon":
        return list(geometry["coordinates"])
    raise ValueError(f"Unsupported geometry type: {geometry['type']}")


def geojson_to_topojson(geojson: dict, object_name: str = "zones", quantization: int = 100_000) -> dict:
    """Encode a FeatureCollection of (Multi)Polygons as quantized TopoJSON."""
    feats = geojson["features"]
    xs = [p[0] for f in feats for poly in _rings(f["geometry"]) for ring in poly for p in ring]
    ys = [p[1] for f in feats for poly in _rings(f["geometry"]) for ring in poly for p in ring]
    x0, y0 = min(xs), min(ys)
    kx = (max(xs) - x0) / (quantization - 1) or 1.0
    ky = (max(ys) - y0) / (quantization - 1) or 1.0

    arcs: list[list[list[int]]] = []
    geometries = []
    for f in feats:
        polys = []
        for poly in _rings(f["geometry"]):
            ring_ids = []
            for ring in poly:
                q = [(round((x - x0) / kx), round((y - y0) / ky)) for x, y in ring]
                dedup = [q[0]] + [p for prev, p in zip(q, q[1:]) if p != prev]
                if dedup[0] != dedup[-1]:
                    dedup.append(dedup[0])
                if len(dedup) < 4:            # ring collapsed at this resolution
                    continue
                delta = [list(dedup[0])] + [[b[0] - a[0], b[1] - a[1]] for a, b in zip(dedup, dedup[1:])]
                ring_ids.append([len(arcs)])
                arcs.append(delta)
            if ring_ids:
                polys.append(ring_ids)
        props = dict(f.get("properties") or {})
        code = props.get("zone_code") or props.get("zone_id")
        out_props = {"zone_code": code, "zone_name": props.get("zone_name"), "zone_type": props.get("zone_type")}
        geom = ({"type": "Polygon", "arcs": polys[0]} if len(polys) == 1
                else {"type": "MultiPolygon", "arcs": polys})
        geometries.append({**geom, "id": code, "properties": out_props})

    return {"type": "Topology",
            "transform": {"scale": [kx, ky], "translate": [x0, y0]},
            "objects": {object_name: {"type": "GeometryCollection", "geometries": geometries}},
            "arcs": arcs}


def decode_arc(topology: dict, index: int) -> list[tuple[float, float]]:
    """Decode one arc back to lon/lat (used by the tests)."""
    (kx, ky), (x0, y0) = topology["transform"]["scale"], topology["transform"]["translate"]
    x = y = 0
    out = []
    for dx, dy in topology["arcs"][index]:
        x += dx
        y += dy
        out.append((x * kx + x0, y * ky + y0))
    return out


def write_zone_topojson(dest: Path | str, source: Path | str = ZONES_FILE) -> dict:
    with open(source, encoding="utf-8") as f:
        topo = geojson_to_topojson(json.load(f))
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(topo, f, separators=(",", ":"))
    return topo
