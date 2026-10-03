"""Write results into Markdown documents without touching the hand-written text.

A findings document contains marked blocks:

    <!-- AUTO:policy_comparison -->
    (anything here is replaced on every run)
    <!-- /AUTO:policy_comparison -->

Report scripts compute numbers from the data and call `fill_block`, so result
tables are never typed by hand and cannot drift from the data. The
interpretation around the blocks is written by people.
"""
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

import pandas as pd


def table(df: pd.DataFrame, formats: dict | None = None, index: bool = False) -> str:
    """Render a DataFrame as a GitHub Markdown table (no extra dependencies)."""
    formats = formats or {}
    d = df.reset_index() if index else df
    cols = [str(c) for c in d.columns]

    def fmt(col, v):
        if v is None or (isinstance(v, float) and pd.isna(v)):
            return ""
        f = formats.get(col)
        if callable(f):
            return f(v)
        if f:
            return f.format(v)
        if isinstance(v, float):
            return f"{v:,.2f}"
        if isinstance(v, int) and not isinstance(v, bool):
            return f"{v:,}"
        return str(v)

    lines = ["| " + " | ".join(cols) + " |",
             "|" + "|".join("---" for _ in cols) + "|"]
    for row in d.itertuples(index=False):
        lines.append("| " + " | ".join(fmt(c, v) for c, v in zip(d.columns, row)) + " |")
    return "\n".join(lines)


def inr(v) -> str:
    """Format rupees with a proper minus sign: ₹1,234 / −₹1,234."""
    return ("−₹" if v < 0 else "₹") + f"{abs(v):,.0f}"


def fill_block(path: Path | str, name: str, content: str, stamp: bool = True) -> None:
    """Replace the AUTO block `name` in a Markdown file with `content`."""
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    start, end = f"<!-- AUTO:{name} -->", f"<!-- /AUTO:{name} -->"
    if start not in text or end not in text:
        raise ValueError(f"Block '{name}' not found in {path}")
    body = content.strip()
    if stamp:
        body += f"\n\n_Generated {date.today().isoformat()} by a report script — do not edit by hand._"
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), flags=re.S)
    text = pattern.sub(lambda _: f"{start}\n{body}\n{end}", text)
    path.write_text(text, encoding="utf-8")
