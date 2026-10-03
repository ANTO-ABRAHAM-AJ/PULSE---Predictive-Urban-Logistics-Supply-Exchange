# PULSE — Predictive Urban Logistics & Supply Exchange

> How should a multi-service marketplace anticipate demand and allocate scarce
> supply across mobility and food delivery to maintain service levels and
> maximize contribution?

PULSE models a Bengaluru super-app where one pool of partners serves both ride
and food-delivery demand. It forecasts demand by **Zone × Time × Service** and
uses constrained optimization (Python + OR-Tools) to decide where supply should
go, when, and for which service — and whether it is economically justified.

## Status

| Stage | What | Status |
|-------|------|--------|
| 0–1 | Repo setup; toy optimization model validated against a hand calculation | ✅ |
| 2 | Optimizer stress tests (no supply, spikes, infeasible service floors, …) | ✅ |
| 3 | Naive baseline + independent evaluator: optimizer wins 99% of demand draws | ✅ |
| 4 | Shadow prices verified by re-solving; bottleneck ranking | ✅ |
| 5 | Synthetic Bengaluru: 24 zones, 16 weeks, 850 partners, 1.1M rides and orders | ✅ |
| Phase 4 | SQL Server data warehouse: 15-table star schema, loader, quality checks | ✅ |
| Phase 5 | Marketplace performance analytics (T-SQL KPI views) | Next |

## Results documents

Every result table is generated from data by a report script — never typed by hand.

| Document | What it shows | Regenerate |
|----------|---------------|------------|
| `10_Optimization/Validation_Results.md` | Optimizer proof on the toy: hand calculation, stress tests, +9% vs naive dispatch, bottleneck pricing | `python scripts/report_optimizer.py` |
| `03_Data_Engineering/Generation_Results.md` | Synthetic Bengaluru: planted patterns recovered, status-quo performance, the supply mismatch | `python scripts/report_generation.py` |
| `04_Data_Warehouse/Load_Results.md` | Warehouse: tables loaded, quality checks, SQL ↔ Python reconciliation | `python scripts/report_warehouse.py` |

## Key findings so far (synthetic data, status-quo dispatch)

- 72% of ride requests and 94% of food orders are fulfilled.
- Partners are idle ~53% of their online time — while office-zone evening
  rides succeed only about 1 time in 4.
- The shortage is mostly about **where** supply is, not how much exists:
  the problem PULSE's optimizer is built to solve.

All results are model-based estimates on synthetic data, not real-world impact.

## Repository layout

| Path | Contents |
|------|----------|
| `01_`–`12_` folders | Phase documentation, SQL, notebooks, outputs |
| `src/pulse/` | All reusable Python code (`optimization/`, `generation/`, …) |
| `config/` | All shared parameters (`config/bengaluru/` for the city) |
| `data/` | Datasets (`sample/` committed; `raw/`, `processed/` gitignored) |
| `tests/` | Validation and stress tests |
| `scripts/` | Entry points |

Assumptions: `01_Business_Understanding/Assumptions.md` ·
KPI definitions: `01_Business_Understanding/KPI_Dictionary.md` ·
Data generation: `03_Data_Engineering/Data_Generation_Framework.md`

## Quick start

```bash
pip install -r requirements-lock.txt   # exact tested versions (or requirements.txt)
pip install -e .
pytest                                 # 68 tests
python scripts/run_toy.py              # toy optimizer
python scripts/compare_policies.py     # optimizer vs baseline
python scripts/bottlenecks.py          # marginal value of supply
python scripts/build_all.py            # rebuild all Bengaluru data (~2-4 min)
python scripts/load_warehouse.py       # load SQL Server warehouse PULSE_DW
```

Tested on Python 3.14.
