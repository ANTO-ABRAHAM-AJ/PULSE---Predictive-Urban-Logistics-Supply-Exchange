# Stage 5 — Synthetic Bengaluru Marketplace: Generation Results
## Planted Patterns, Status-Quo Performance and the Supply Mismatch

**Code:** `src/pulse/generation/` · **Report script:** `scripts/report_generation.py`

---

## 1. Business Question

Does the synthetic Bengaluru marketplace behave like a real two-service
marketplace — and does it contain the operational problem PULSE is meant to
solve?

---

## 2. Objective

Verify that every demand pattern planted in the generator appears in the
realized data, measure how the marketplace performs under status-quo dispatch,
and quantify where and when supply and demand are mismatched.

---

## 3. Data Sources

Generated files in `data/processed/` (built by `python scripts/build_all.py`):

- `demand_hourly.csv` — realized demand per Zone × Hour × Service
- `supply_hourly.csv` — baseline online partners per home zone and hour
- `rides.csv`, `food_orders.csv` — every ride request and food order
- `partner_hourly.csv` — partner location, busy and online minutes per hour

Only **realized** data is used; the generator's hidden expected rates
(`_truth_demand_hourly.csv`) are deliberately excluded, exactly as later
analytics will exclude them.

---

## 4. Analytical Grain

- Demand patterns: **Zone × Hour × Service** (hourly counts)
- Operations: **individual ride or order**
- Supply: **partner × hour**

---

## 5. Techniques Used

- Ratio tests on realized demand against thresholds set before generation
- Weekday / weekend, rain / dry and event / normal comparisons
- Supply–demand pressure: partners needed (rides ÷ 2 + orders ÷ 3, Assumption
  O-01) divided by partners available
- Completion and cancellation rates by zone type and hour

---

# 6. Result Set A — Dataset at a Glance

<!-- AUTO:overview -->
| Item | Value |
|---|---|
| Simulated period | 01 Jun 2026 – 20 Sep 2026 (112 days: 84 history, 28 holdout) |
| Zones | 24 Bengaluru zones |
| Ride requests | 477,426 |
| Food orders | 621,451 |
| Jobs per day (average) | 9,811 |
| Partners | 850 |
| Customers | 60,001 |
| Restaurants | 1,035 |
| Rain days / event days | 36 / 6 |

_Generated 2026-10-03 by a report script — do not edit by hand._
<!-- /AUTO:overview -->

# 7. Result Set B — Planted Demand Patterns Recovered

<!-- AUTO:planted -->
| Pattern | Measure | Observed | Required | Recovered |
|---|---|---|---|---|
| Weekday commute peaks (D-01) | Two busiest weekday ride hours | 9:00, 18:00 | in 08–10 or 17–20 | ✅ |
| Office lunch rush (D-03) | Office lunch orders, weekday ÷ weekend | 7.9× | > 4× | ✅ |
| Office evening exodus (D-03) | Office rides, 17–19 ÷ 08–10 (weekday) | 3.0× | > 1.5× | ✅ |
| Residential dinner (D-04) | Residential orders, 19–21 ÷ 12–13 (weekday) | 2.4× | > 1.5× | ✅ |
| Restaurant-cluster nights (D-05) | Late-night orders, weekend ÷ weekday | 2.1× | > 1.5× | ✅ |
| Rain lifts food (D-08) | Weekday food orders, rain ÷ dry day | 1.29× | > 1.15× | ✅ |
| Stadium nights (D-10) | CBD rides 21–24, event ÷ normal night | 2.3× | > 1.8× | ✅ |

_Generated 2026-10-03 by a report script — do not edit by hand._
<!-- /AUTO:planted -->

# 8. Result Set C — Status-Quo Marketplace Performance

<!-- AUTO:operations -->
| KPI | Value |
|---|---|
| Ride completion rate | 71.9% |
| Rides cancelled — no partner | 19.4% |
| Rides cancelled — customer | 8.7% |
| Average pickup ETA (completed rides) | 8.9 min |
| Average trip distance | 6.6 km |
| Food delivery rate | 93.7% |
| Average order-to-door time | 29.2 min |
| Average order value | ₹397 |
| Partner utilization (busy ÷ online) | 47.2% |
| Partner busy time per ride / delivery | 27 min / 17 min |

_Generated 2026-10-03 by a report script — do not edit by hand._
<!-- /AUTO:operations -->

# 9. Result Set D — Weekday Lunch Pressure by Zone Type (12:00–14:00)

<!-- AUTO:lunch_pressure -->
| Zone type | Partners needed / hour | Partners living there / hour | Pressure (needed ÷ available) | State |
|---|---|---|---|---|
| office | 86 | 13 | 6.68 | Under-supplied |
| restaurant_cluster | 49 | 26 | 1.85 | Under-supplied |
| transit_hub | 16 | 9 | 1.71 | Under-supplied |
| mixed | 59 | 126 | 0.47 | Over-supplied |
| residential | 66 | 253 | 0.26 | Over-supplied |

Citywide pressure at lunch: **0.65** (thresholds from KPI_Dictionary.md: > 1.10 under-supplied, < 0.80 over-supplied).

_Generated 2026-10-03 by a report script — do not edit by hand._
<!-- /AUTO:lunch_pressure -->

# 10. Result Set E — Weekday Evening Ride Completion (17:00–20:00)

<!-- AUTO:evening_rides -->
| Zone type | Ride requests | Completed | No partner |
|---|---|---|---|
| office | 30,722 | 21.5% | 70.6% |
| transit_hub | 13,207 | 51.5% | 30.9% |
| mixed | 20,032 | 62.6% | 24.8% |
| restaurant_cluster | 10,064 | 69.0% | 18.1% |
| residential | 15,895 | 87.5% | 0.5% |

_Generated 2026-10-03 by a report script — do not edit by hand._
<!-- /AUTO:evening_rides -->

---

# 11. Key Observations

### 11.1 Every planted pattern is recovered
Commute peaks, the office lunch rush, the evening exodus from offices,
residential dinner demand, weekend restaurant nights, rain and stadium
nights all appear in realized data (Result Set B). The generator does what the
assumptions say.

### 11.2 Food is served well; mobility is not
Most food orders are delivered, but a large share of ride requests fail —
mostly because no partner can reach the customer in time (Result Set C).

### 11.3 Supply is concentrated where partners live, not where demand is
At weekday lunch, office zones need several times more partners than live
there, while residential and mixed zones hold a large surplus (Result Set D).
The city as a whole is close to balanced.

### 11.4 The evening exodus is the sharpest failure
Weekday evening rides leaving office zones mostly fail, while rides from
residential zones at the same hour almost all succeed (Result Set E).

### 11.5 Idle supply coexists with unserved demand
Partners are idle for roughly half their online time during the same hours
that requests elsewhere go unserved.

---

# 12. Business Interpretation

The marketplace's problem is **where and when** supply sits, not **how much**
supply exists. Status-quo dispatch never moves partners ahead of demand, so
they wait in residential areas while office zones run short.

---

# 13. Business Implication

This mismatch is exactly what the Phase 10 allocation and repositioning
optimizer is designed to fix. It also defines what Phases 5–8 must quantify:
demand maps, supply maps and a pressure index at Zone × Time × Service grain.

---

# 14. Calibration Decisions Made During Generation

| Change | Why | Effect |
|--------|-----|--------|
| Fleet 650 → 850 partners | First sizing used the planning ratio only; the event simulation showed travel and idle time reduce effective capacity | Ride completion ~59% → ~72% |
| Ride wait limit 15 → 20 min | At 15 km/h peak speed, 15 minutes covers only ~4 km, making evening completion unrealistically low | Peak-hour completion raised to plausible levels |
| Just-in-time food dispatch | Partners were idling at restaurants during prep, which real platforms avoid | Food partner busy time per delivery ~25 → ~17 min |
| Destination distance decay 10 → 5 km | Trips averaged too long for city rides | Average trip ~7 km |

Planning ratio O-01 (2 rides or 3 deliveries per partner-hour) was confirmed by
the simulation's measured busy time per job (Result Set C).

---

# 15. Scope Control

This analysis intentionally does **not** include:

- Warehouse KPIs (Phase 5), demand and supply maps (Phases 6–7)
- The Marketplace Pressure Index at full Zone × Hour grain (Phase 8)
- Forecasting, optimization or incentives (Phases 9–11)

All figures describe a **synthetic** marketplace under status-quo dispatch —
a model of the "before PULSE" world, not real-world measurements.

---

# 16. Reproducibility

```bash
python scripts/build_all.py          # regenerate the data (fixed seeds)
pytest tests/test_generation.py tests/test_supply.py tests/test_events.py
python scripts/report_generation.py  # regenerate every table above
```

Fixed random seeds make the data identical on every machine. Tables are never
edited by hand.

---

## Conclusion

The synthetic Bengaluru marketplace reproduces every planted demand pattern
and, under status-quo dispatch, shows a clear spatial and temporal supply
mismatch: idle partners in residential zones while office-zone demand goes
unserved. This is the problem PULSE exists to solve.
