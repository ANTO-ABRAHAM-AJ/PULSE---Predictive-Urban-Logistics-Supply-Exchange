# Data Generation Framework

Documentation only. Generator code lives in `src/pulse/generation/`; generated
files go to `data/processed/` (gitignored). Every rule references an ID in
`01_Business_Understanding/Assumptions.md`.

## Stage 5a — City and hourly demand (built)

| Piece | Code | Config | Assumptions |
|-------|------|--------|-------------|
| Zones, distances, travel time | `generation/city.py` | `config/bengaluru/zones.yaml` | C-01 … C-07 |
| Calendar (weekend, rain, events, history/holdout) | `generation/demand.py` | `config/bengaluru/demand.yaml` | T-01 … T-03, D-08, D-10 |
| Hourly demand per Zone × Hour × Service | `generation/demand.py` | `config/bengaluru/demand.yaml` | D-01 … D-09 |

**Geometry source.** Zone centroids are approximate locality centres (±1 km),
entered by hand. They are adequate for distances and travel times. Boundary
polygons for the Phase 6–7 maps will come from public ward/locality boundary
data; the exact dataset and licence will be recorded here when added.

**How demand is built.** For each date, zone and service:
`expected(hour) = daily base × city scale × weekend multiplier × hour profile
× zone-type hour modifier × rain × event × hidden day noise`, then realized
demand = Poisson(expected).

**Truth vs realized.** `_truth_demand_hourly.csv` holds the expected rates and
exists only to validate the generator. Analytics, forecasting and the
warehouse use `demand_hourly.csv` only.

**Validation.** `tests/test_generation.py` checks every planted pattern against
realized data (commute peaks, lunch/dinner peaks, office weekday lunch rush,
residential dinner, restaurant weekend nights, rain uplift, event spikes,
airport isolation).

**Run:** `python scripts/generate_demand.py`

## Stage 5b — Supply and event-level operations (next)

Partners, shifts, home zones, request/order events, assignments,
cancellations, fares and payouts.
