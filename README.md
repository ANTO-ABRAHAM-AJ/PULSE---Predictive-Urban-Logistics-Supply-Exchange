# PULSE — Predictive Urban Logistics & Supply Exchange

> How should a multi-service marketplace anticipate demand and allocate scarce
> supply across mobility and food delivery to maintain service levels and
> maximize contribution?

PULSE models a Bengaluru super-app where one pool of partners serves both ride
and food-delivery demand. It forecasts demand by **Zone × Time × Service** and
uses constrained optimization (Python + OR-Tools) to decide where supply should
go, when, and for which service — and whether it is economically justified.

## Status

| Stage / Phase | What | Status |
|---------------|------|--------|
| Phase 1 | Business understanding: assumptions log and KPI dictionary (narrative documents written last) | Partial |
| Phase 2 | Marketplace data ecosystem: entities, lifecycles, lineage, coverage | ✅ |
| 0–1 | Repo setup; toy optimization model validated against a hand calculation | ✅ |
| 2 | Optimizer stress tests (no supply, spikes, infeasible service floors, …) | ✅ |
| 3 | Naive baseline + independent evaluator: optimizer wins 99% of demand draws | ✅ |
| 4 | Shadow prices verified by re-solving; bottleneck ranking | ✅ |
| 5 (Phase 3) | Synthetic Bengaluru: 24 zones, 16 weeks, 850 partners, 1.1M rides and orders | ✅ |
| Phase 4 | SQL Server data warehouse: 15-table star schema, loader, quality checks | ✅ |
| Phase 5 | Marketplace performance analytics: 4 KPI views, 5 analyses, reconciled to Python | ✅ |
| Phase 6 | Hyperlocal demand intelligence: real Bengaluru ward map, 5 analyses, heatmaps | ✅ |
| Phase 7 | Supply intelligence: supply map, partner time states, idle supply vs reach | ✅ |
| Phase 8 | Supply–demand imbalance: Marketplace Pressure Index, shortage types | ✅ |
| Phase 9 | Forecasting: week-ahead demand, supply and pressure | ✅ |
| Phase 10 | City-scale repositioning optimization, tested fairly against the status quo | ✅ |
| Phase 11 | Incentive economics and stress scenarios | ✅ |
| Phase 12 | Power BI executive dashboard | Next |

Stages 0–5 built and validated the optimizer core and the synthetic city; they
correspond to the early part of Phases 3 and 10.

## Results documents

Every result table is generated from data by a report script — never typed by hand.

| Document | What it shows | Regenerate |
|----------|---------------|------------|
| `10_Optimization/Validation_Results.md` | Optimizer proof on a 5-zone toy: hand calculation, stress tests, +9% vs naive dispatch on the toy, bottleneck pricing (city-scale results: Phase 10) | `python scripts/report_optimizer.py` |
| `03_Data_Engineering/Generation_Results.md` | Synthetic Bengaluru: planted patterns recovered, status-quo performance, the supply mismatch | `python scripts/report_generation.py` |
| `04_Data_Warehouse/Load_Results.md` | Warehouse: tables loaded, quality checks, SQL ↔ Python reconciliation | `python scripts/report_warehouse.py` |
| `05_Marketplace_Analytics/01_…05_*.md` | Baseline marketplace KPIs: overview, mobility, food, supply, economics | `python scripts/report_phase5.py` |
| `06_Demand_Intelligence/01_…05_*.md` | Demand map of Bengaluru, zone profiles, hourly patterns, pressure points, restaurants, rain | `python scripts/report_phase6.py` |
| `07_Supply_Intelligence/01_…05_*.md` | Supply map, partner time states, idle supply vs reach, empty km, vehicle eligibility | `python scripts/report_phase7.py` |
| `08_Supply_Demand_Imbalance/01_…05_*.md` | Pressure Index (validated), pressure map, shortage types and their levers, service and rain pressure | `python scripts/report_phase8.py` |
| `09_Forecasting/01_…04_*.md` | Forecast approach, demand and supply accuracy vs benchmark and noise floor, week-ahead shortage prediction | `python scripts/report_phase9.py` |
| `10_Optimization/01_…05_*.md` | City optimizer design, policy comparison with 95% ranges, where gains come from, repositioning, value of supply | `python scripts/tune_policy.py`, then `python scripts/report_phase10.py` |
| `11_Incentive_Economics/01_…03_*.md` | Incentive design, whether incentives pay, cost-per-job lever ladder, stress scenarios | `python scripts/report_phase11.py` |

## Key findings (synthetic Bengaluru, holdout weeks)

- **The problem is where supply is, not how much exists.** Partners are idle
  ~53% of their online time, yet only 72% of ride requests are completed;
  office-zone evening rides succeed only about 1 time in 5. Supply drifts with
  the commute: office zones hold 47% of partners at 09:00 but 3% at 19:00.
- **Shortages are predictable.** A week-ahead forecast flags 29% of zone-hours
  as short, and those zone-hours contain 91% of the jobs later lost.
- **Repositioning is a service lever, not a profit lever.** The optimizer cuts
  lost jobs by 13% at no measurable cost (+0.06% contribution, 95% range
  spanning zero); a service-first setting cuts them by 24% for about ₹17 per
  extra job served. The toy model's +9% did not survive realistic economics.
- **Standing incentives do not pay.** Guaranteed-hour bonuses serve many more
  customers but cost ₹43–55 per extra job; they come closest to paying on rain
  and festival days, which is when to use them.

All results are model-based estimates on synthetic data, not real-world impact.

## Repository layout

| Path | Contents |
|------|----------|
| `01_`–`12_` folders | Phase documentation, SQL, generated results and charts |
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
pytest                                 # 105 tests
python scripts/run_toy.py              # toy optimizer
python scripts/compare_policies.py     # optimizer vs baseline
python scripts/bottlenecks.py          # marginal value of supply
python scripts/build_all.py            # rebuild all Bengaluru data (~2-4 min)
python scripts/load_warehouse.py       # load SQL Server warehouse PULSE_DW
python scripts/report_phase5.py        # ... then report_phase6 to report_phase11 in order
```

Each `report_phaseN.py` reads the warehouse, rebuilds that phase's tables,
documents and charts; the "Results documents" table above lists them all.

Tested on Python 3.14.
