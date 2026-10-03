# Phase 9 — Demand & Supply Forecasting
## 01. Forecasting Approach

**Code:** `src/pulse/forecasting/` · **Pipeline:** `scripts/report_phase9.py`

---

## 1. Business Question

What does PULSE need to know in advance to act before demand arrives — and
how can it be forecast honestly?

---

## 2. Why Forecast

Phases 7 and 8 showed that most lost demand needs supply moved **before**
the peak: at the moment of failure, spare partners are too far away. Acting
early needs a forecast of three things for every zone and hour:

| Forecast | Grain | Used for |
|----------|-------|----------|
| **Demand** | zone × hour × service | how much work is coming |
| **Baseline supply** | home zone × hour × vehicle | where partners will start, before any moves |
| **Pressure** | zone × hour | which zone-hours will be short (Phase 10 targets) |

---

## 3. Data

<!-- AUTO:data -->
| Dataset | History rows | Holdout rows |
|---|---|---|
| Demand (zone x hour x service) | 96,768 | 32,256 |
| Baseline supply (home zone x hour x vehicle) | 96,768 | 32,256 |
| Pressure (zone x hour) | 48,384 | 16,128 |

_Generated 2026-10-03 by a report script — do not edit by hand._
<!-- /AUTO:data -->

- **Training:** the 12 history weeks. **Test:** the 4 holdout weeks, never
  seen during fitting.
- Every zone-hour is present, **including zero-demand hours**, so the models
  learn when demand is absent as well as when it is high.

---

## 4. Models

| Model | How it forecasts | Role |
|-------|------------------|------|
| Seasonal naive | same hour, same weekday, one week earlier | **benchmark** (KPI_Dictionary.md §7) |
| 4-week mean | average of the same hour over the previous four weeks | simple smoother |
| History profile | average for the zone, service, hour and day type over the history weeks | structural baseline |
| GBM calendar | gradient-boosted trees (Poisson loss) on zone, zone type, service, hour, day of week, weekend and scheduled-event flags | machine learning, **no weather** |
| GBM + rain | the same, plus the day's rain flag | machine learning **with a weather forecast** |

**Baseline supply** uses a seasonal naive benchmark and history profiles by
home zone, vehicle, hour and day type (with and without rain).

**Pressure** combines the GBM calendar demand forecast with a history profile
of partners present in each zone, and flags zone-hours whose forecast MPI
exceeds 1.10 (the Phase 8 threshold).

---

## 5. Honest Design Choices

### 5.1 No information from the future
Models are fitted once on history and never see holdout data. Benchmarks use
only demand from at least seven days before the target hour.

### 5.2 Rain is kept separate
A week-ahead rain forecast is not perfect in reality, so the rain-aware model
is reported separately. The pressure forecast for Phase 10 uses the
calendar-only model, so it does not depend on knowing the weather.

### 5.3 Recent-demand lags were tested and rejected
Adding last week's demand as a feature made the gradient-boosting model
*worse*: in a marketplace without a trend, one week's random swings are
noise. The final models rely on structure (zone, service, hour, day type)
plus events and weather.

### 5.4 A known floor on accuracy
Because the data is synthetic, the true expected demand of every zone-hour is
known. Its error against actual demand is the **noise floor** — the part of
the error that is pure randomness and that no model can remove. Reporting it
shows how close the models are to the best possible.

---

## 6. Metrics

From KPI_Dictionary.md §7:

- **WAPE** = Σ |forecast − actual| ÷ Σ actual — used instead of MAPE because
  many zone-hours have zero demand.
- **Bias** = (Σ forecast − Σ actual) ÷ Σ actual — over- or under-forecasting.
- **Skill vs naive** = 1 − WAPE_model ÷ WAPE_naive.
- For pressure: **precision**, **recall** and the **share of lost jobs** in
  zone-hours flagged as short.

---

## 7. Scope Control

Phase 9 forecasts; it does not decide moves (Phase 10) or incentives
(Phase 11). Forecasts are stored in the warehouse for both, and for the Power
BI forecast page (Phase 12).
