"""Build the SVG graphics used by the front-page README (docs/assets/).

Writes a dark and a light version of each graphic, so GitHub can show the one
that matches the reader's theme:

    banner        PULSE title + the 24 Bengaluru zones shaded by jobs lost per day
    kpis          the six headline numbers, grouped Diagnose / Predict / Decide
    lever_ladder  jobs won back vs cost per extra job, for each lever

Zone values come from the warehouse (same definition as the Power BI measure
Lost Jobs per Day) when PULSE_DW is reachable; otherwise from the committed
snapshot docs/assets/data/zone_lost_jobs.csv. The other numbers are the
holdout results reported in Phases 9-12.

Usage:
    python scripts/build_readme_assets.py
"""
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "assets"
GEO = ROOT / "config" / "bengaluru" / "zone_boundaries.geojson"
SNAPSHOT = OUT / "data" / "zone_lost_jobs.csv"

LOST_SQL = """
SELECT z.zone_code,
       SUM(CAST(m.lost_no_partner AS FLOAT)) /
       (SELECT COUNT(DISTINCT date_value) FROM pbi.Dim_Time WHERE data_split <> 'spill') AS lost_jobs_per_day
FROM pbi.Fact_Marketplace m JOIN pbi.Dim_Zone z ON z.zone_key = m.zone_key
GROUP BY z.zone_code
"""

FONT = "Segoe UI, -apple-system, Helvetica Neue, Arial, sans-serif"

THEMES = {
    "dark": {
        "bg": "#0B1220", "panel": "#111A2B", "line": "#1F2A3D", "ink": "#F1F5F9",
        "ink2": "#94A3B8", "ink3": "#64748B", "teal": "#2DD4BF", "coral": "#F87171",
        "amber": "#FBBF24", "violet": "#C084FC", "zone_edge": "#0B1220",
        # sequential, low -> high: from near-surface to coral
        "ramp": ["#22304A", "#47344D", "#7A3A4E", "#B4434F", "#F0625E"],
    },
    "light": {
        "bg": "#F8FAFC", "panel": "#FFFFFF", "line": "#E2E8F0", "ink": "#0F172A",
        "ink2": "#475569", "ink3": "#64748B", "teal": "#0D9488", "coral": "#DC2626",
        "amber": "#D97706", "violet": "#9333EA", "zone_edge": "#F8FAFC",
        "ramp": ["#E7ECF3", "#F6C9C6", "#EE9590", "#DC5C57", "#B91C1C"],
    },
}


# ------------------------------------------------------------------ data
def zone_values() -> dict[str, float]:
    try:
        from pulse.warehouse.load import connect, load_settings
        import pandas as pd
        with connect(load_settings()) as conn:
            df = pd.read_sql(LOST_SQL, conn)
        vals = dict(zip(df["zone_code"], df["lost_jobs_per_day"].astype(float)))
        with SNAPSHOT.open("w", newline="") as f:
            w = csv.writer(f)
            w.writerow(["zone_code", "lost_jobs_per_day"])
            for k in sorted(vals):
                w.writerow([k, round(vals[k])])
        print("Zone values: read from PULSE_DW (snapshot refreshed)")
        return vals
    except Exception:
        with SNAPSHOT.open() as f:
            vals = {r["zone_code"]: float(r["lost_jobs_per_day"]) for r in csv.DictReader(f)}
        print("Zone values: warehouse not reachable, used the committed snapshot")
        return vals


# ------------------------------------------------------------------ map
def rings(geom):
    if geom["type"] == "Polygon":
        return [geom["coordinates"][0]]
    return [poly[0] for poly in geom["coordinates"]]


def map_paths(x0, y0, w, h):
    """Project the zones into a w x h box at (x0, y0); returns {code: (path, centroid)}."""
    feats = json.loads(GEO.read_text(encoding="utf-8"))["features"]
    pts = [p for f in feats for r in rings(f["geometry"]) for p in r]
    lat0 = sum(p[1] for p in pts) / len(pts)
    k = math.cos(math.radians(lat0))
    xs = [p[0] * k for p in pts]
    ys = [p[1] for p in pts]
    s = min(w / (max(xs) - min(xs)), h / (max(ys) - min(ys)))
    ox = x0 + (w - (max(xs) - min(xs)) * s) / 2
    oy = y0 + (h - (max(ys) - min(ys)) * s) / 2

    def pr(lon, lat):
        return ox + (lon * k - min(xs)) * s, oy + (max(ys) - lat) * s

    out = {}
    for f in feats:
        code = f["properties"]["zone_id"]
        d, cx, cy, n = "", 0.0, 0.0, 0
        for r in rings(f["geometry"]):
            xy = [pr(*p[:2]) for p in r]
            d += "M" + "L".join(f"{x:.1f},{y:.1f}" for x, y in xy) + "Z"
            cx += sum(x for x, _ in xy)
            cy += sum(y for _, y in xy)
            n += len(xy)
        out[code] = (d, (cx / n, cy / n))
    return out


def bucket(v, edges):
    return sum(v > e for e in edges)


# ------------------------------------------------------------------ svg helpers
def svg_open(w, h, t, title):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" '
            f'role="img" aria-label="{title}" font-family="{FONT}">\n<title>{title}</title>\n')


def text(x, y, s, size, fill, weight=400, anchor="start", extra=""):
    s = s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    return (f'<text x="{x}" y="{y}" font-size="{size}" fill="{fill}" font-weight="{weight}" '
            f'text-anchor="{anchor}" {extra}>{s}</text>\n')


# ------------------------------------------------------------------ banner
def banner(theme: str, vals: dict[str, float]) -> str:
    t = THEMES[theme]
    W, H = 1280, 440
    g = svg_open(W, H, t, "PULSE: Predictive Urban Logistics and Supply Exchange")
    g += f"""<defs>
  <pattern id="dots" width="22" height="22" patternUnits="userSpaceOnUse">
    <circle cx="2" cy="2" r="1.1" fill="{t['line']}"/></pattern>
  <linearGradient id="fade" x1="0" x2="1"><stop offset="0" stop-color="{t['bg']}" stop-opacity="1"/>
    <stop offset="0.55" stop-color="{t['bg']}" stop-opacity="0.6"/><stop offset="1" stop-color="{t['bg']}" stop-opacity="0"/></linearGradient>
</defs>
<style>
  .ecg {{ stroke-dasharray: 1400; stroke-dashoffset: 1400; animation: draw 4.5s ease-in-out infinite; }}
  @keyframes draw {{ 0% {{ stroke-dashoffset: 1400; }} 55% {{ stroke-dashoffset: 0; }} 100% {{ stroke-dashoffset: -1400; }} }}
  .ring {{ transform-box: fill-box; transform-origin: center; animation: ping 2.4s ease-out infinite; }}
  .ring.d1 {{ animation-delay: .8s; }} .ring.d2 {{ animation-delay: 1.6s; }}
  @keyframes ping {{ 0% {{ transform: scale(.4); opacity: .9; }} 100% {{ transform: scale(2.6); opacity: 0; }} }}
  @media (prefers-reduced-motion: reduce) {{ .ecg, .ring {{ animation: none; stroke-dashoffset: 0; }} }}
</style>
<rect width="{W}" height="{H}" rx="18" fill="{t['bg']}"/>
<rect width="{W}" height="{H}" rx="18" fill="url(#dots)"/>
"""
    # map on the right
    paths = map_paths(720, 30, 500, 350)
    edges = [15, 25, 40, 90]
    for code, (d, _) in paths.items():
        fill = t["ramp"][bucket(vals.get(code, 0), edges)]
        g += f'<path d="{d}" fill="{fill}" stroke="{t["zone_edge"]}" stroke-width="1.6" stroke-linejoin="round"/>\n'
    top = sorted(vals, key=vals.get, reverse=True)[:3]
    for i, code in enumerate(top):
        cx, cy = paths[code][1]
        g += (f'<circle class="ring d{i}" cx="{cx:.1f}" cy="{cy:.1f}" r="9" fill="none" '
              f'stroke="{t["coral"]}" stroke-width="2"/>\n')
        g += f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="4" fill="{t["ink"]}"/>\n'
        lx = cx + 14 if code != "KIA" else cx - 26
        anchor = "start" if code != "KIA" else "end"
        g += text(round(lx), round(cy + 4), f"{code} {vals[code]:.0f}", 13, t["ink"], 700, anchor,
                  extra=f'stroke="{t["bg"]}" stroke-width="4" paint-order="stroke"')
    # legend
    lx, ly = 1010, 398
    g += text(lx - 8, ly + 9, "Jobs lost per day", 12, t["ink2"], 400, "end")
    labels = ["0–15", "15–25", "25–40", "40–90", "90+"]
    for i, c in enumerate(t["ramp"]):
        g += f'<rect x="{lx + i * 44}" y="{ly}" width="42" height="10" rx="2" fill="{c}"/>\n'
        g += text(lx + i * 44 + 21, ly + 26, labels[i], 10, t["ink3"], 400, "middle")
    # left text block over a soft fade so it never fights the map
    g += f'<rect x="0" y="0" width="760" height="{H}" rx="18" fill="url(#fade)"/>\n'
    g += text(64, 92, "SUPPLY &amp; DEMAND INTELLIGENCE  ·  BENGALURU".replace("&amp;", "&"), 15, t["teal"], 700,
              extra='letter-spacing="2.5"')
    g += text(60, 190, "PULSE", 104, t["ink"], 800, extra='letter-spacing="6"')
    g += text(64, 232, "Predictive Urban Logistics & Supply Exchange", 25, t["ink2"], 500)
    # heartbeat line
    y = 290
    ecg = (f"M64,{y} L250,{y} L266,{y-8} L280,{y} L296,{y} L310,{y-34} L326,{y+26} L340,{y} "
           f"L360,{y} L374,{y-12} L392,{y} L640,{y}")
    g += f'<path d="{ecg}" fill="none" stroke="{t["line"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>\n'
    g += f'<path class="ecg" d="{ecg}" fill="none" stroke="{t["teal"]}" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"/>\n'
    g += text(64, 348, "Forecast where riders and diners will be.", 21, t["ink"], 500)
    g += text(64, 378, "Move partners before they are needed.", 21, t["ink"], 500)
    g += text(64, 408, "Pay partners only when it pays.", 21, t["ink"], 500)
    return g + "</svg>\n"


# ------------------------------------------------------------------ KPI strip
KPIS = [
    ("DIAGNOSE", "coral", "935", "jobs lost a day", "no partner in 20 minutes"),
    ("DIAGNOSE", "coral", "52.8%", "of partner time idle", "while those jobs are lost"),
    ("PREDICT", "amber", "91%", "of lost jobs flagged", "a week ahead"),
    ("DECIDE", "teal", "−13%", "lost jobs, at no cost", "profit repositioning"),
    ("DECIDE", "teal", "₹19.5", "break-even per job", "service wins above it"),
    ("DECIDE", "teal", "₹43–55", "per job via bonuses", "vs ₹17 repositioning"),
]


def kpis(theme: str) -> str:
    t = THEMES[theme]
    W, H, gap = 1280, 206, 14
    tw = (W - gap * 7) / 6
    g = svg_open(W, H, t, "PULSE headline results")
    groups = {}
    for i, k in enumerate(KPIS):
        groups.setdefault(k[0], []).append(i)
    for name, idx in groups.items():
        x1 = gap + idx[0] * (tw + gap)
        x2 = gap + idx[-1] * (tw + gap) + tw
        col = t[KPIS[idx[0]][1]]
        g += f'<rect x="{x1:.1f}" y="10" width="{x2 - x1:.1f}" height="3" rx="1.5" fill="{col}"/>\n'
        g += text(round(x1), 36, name, 15, col, 700, extra='letter-spacing="2"')
    for i, (_, c, big, l1, l2) in enumerate(KPIS):
        x = gap + i * (tw + gap)
        g += f'<rect x="{x:.1f}" y="50" width="{tw:.1f}" height="146" rx="12" fill="{t["panel"]}" stroke="{t["line"]}"/>\n'
        g += f'<rect x="{x:.1f}" y="50" width="5" height="146" rx="2.5" fill="{t[c]}"/>\n'
        g += text(round(x + 22), 110, big, 44, t["ink"], 700)
        g += text(round(x + 22), 146, l1, 17, t["ink"], 600)
        g += text(round(x + 22), 174, l2, 14, t["ink2"], 400)
    return g + "</svg>\n"


# ------------------------------------------------------------------ lever ladder
LEVERS = [  # name, jobs won back vs status quo (%), net cost per extra job vs profit policy (INR), note
    ("Profit repositioning", 13.0, 0.0, "free: +₹205 a day"),
    ("Service repositioning", 23.9, 16.8, ""),
    ("Profit + ₹60 bonus", 40.3, 43.1, ""),
    ("Profit + ₹40 bonus", 49.5, 49.2, ""),
    ("Profit + ₹80 bonus", 34.1, 55.2, ""),
]


def ladder(theme: str) -> str:
    t = THEMES[theme]
    W, H = 1280, 404
    g = svg_open(W, H, t, "Lever ladder: jobs won back and cost per extra job")
    g += f'<rect width="{W}" height="{H}" rx="16" fill="{t["panel"]}" stroke="{t["line"]}"/>\n'
    lab_w, top, row = 250, 128, 50
    p1x, p1w = 300, 400   # panel 1: jobs won back
    p2x, p2w = 800, 400   # panel 2: cost per extra job
    g += text(40, 48, "The lever ladder", 28, t["ink"], 700)
    g += text(40, 74, "Ordered by price per extra job served: pull the cheapest lever first.",
              17, t["ink2"])
    g += text(p1x, top - 14, "Lost jobs won back vs status quo", 16, t["ink2"], 600)
    g += text(p2x, top - 14, "Net cost per extra job served (₹)", 16, t["ink2"], 600)
    for i, (name, won, cost, note) in enumerate(LEVERS):
        y = top + i * row
        g += text(40, y + 25, name, 18, t["ink"], 600)
        if i:
            g += f'<line x1="40" y1="{y - 6}" x2="{W - 40}" y2="{y - 6}" stroke="{t["line"]}"/>\n'
        bw = p1w * won / 55
        g += f'<rect x="{p1x}" y="{y + 8}" width="{bw:.1f}" height="22" rx="4" fill="{t["teal"]}"/>\n'
        g += text(round(p1x + bw + 10), y + 25, f"{won:.1f}%", 17, t["ink"], 600)
        if cost > 0:
            cw = p2w * cost / 60
            g += f'<rect x="{p2x}" y="{y + 8}" width="{cw:.1f}" height="22" rx="4" fill="{t["amber"]}"/>\n'
            g += text(round(p2x + cw + 10), y + 25, f"₹{cost:.0f}" if cost >= 20 else f"₹{cost:.1f}", 17, t["ink"], 600)
        else:
            g += f'<line x1="{p2x}" y1="{y + 8}" x2="{p2x}" y2="{y + 30}" stroke="{t["ink3"]}" stroke-width="2"/>\n'
            g += text(p2x + 12, y + 25, note, 17, t["ink"], 600)
    g += text(40, H - 20, "Holdout weeks 13–16, every lever replayed on the same customers. "
              "Costs are against the profit policy. Model-based estimates on a synthetic city.", 14, t["ink3"])
    return g + "</svg>\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    vals = zone_values()
    for theme in THEMES:
        (OUT / f"banner-{theme}.svg").write_text(banner(theme, vals), encoding="utf-8")
        (OUT / f"kpis-{theme}.svg").write_text(kpis(theme), encoding="utf-8")
        (OUT / f"lever-ladder-{theme}.svg").write_text(ladder(theme), encoding="utf-8")
    print(f"Wrote 6 SVGs to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
