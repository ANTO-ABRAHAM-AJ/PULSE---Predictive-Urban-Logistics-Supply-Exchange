# PULSE — KPI Dictionary

**Status:** v0.1 — the single source of truth for every metric.

**Rules**
1. Each KPI is implemented **once**, as a T-SQL view (Phase 5). Power BI DAX
   measures aggregate those views; they never redefine the logic.
2. The KPI name here, the SQL column name and the DAX measure name match.
3. Default grain is **Zone × Hour × Service** unless stated.
4. Rates are computed from summed numerators and denominators, never by
   averaging rates (avoids misleading averages across zones).

---

## 1. Mobility

| KPI | Definition | Formula |
|-----|-----------|---------|
| Ride Requests | Ride requests created | `COUNT(request_id)` |
| Completed Rides | Requests that ended in a completed trip | `COUNT(request_id WHERE status = 'completed')` |
| Ride Completion Rate | Share of requests completed | `Completed Rides ÷ Ride Requests` |
| Ride Cancellation Rate | Share of requests cancelled, split by reason (customer / partner / no partner found) | `Cancelled Rides ÷ Ride Requests` |
| Avg Pickup ETA (min) | Time from assignment to partner arrival | `AVG(pickup_at − assigned_at)` |
| Avg Trip Distance (km) | Distance of completed trips | `AVG(trip_km)` |
| Ride GBV | Total fares paid by riders | `SUM(fare)` |
| Ride Platform Revenue | Fare kept by the platform | `SUM(fare − partner_payout)` |

## 2. Food delivery

| KPI | Definition | Formula |
|-----|-----------|---------|
| Food Orders | Orders placed | `COUNT(order_id)` |
| Delivered Orders | Orders delivered | `COUNT(order_id WHERE status = 'delivered')` |
| Food Completion Rate | Share of orders delivered | `Delivered Orders ÷ Food Orders` |
| Food Cancellation Rate | Share cancelled, split by reason (customer / restaurant / no partner) | `Cancelled Orders ÷ Food Orders` |
| Avg Prep Time (min) | Restaurant accept → food ready | `AVG(ready_at − accepted_at)` |
| Avg Delivery Time (min) | Order placed → delivered | `AVG(delivered_at − placed_at)` |
| GMV | Total order value | `SUM(order_value)` |
| AOV | Average order value | `GMV ÷ Delivered Orders` |
| Delivery Revenue | Commission + delivery fee kept by platform | `SUM(commission + delivery_fee − partner_payout)` |

## 3. Supply

| KPI | Definition | Formula |
|-----|-----------|---------|
| Online Partner-Hours | Hours partners were logged in | `SUM(online_minutes) ÷ 60` |
| Busy Partner-Hours | Hours on a job (assigned, on trip, delivering) | `SUM(busy_minutes) ÷ 60` |
| Idle Partner-Hours | Online but without a job | `Online − Busy − Repositioning` |
| Utilization | Share of online time spent on jobs | `Busy Partner-Hours ÷ Online Partner-Hours` |
| Empty km | Km driven without a passenger/order (pickup + repositioning) | `SUM(pickup_km + reposition_km)` |
| Repositioning km | Km driven moving between zones on platform instruction | `SUM(reposition_km)` |

## 4. Marketplace balance

| KPI | Definition | Formula |
|-----|-----------|---------|
| Demand | Ride requests + food orders (per service at service grain) | `Ride Requests` or `Food Orders` |
| Effective Capacity | Jobs the online, eligible supply could complete | `Σ eligible partner-hours × jobs per partner-hour` (Assumption O-01) |
| Shortage | Demand that capacity cannot cover | `MAX(0, Demand − Effective Capacity)` |
| Service Level | Share of demand completed | `Completed ÷ Demand` |
| **Marketplace Pressure Index (MPI)** | Demand relative to capacity | `Demand ÷ Effective Capacity` (undefined if capacity = 0 → flagged) |
| Pressure State | Classification of MPI | `Under-supplied` if MPI > 1.10 · `Balanced` if 0.80–1.10 · `Over-supplied` if < 0.80 (thresholds *illustrative*, reviewed in Phase 8) |

## 5. Economics

| KPI | Definition | Formula |
|-----|-----------|---------|
| Platform Revenue | Ride Platform Revenue + Delivery Revenue | sum |
| Incentive Cost | Bonuses and guarantees paid to partners | `SUM(incentive_amount)` |
| Repositioning Cost | Cost of platform-instructed moves | `SUM(reposition_km × cost_per_km)` |
| **Contribution** | What the marketplace earns after variable costs | `Platform Revenue − Incentive Cost − Repositioning Cost − Other Variable Cost` |
| Contribution per Job | Unit economics | `Contribution ÷ (Completed Rides + Delivered Orders)` |

## 6. Optimization (Phases 10–11)

| KPI | Definition | Formula |
|-----|-----------|---------|
| Optimized Net | Evaluator-scored net value of the optimized plan | from `evaluator.py` |
| Baseline Net | Evaluator-scored net value of naive dispatch | from `evaluator.py` |
| **Counterfactual Uplift** | Model-based gain vs baseline | `Optimized Net − Baseline Net` (also as % of Baseline Net), reported with a 95% interval |
| Win Rate | Share of demand draws where optimized beats baseline | `COUNT(uplift > 0) ÷ draws` |
| Marginal Value of Supply | Gain from one extra partner of a type in a zone | re-solve +1 (`duals.py`) |
| Supply Loss Risk | Loss from one fewer partner | re-solve −1 (`duals.py`) |

## 7. Forecasting (Phase 9)

| KPI | Definition | Formula |
|-----|-----------|---------|
| WAPE | Weighted absolute percentage error | `Σ|actual − forecast| ÷ Σ actual` |
| Bias | Systematic over/under-forecast | `Σ(forecast − actual) ÷ Σ actual` |
| Skill vs Naive | Improvement over seasonal-naive (same hour last week) | `1 − WAPE_model ÷ WAPE_naive` |

WAPE is used instead of MAPE because many Zone × Hour cells have zero demand,
where MAPE is undefined.
