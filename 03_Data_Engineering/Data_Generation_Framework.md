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

## Stage 5b (part 1) — Partner fleet and baseline supply (built)

| Piece | Code | Config | Assumptions |
|-------|------|--------|-------------|
| Partners: vehicle, home zone, shift, eligibility | `generation/supply.py` | `config/bengaluru/supply.yaml` | M-02, S-01 … S-03 |
| Daily log-ins (weekday/weekend, rain) | `generation/supply.py` | `config/bengaluru/supply.yaml` | S-02, S-04 |
| Baseline online partners per Date × Hour × Zone × Vehicle | `generation/supply.py` | — | S-01, S-05 |

**Baseline supply** means partners counted in their *home* zone during their
shift hours, before any repositioning or dispatch. It is what Phase 9
forecasts and what Phase 10 decides how to move.

**Fleet sizing.** `partners_at_scale_1 × city_scale` (650 at the default 0.5),
chosen so the city as a whole is roughly balanced at dinner. Shortages are
mostly spatial: at weekday lunch, office zones need several times more
partners than live there while residential zones have a surplus.

**Validation.** `tests/test_supply.py` checks fleet mix, eligibility, home-zone
distribution, 24-hour coverage, rain effect on two-wheelers only, the office
lunch mismatch, and citywide dinner balance.

**Run:** `python scripts/generate_supply.py` (after `generate_demand.py`)

## Stage 5b (part 2) — Event-level operations (next)

Individual rides and orders with timestamps, destinations, fares, prep times,
assignments, pickup ETAs, cancellations and payouts.
