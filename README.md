# PULSE — Predictive Urban Logistics & Supply Exchange

> How should a multi-service marketplace anticipate demand and allocate scarce
> supply across mobility and food delivery to maintain service levels and
> maximize contribution?

**Status:** Stage 1 — toy optimization core validated. Phases 1–12 scaffolded.

## Repository layout

| Path | Contents |
|------|----------|
| `01_`–`12_` folders | Phase documentation, SQL, notebooks, outputs |
| `src/pulse/` | All reusable Python code |
| `config/` | All shared parameters (costs, eligibility, limits) |
| `data/` | All datasets (`sample/` committed; `raw/`, `processed/` ignored) |
| `tests/` | Validation and stress tests |
| `scripts/` | Entry points |

## Quick start

```bash
pip install -r requirements.txt
pip install -e .
python scripts/run_toy.py
pytest
```
