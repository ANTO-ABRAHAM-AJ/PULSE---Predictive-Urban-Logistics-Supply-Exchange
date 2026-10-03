"""Result documents are generated, never typed: test the Markdown helpers."""
import pandas as pd
import pytest

from pulse.reporting import fill_block, inr, table


def test_table_renders_markdown_with_formats():
    df = pd.DataFrame({"Zone": ["A", "B"], "Value": [1234.5, -10.0], "Rate": [0.5, 0.25]})
    md = table(df, {"Value": inr, "Rate": "{:.0%}"})
    assert md.splitlines()[0] == "| Zone | Value | Rate |"
    assert "| A | ₹1,234 | 50% |" in md and "| B | −₹10 | 25% |" in md


def test_fill_block_replaces_only_the_marked_block(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("Intro\n<!-- AUTO:x -->\nold\n<!-- /AUTO:x -->\nInterpretation\n", encoding="utf-8")
    fill_block(doc, "x", "new table", stamp=False)
    text = doc.read_text(encoding="utf-8")
    assert "new table" in text and "old" not in text
    assert text.startswith("Intro") and text.rstrip().endswith("Interpretation")


def test_fill_block_is_repeatable(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("<!-- AUTO:x -->\n<!-- /AUTO:x -->\n", encoding="utf-8")
    fill_block(doc, "x", "one", stamp=False)
    fill_block(doc, "x", "two", stamp=False)
    assert doc.read_text(encoding="utf-8").count("two") == 1


def test_missing_block_is_an_error(tmp_path):
    doc = tmp_path / "doc.md"
    doc.write_text("no markers", encoding="utf-8")
    with pytest.raises(ValueError):
        fill_block(doc, "x", "content")
