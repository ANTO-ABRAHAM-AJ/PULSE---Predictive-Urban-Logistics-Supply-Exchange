"""Phase 7: report wiring, headlines and charts (no database needed)."""
import importlib.util
import re
from pathlib import Path

import pandas as pd

from pulse.generation.city import load_city
from pulse.geo.plots import stacked_shares

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("report_phase7", ROOT / "scripts" / "report_phase7.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


def sql_aliases(stem):
    text = (ROOT / "07_Supply_Intelligence" / "sql" / f"{stem}.sql").read_text(encoding="utf-8")
    return [list(dict.fromkeys(re.findall(r"\bAS \[([^\]]+)\]", part)))
            for part in re.split(r"/\* -+ Result Set [A-Z]", text)[1:]]


def test_every_analysis_has_its_blocks():
    for stem, doc in rp.ANALYSES.items():
        text = (ROOT / "07_Supply_Intelligence" / doc).read_text(encoding="utf-8")
        assert len(sql_aliases(stem)) == 2, stem
        for letter in "AB":
            assert f"<!-- AUTO:{letter} -->" in text, (doc, letter)
        assert "<!-- AUTO:headline -->" in text


def test_state_columns_match_the_sql():
    assert sql_aliases("02_partner_time_states")[0][2:] == rp.STATES


def _frames(stem):
    texts = {"Zone": ["BSK", "WHF", "MAJ"], "Zone type": ["office", "residential", "mixed"],
             "Vehicle": ["Two-wheeler", "Four-wheeler cab", "Four-wheeler cab"]}
    frames = []
    for cols in sql_aliases(stem):
        df = pd.DataFrame({c: texts.get(c, [10.0, 12.0, 11.0]) for c in cols})
        if "Hour" in df:
            df["Hour"] = [8, 9, 18]
        frames.append(df)
    return frames


def test_headlines_run_on_frames_shaped_like_the_sql():
    for stem, fn in rp.HEADLINES.items():
        text = fn(*_frames(stem))
        assert text.startswith("- ") and "nan" not in text.lower(), stem


def test_charts_are_drawn(tmp_path, monkeypatch):
    z = load_city()["zones"]
    matrix = pd.DataFrame([{"zone_code": k, "zone_type": v["type"], "hour_of_day": h,
                            "partners_online": 5.0 + h % 4, "busy_hours": 2.0, "idle_hours": 3.0 + h % 4,
                            "utilization_pct": 40.0}
                           for k, v in z.items() for h in range(24)])
    living = pd.DataFrame({"zone_code": list(z), "partners_living": range(1, len(z) + 1)})
    states = pd.DataFrame({"Hour": range(24), "Idle %": 50.0, "To pickup %": 10.0, "On trip %": 20.0,
                           "To restaurant %": 10.0, "Delivering %": 10.0})
    monkeypatch.setattr(rp, "CHARTS", tmp_path)
    rp.draw_charts(matrix, living, states)
    for name in ["supply_map", "heatmap_partners_present", "heatmap_idle", "heatmap_utilization",
                 "partner_time_states"]:
        assert (tmp_path / f"{name}.png").stat().st_size > 10_000, name
