"""Phase 8: pressure-index report wiring, headlines and charts (no database needed)."""
import importlib.util
import re
from pathlib import Path

import pandas as pd

from pulse.generation.city import load_city

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("report_phase8", ROOT / "scripts" / "report_phase8.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)
SQL = ROOT / "08_Supply_Demand_Imbalance" / "sql"


def sql_aliases(stem):
    text = (SQL / f"{stem}.sql").read_text(encoding="utf-8")
    return [list(dict.fromkeys(re.findall(r"\bAS \[([^\]]+)\]", part)))
            for part in re.split(r"/\* -+ Result Set [A-Z]", text)[1:]]


def test_thresholds_match_the_kpi_dictionary():
    """The pressure table must use the KPI_Dictionary thresholds 0.80 and 1.10."""
    text = (SQL / "00_build_pressure_table.sql").read_text(encoding="utf-8")
    kpi = (ROOT / "01_Business_Understanding" / "KPI_Dictionary.md").read_text(encoding="utf-8")
    assert "1.10" in kpi and "0.80" in kpi
    assert "local_mpi > 1.10" in text and "local_mpi < 0.80" in text


def test_every_analysis_has_its_blocks():
    for stem, doc in rp.ANALYSES.items():
        text = (ROOT / "08_Supply_Demand_Imbalance" / doc).read_text(encoding="utf-8")
        assert len(sql_aliases(stem)) == 2, stem
        for letter in "AB":
            assert f"<!-- AUTO:{letter} -->" in text, (doc, letter)
        assert "<!-- AUTO:headline -->" in text


def test_headlines_run_on_frames_shaped_like_the_sql():
    texts = {"Pressure state": ["Over-supplied", "Balanced", "Under-supplied"],
             "MPI band": ["< 0.5", "1.1 - 1.5", "3.0 or more"],
             "Shortage type": ["Reposition ahead", "Citywide shortage", "Fix now"],
             "Lever": ["a", "b", "c"], "Zone": ["KIA", "ECY", "WHF"],
             "Zone type": ["office", "transit_hub", "mixed"],
             "Time band": ["1 Morning 07-10", "4 Evening 17-20", "5 Night 21-06"]}
    for stem, fn in rp.HEADLINES.items():
        frames = []
        for cols in sql_aliases(stem):
            df = pd.DataFrame({c: texts.get(c, [10.0, 12.0, 11.0]) for c in cols})
            if "Hour" in df:
                df["Hour"] = [8, 9, 18]
            frames.append(df)
        text = fn(*frames)
        assert text.startswith("- ") and "nan" not in text.lower(), stem


def test_charts_are_drawn(tmp_path, monkeypatch):
    z = load_city()["zones"]
    matrix = pd.DataFrame([{"zone_code": k, "zone_type": v["type"], "hour_of_day": h,
                            "mpi": 0.3 + (h % 5) * 0.6, "under_pct": 10.0, "lost_per_day": 1.0,
                            "lost_fix_now": 0.1, "lost_reposition_ahead": 0.7, "lost_citywide": 0.2}
                           for k, v in z.items() for h in range(24)])
    zone_table = pd.DataFrame({"Zone": list(z), "Under-supplied hours %": 20.0, "MPI 17-20": 1.4})
    calibration = pd.DataFrame({"MPI band": ["< 0.5", "1.1 - 1.5", "No supply present"],
                                "Loss rate %": [0.1, 6.0, 90.0]})
    monkeypatch.setattr(rp, "CHARTS", tmp_path)
    rp.draw_charts(matrix, zone_table, calibration)
    for name in ["pressure_map", "heatmap_mpi", "lost_by_shortage_type", "mpi_calibration"]:
        assert (tmp_path / f"{name}.png").stat().st_size > 10_000, name
