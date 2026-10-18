# Scripts

Entry points. Run from the repository root after `pip install -e .`, for
example `python scripts/run_toy.py`. Scripts that read the warehouse need
SQL Server and `PULSE_DW` (`config/warehouse.yaml`).

## Optimizer core on the toy model (Stages 0–4)

| Script | What it does |
|---|---|
| `run_toy.py` | Solve the 5-zone toy lunch instance and print the allocation |
| `compare_policies.py` | Optimized plan vs naive baseline on many demand draws |
| `bottlenecks.py` | Where one more partner creates the most value (shadow prices) |
| `report_optimizer.py` | Regenerate `10_Optimization/Validation_Results.md` |

## Synthetic Bengaluru (Phase 3)

| Script | What it does |
|---|---|
| `build_all.py` | Rebuild the whole dataset in order (runs the four below) |
| `generate_demand.py` | Zones, distances, calendar, hourly demand |
| `generate_supply.py` | Partner fleet and baseline hourly supply |
| `generate_events.py` | Simulate every ride and food order under status-quo dispatch |
| `generate_entities.py` | Attach customers and restaurants to every job |
| `build_zone_geometry.py` | Build zone polygons from public BBMP ward boundaries (Phase 6 maps) |
| `report_generation.py` | Regenerate `03_Data_Engineering/Generation_Results.md` |

## Warehouse and analysis (Phases 4–12, run in order)

| Script | What it does |
|---|---|
| `load_warehouse.py` | Create `PULSE_DW`, load, index and run quality checks |
| `report_warehouse.py` | Regenerate `04_Data_Warehouse/Load_Results.md` |
| `report_phase5.py` … `report_phase9.py` | Rebuild each phase's views, tables, documents and charts |
| `tune_policy.py` | Choose repositioning settings on validation weeks (run once before Phase 10) |
| `report_phase10.py` | Simulate the policies on the holdout weeks and report |
| `report_phase11.py` | Incentive programmes and stress scenarios |
| `report_phase12.py` | Power BI semantic layer, map file and DAX-vs-SQL checks |
