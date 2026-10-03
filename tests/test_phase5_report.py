"""Phase 5 report: formatting and headline logic on result sets shaped like
the SQL output (the SQL itself runs against SQL Server on the user's machine)."""
import importlib.util
import re
from decimal import Decimal
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("report_phase5", ROOT / "scripts" / "report_phase5.py")
rp = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rp)


def sql_aliases(stem: str) -> list[list[str]]:
    """Bracketed column aliases of each final SELECT, in order, from the SQL file."""
    text = (ROOT / "05_Marketplace_Analytics" / "sql" / f"{stem}.sql").read_text(encoding="utf-8")
    out = []
    for part in re.split(r"/\* -+ Result Set [A-Z]", text)[1:]:
        names = re.findall(r"\bAS \[([^\]]+)\]", part)
        out.append(list(dict.fromkeys(names)))
    return out


def test_clean_turns_decimals_into_numbers():
    df = pd.DataFrame({"a": [Decimal("3"), Decimal("4")], "b": [Decimal("1.5"), None]})
    out = rp.clean(df)
    assert out["a"].tolist() == [3, 4] and out["b"].tolist()[0] == 1.5


def test_every_analysis_has_a_document_with_its_blocks():
    for stem, doc in rp.ANALYSES.items():
        text = (ROOT / "05_Marketplace_Analytics" / doc).read_text(encoding="utf-8")
        n_sets = len(sql_aliases(stem))
        for letter in "ABCDEFG"[:n_sets]:
            assert f"<!-- AUTO:{letter} -->" in text, (doc, letter)
        assert "<!-- AUTO:headline -->" in text, doc


def test_headlines_use_columns_that_the_sql_returns():
    """Build tiny frames with exactly the SQL column names and run each headline."""
    for stem, fn in rp.HEADLINES.items():
        frames = []
        for cols in sql_aliases(stem):
            rows = []
            for i in range(3):
                row = {}
                for c in cols:
                    if c in ("Service",):
                        row[c] = ["Mobility", "Food Delivery", "Marketplace total"][i]
                    elif c == "Vehicle":
                        row[c] = ["Two-wheeler", "Four-wheeler cab", "All partners"][i]
                    elif c in ("Zone type", "Split"):
                        row[c] = ["office", "mixed", "residential"][i]
                    else:
                        row[c] = float(10 + i)
                rows.append(row)
            frames.append(pd.DataFrame(rows))
        text = fn(*frames)
        assert text.startswith("- ") and "nan" not in text.lower(), stem
