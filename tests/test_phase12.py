"""Phase 12: Power BI layer — map file, SQL/DAX consistency, report wiring (no database needed)."""
import importlib.util
import json
import re
from pathlib import Path

import pandas as pd

from pulse.generation.city import load_city
from pulse.geo.topojson import decode_arc, geojson_to_topojson
from pulse.geo.zones import ZONES_FILE

ROOT = Path(__file__).resolve().parents[1]
PBI = ROOT / "12_PowerBI"
spec = importlib.util.spec_from_file_location("report_phase12", ROOT / "scripts" / "report_phase12.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)

VIEWS_SQL = (PBI / "sql" / "00_create_powerbi_views.sql").read_text(encoding="utf-8")
CHECKS_SQL = (PBI / "sql" / "01_dashboard_checks.sql").read_text(encoding="utf-8")
DAX = (PBI / "dax" / "PULSE_measures.dax").read_text(encoding="utf-8")
PARAMETER_TABLES = {"Job Value": {"Job Value"}, "Bonus": {"Bonus"}, "Map Metric": {"Metric", "Order"}}


def view_blocks() -> dict[str, str]:
    parts = re.split(r"CREATE OR ALTER VIEW pbi\.(\w+) AS", VIEWS_SQL)
    return {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}


# ------------------------------------------------------------------ map
def test_topojson_round_trips_every_zone():
    src = json.loads(ZONES_FILE.read_text(encoding="utf-8"))
    topo = geojson_to_topojson(src)
    geoms = topo["objects"]["zones"]["geometries"]
    assert sorted(g["properties"]["zone_code"] for g in geoms) == sorted(load_city()["zones"])
    # first ring of every zone decodes back to the source ring within ~1 m
    for f, g in zip(src["features"], geoms):
        ring = (f["geometry"]["coordinates"] if f["geometry"]["type"] == "Polygon"
                else f["geometry"]["coordinates"][0])[0]
        first_arc = g["arcs"][0][0] if g["type"] == "Polygon" else g["arcs"][0][0][0]
        decoded = decode_arc(topo, first_arc)
        assert decoded[0] == decoded[-1]                       # closed ring
        assert abs(decoded[0][0] - ring[0][0]) < 1e-5 and abs(decoded[0][1] - ring[0][1]) < 1e-5


def test_committed_map_file_matches_the_zone_boundaries():
    committed = json.loads((PBI / "map" / "bengaluru_zones.json").read_text(encoding="utf-8"))
    assert committed == json.loads(json.dumps(geojson_to_topojson(
        json.loads(ZONES_FILE.read_text(encoding="utf-8")))))


# ------------------------------------------------------------------ SQL <-> DAX
def test_every_power_bi_table_has_a_view():
    assert set(view_blocks()) == set(rp.TABLES)


def test_dax_only_uses_columns_the_views_provide():
    blocks = view_blocks()
    refs = re.findall(r"(?:'([^']+)'|\b([A-Z][A-Za-z_]+))\[([^\]]+)\]", DAX)
    for quoted, bare, col in refs:
        table = quoted or bare
        if table == "_Measures":
            continue
        if table in PARAMETER_TABLES:
            assert col in PARAMETER_TABLES[table], (table, col)
            continue
        assert table in blocks, f"unknown table {table}"
        assert re.search(rf"\b{re.escape(col)}\b", blocks[table]), (table, col)


def test_every_measure_reference_is_defined_once():
    names = re.findall(r"MEASURE '_Measures'\[([^\]]+)\]", DAX)
    assert len(names) == len(set(names))
    code = re.sub(r'"[^"]*"', '""', re.sub(r"//.*", "", DAX))
    used = set(re.findall(r"(?<![\w'\]])\[([^\]]+)\]", code)) - {"@gain", "No"}
    assert used <= set(names), used - set(names)


def test_dax_parentheses_balance_in_every_measure():
    body = DAX.split("DEFINE", 1)[1]
    for chunk in re.split(r"\n(?=MEASURE |EVALUATE)", body):
        code = re.sub(r'"[^"]*"', '""', re.sub(r"//.*", "", chunk))
        assert code.count("(") == code.count(")"), chunk[:60]


def test_sql_checks_and_dax_checks_are_the_same_list():
    sql_names = re.findall(r"'(?:Marketplace|Supply|Pressure|Forecast|Policy|Incentives)'(?: AS area)?,\s*'([^']+)'",
                           CHECKS_SQL)
    assert sql_names == rp.check_names()
    assert len(sql_names) == 30


def test_report_pages_only_reference_existing_measures():
    names = set(re.findall(r"MEASURE '_Measures'\[([^\]]+)\]", DAX))
    for doc in ("03_Report_Pages.md", "04_Interactivity.md", "02_DAX_Measures.md"):
        text = (PBI / doc).read_text(encoding="utf-8")
        refs = set(re.findall(r"`\[([^\]`]+)\]`", text))
        assert refs <= names, (doc, refs - names)


def test_report_pages_only_reference_existing_columns():
    blocks = view_blocks()
    for doc in ("03_Report_Pages.md", "04_Interactivity.md"):
        text = (PBI / doc).read_text(encoding="utf-8")
        for table, col in re.findall(r"`(\w+(?: \w+)?)\[(\w+)\]`", text):
            if table in PARAMETER_TABLES:
                assert col in PARAMETER_TABLES[table] or col.replace("_", " ") in PARAMETER_TABLES[table]
                continue
            assert table in blocks, (doc, table)
            assert re.search(rf"\b{col}\b", blocks[table]), (doc, table, col)


# ------------------------------------------------------------------ report wiring
def test_catalogue_covers_every_measure_with_a_folder_and_format():
    cat = rp.measure_catalogue()
    assert len(cat) == len(re.findall(r"^MEASURE ", DAX, flags=re.M))
    assert cat["Display folder"].str.len().gt(0).all()
    fmt = dict(zip(cat["Measure"], cat["Format string"]))
    assert fmt["Ride Completion %"] == "0.0%" and fmt["MPI"] == "0.00"
    assert fmt["Headline Problem"] == "Text" and fmt["Contribution per Day"] == "₹#,0"


def test_check_tables_and_headline_render():
    names = rp.check_names()
    units = ["count", "pct", "inr", "dec"] * 8
    a = pd.DataFrame({"#": range(1, 31), "Area": "x", "Check measure": names,
                      "Unit": units[:30], "SQL value": [71.9] * 30})
    b = pd.DataFrame({"Scenario": ["Status quo", "Profit", "+₹40 bonus"], "Completed jobs": [230419, 233588, 240000],
                      "Jobs lost to no partner": [26375, 22954, 13319], "Lost jobs vs status quo %": [0.0, -13.0, -49.5],
                      "Contribution (INR)": [9435104, 9440832, 8967000],
                      "Uplift per day vs status quo (INR)": [0, 205, -16700],
                      "Net vs profit policy per day (INR)": [-205, 0, -16905],
                      "Extra completed jobs per day vs status quo": [0, 113, 330]})
    assert "Power BI shows" in rp.checks_table(a)
    h = rp.headline(a, b)
    assert "+₹40 bonus" in h and "13,319" in h


def test_documents_have_their_blocks():
    assert "<!-- AUTO:rowcounts -->" in (PBI / "01_Data_Model.md").read_text(encoding="utf-8")
    text = (PBI / "02_DAX_Measures.md").read_text(encoding="utf-8")
    for block in ("A", "B", "catalogue", "headline"):
        assert f"<!-- AUTO:{block} -->" in text
