"""Load star-schema tables into SQL Server with pyodbc.

Steps (scripts/load_warehouse.py runs them in order):
  1. 01_create_database.sql   (connected to master, autocommit)
  2. 02_create_tables.sql     (drops and recreates the schema)
  3. bulk insert every table  (fast_executemany, in batches)
  4. 03_create_indexes.sql
  5. row-count check against the source DataFrames
  6. 04_data_quality_checks.sql
"""
from __future__ import annotations

import re
import time
from pathlib import Path

import pandas as pd
import yaml

from pulse.utils.config import CONFIG_DIR

ROOT = Path(__file__).resolve().parents[3]
SQL_DIR = ROOT / "04_Data_Warehouse" / "sql"


def load_settings(path: Path | str = CONFIG_DIR / "warehouse.yaml") -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def connection_string(settings: dict, database: str | None = None) -> str:
    parts = [f"DRIVER={{{settings['driver']}}}",
             f"SERVER={settings['server']}",
             f"DATABASE={database or settings['database']}"]
    if settings.get("trusted_connection", True):
        parts.append("Trusted_Connection=yes")
    if settings.get("trust_server_certificate", False):
        parts.append("TrustServerCertificate=yes")
    return ";".join(parts) + ";"


def connect(settings: dict, database: str | None = None, autocommit: bool = False):
    import pyodbc  # imported here so the rest of the package works without it
    return pyodbc.connect(connection_string(settings, database), autocommit=autocommit)


def split_batches(sql_text: str) -> list[str]:
    """Split a T-SQL script on lines containing only GO (like SSMS does)."""
    batches = re.split(r"^\s*GO\s*;?\s*$", sql_text, flags=re.IGNORECASE | re.MULTILINE)
    return [b.strip() for b in batches if b.strip()]


def run_script(conn, path: Path) -> None:
    cur = conn.cursor()
    for batch in split_batches(Path(path).read_text(encoding="utf-8")):
        cur.execute(batch)
        while cur.nextset():          # drain any extra result sets
            pass
    if not conn.autocommit:
        conn.commit()


def rows_for_insert(df: pd.DataFrame) -> list[tuple]:
    """Convert a DataFrame to plain Python tuples; every missing value -> None."""
    obj = df.astype(object)
    obj = obj.where(pd.notna(df), None)
    return list(obj.itertuples(index=False, name=None))


def insert_table(conn, table: str, df: pd.DataFrame, batch_size: int = 50_000) -> None:
    cols = ", ".join(df.columns)
    marks = ", ".join("?" for _ in df.columns)
    sql = f"INSERT INTO dw.{table} ({cols}) VALUES ({marks})"
    cur = conn.cursor()
    cur.fast_executemany = True
    for start in range(0, len(df), batch_size):
        cur.executemany(sql, rows_for_insert(df.iloc[start:start + batch_size]))
    conn.commit()


def table_count(conn, table: str) -> int:
    return conn.cursor().execute(f"SELECT COUNT_BIG(*) FROM dw.{table}").fetchone()[0]


def run_query(conn, path: Path | str) -> pd.DataFrame:
    """Run a saved .sql query file and return its (first) result set."""
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"^\s*USE\s+\w+\s*;?\s*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    cur = conn.cursor().execute(text)
    while cur.description is None and cur.nextset():
        pass
    cols = [c[0] for c in cur.description]
    return pd.DataFrame([tuple(r) for r in cur.fetchall()], columns=cols)


def run_query_all(conn, path: Path | str) -> list[pd.DataFrame]:
    """Run a saved .sql file and return EVERY result set it produces, in order
    (an analysis file usually has Result Set A and Result Set B)."""
    text = Path(path).read_text(encoding="utf-8")
    text = re.sub(r"^\s*USE\s+\w+\s*;?\s*$", "", text, flags=re.IGNORECASE | re.MULTILINE)
    cur = conn.cursor().execute("SET NOCOUNT ON;\n" + text)
    frames = []
    while True:
        if cur.description is not None:
            cols = [c[0] for c in cur.description]
            frames.append(pd.DataFrame([tuple(r) for r in cur.fetchall()], columns=cols))
        if not cur.nextset():
            break
    return frames


def quality_checks(conn) -> pd.DataFrame:
    return run_query(conn, SQL_DIR / "04_data_quality_checks.sql")


def load_all(tables: dict[str, pd.DataFrame], order: list[str], settings: dict,
             log=print) -> pd.DataFrame:
    t0 = time.time()
    with connect(settings, database="master", autocommit=True) as master:
        run_script(master, SQL_DIR / "01_create_database.sql")
    log("  database and schema ready")

    with connect(settings) as conn:
        run_script(conn, SQL_DIR / "02_create_tables.sql")
        log("  tables created")
        for name in order:
            t = time.time()
            insert_table(conn, name, tables[name], settings.get("batch_size", 50_000))
            log(f"  loaded {name:<26} {len(tables[name]):>10,} rows  ({time.time() - t:,.0f} s)")
        run_script(conn, SQL_DIR / "03_create_indexes.sql")
        log("  indexes created")

        mismatches = [(n, len(tables[n]), table_count(conn, n)) for n in order
                      if table_count(conn, n) != len(tables[n])]
        if mismatches:
            raise RuntimeError(f"Row counts differ from source: {mismatches}")
        log("  row counts match source for every table")
        checks = quality_checks(conn)
    log(f"  total load time {time.time() - t0:,.0f} s")
    return checks
