# PULSE — Assumptions Log

**Status:** v0.1 — written before the data generator (Stage 5). Every rule the
synthetic city follows is listed here. Numeric values live in `config/`;
this file explains *why* each value exists and where it is used.

**How to use this file**
- Each assumption has an ID (e.g. `D-03`). Code comments and docs refer to it by ID.
- Values marked *illustrative* are reasonable placeholders, not market data.
  They are calibrated in Stage 5 and stress-tested in Phase 11.
- If an assumption changes, update it here **first**, then the config.

---

## 1. Marketplace model

| ID | Assumption | Rationale |
|----|-----------|-----------|
| M-01 | PULSE is one super-app operator running mobility and food delivery on a shared partner pool. | The locked business model; makes shared-supply allocation a real decision. |
| M-02 | Two partner types: **two-wheeler** (mobility + food) and **four-wheeler cab** (mobility only). | Eligibility becomes an explicit optimization constraint. |
| M-03 | Two-wheeler mobility means bike-taxi rides. This is a modeling assumption, not a statement about current Karnataka regulation. | Keeps the shared-pool trade-off; flagged so it isn't read as a market claim. |
| M-04 | Partners serve one service at a time and are assigned per planning period. | Matches the LP's period-level decision. |

## 2. City, zones and travel

| ID | Assumption | Rationale |
|----|-----------|-----------|
| C-01 | The city is **Bengaluru**, split into ~24 operating zones built from well-known localities. | Real geography recruiters recognize; small enough to optimize and explain. |
| C-02 | Each zone has one type: `office`, `residential`, `mixed`, `restaurant_cluster`, or `transit_hub`. | Zone type drives demand shape (§4). |
| C-03 | Zone geometry comes from public boundary data (ward/locality boundaries); zones are clusters of these. Exact source is recorded in `03_Data_Engineering/Data_Generation_Framework.md`. | Real shapes for the Power BI maps. |
| C-04 | Road distance = straight-line distance between zone centroids × **1.4** detour factor (*illustrative*). | Simple, transparent proxy without a routing engine. |
| C-05 | Average speed depends on hour: **15 km/h** at peak (8–11, 17–21 weekdays), **25 km/h** otherwise (*illustrative*). | Bengaluru peak congestion matters for ETAs and repositioning reach. |
| C-06 | Repositioning is allowed only if travel time ≤ **20 minutes** (τ), so reach shrinks at peak. | Replaces the toy's fixed 4 km limit with a time-based rule. |

Initial zone list (types to be confirmed in Stage 5):

| Type | Zones |
|------|-------|
| office | Whitefield, Manyata Tech Park, Electronic City, Bellandur–ORR, CBD (MG Road) |
| restaurant_cluster | Koramangala, Indiranagar, HSR Layout |
| residential | Jayanagar, JP Nagar, Banashankari, Rajajinagar, Malleshwaram, Yelahanka, BTM Layout, Basavanagudi |
| mixed | Marathahalli, Hebbal, Sarjapur Road, KR Puram, Yeshwanthpur, Bannerghatta Road |
| transit_hub | Majestic (KSR / Kempegowda Bus Station), Airport Road (Hebbal–Yelahanka corridor) |

## 3. Time

| ID | Assumption | Rationale |
|----|-----------|-----------|
| T-01 | Planning period = **1 hour**. | Matches the LP and forecasting grain. |
| T-02 | Simulation horizon = **12 weeks** of history + held-out weeks for testing. | Enough weekly cycles for forecasting backtests. |
| T-03 | Demand exists 24 hours but is near zero 01:00–06:00. | Keeps the time dimension complete for SQL and Power BI. |

## 4. Demand rules (the patterns the analytics must later rediscover)

Expected demand per **Zone × Hour × Service** =
`base rate(zone type, service) × hour profile(day type, service) × day effects × noise`

| ID | Rule |
|----|------|
| D-01 | **Weekday mobility** peaks 08–10 and 17–20 (commute). |
| D-02 | **Food** peaks 12–14 (lunch) and 19–22 (dinner) every day. |
| D-03 | **Office zones**: strong weekday lunch food and evening mobility out; weekend demand drops to ~30%. |
| D-04 | **Residential zones**: morning mobility out, dinner-heavy food; weekends higher than weekdays. |
| D-05 | **Restaurant clusters**: highest food density (restaurants are there); late-night food and weekend nights strongest. |
| D-06 | **Transit hubs**: mobility-heavy, flatter through the day, spikes early morning and late evening. |
| D-07 | **Weekends**: mobility shifts later (leisure, 11–14 and 18–23); food dinner peak grows ~25%. |
| D-08 | **Rain days**: food +30%, mobility +15%, two-wheeler supply −20% (*illustrative*). More likely June–October. |
| D-09 | **Noise**: Poisson counts around the expected rate, plus a hidden day-level multiplier (lognormal, σ ≈ 0.10) not given to any model. Prevents forecasting from being trivial. |
| D-10 | A small number of **event nights** (e.g. stadium matches near CBD) add a local mobility + food spike. Dates are generated, not real fixtures. |

## 5. Supply rules

| ID | Assumption |
|----|-----------|
| S-01 | Partners have a **home zone**, weighted toward residential and peripheral zones. Supply starts where partners live, not where demand is — this creates the repositioning problem. |
| S-02 | Partners work **shifts**: morning, lunch–dinner split, evening, or full day, with daily log-in probability < 1. |
| S-03 | Fleet mix: roughly **70% two-wheelers / 30% four-wheelers** (*illustrative*). |
| S-04 | Rain reduces two-wheeler log-ins (see D-08); four-wheeler supply is unaffected. |
| S-05 | Partner states: `offline`, `available`, `assigned`, `on_trip`, `delivering`, `repositioning`. Idle = available with no job. |

## 6. Operations

| ID | Assumption |
|----|-----------|
| O-01 | Planning capacity: one partner completes **2 rides** or **3 deliveries** per hour (carried from the toy model). The event-level simulation uses actual trip durations; this ratio is the planning approximation. |
| O-02 | Restaurant prep time: 10–30 minutes, longer at peak. |
| O-03 | Pickup ETA = pickup distance ÷ hour-specific speed (C-05). |
| O-04 | Cancellation probability rises with waiting time (logistic curve); unassigned requests cancel after **10 minutes** (mobility) or **15 minutes** (food). |

## 7. Economics (all INR, *illustrative*, calibrated in Stage 5)

| ID | Item | Initial assumption |
|----|------|--------------------|
| E-01 | Mobility fare | Base + per-km rate; four-wheeler fares higher than two-wheeler. |
| E-02 | Food order value | Average order ~₹400, platform commission ~20%, plus a delivery fee. |
| E-03 | Partner payout | Per-trip / per-delivery base + per-km component. |
| E-04 | **Contribution per unit** = platform revenue − partner payout − variable cost. This is the `contribution_per_unit` in `config/economics.yaml`. |
| E-05 | **Unserved penalty** = lost contribution proxy for future churn. It is a business judgement, so Phase 11 tests sensitivity to it. |
| E-06 | **Repositioning cost** = per-km cost by vehicle type (fuel + partner time compensation). |
| E-07 | **Incentives** (Phase 11): extra online partner-hours supplied per ₹ of incentive follow a diminishing-returns curve. The curve is an assumption; results are reported across a range. |

## 8. Planted truths for validation

The Stage 5 exit check confirms the generated data shows these, and later
phases must rediscover them **without being told**:

1. Weekday lunch food shortage in office zones (Whitefield, Manyata, Electronic City).
2. Weekday evening mobility pressure leaving office zones.
3. Dinner food pressure in residential zones; supply concentrated in the wrong places at the wrong hours.
4. Rain days create two-wheeler shortages across food-heavy zones.
5. Weekend restaurant-cluster night peaks.

## 9. Known limitations

- Synthetic data: results are **model-based estimates**, not real-world causal impact.
- Travel times use a detour factor, not real road routing.
- Economic values are illustrative; conclusions are reported with sensitivity ranges.
- Partner behavior (acceptance, log-in, incentive response) is rule-based, not learned from real partners.
