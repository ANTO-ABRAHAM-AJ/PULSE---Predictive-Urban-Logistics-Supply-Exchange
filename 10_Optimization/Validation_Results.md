# Phase 10 (early) — Optimizer Validation on a Toy Marketplace
## Stages 1–4: Correctness, Robustness, Value and Bottleneck Pricing

**Code:** `src/pulse/optimization/` · **Report script:** `scripts/report_optimizer.py`

---

## 1. Business Question

Before the optimizer is trusted with Bengaluru, does it make the right
allocation decisions, behave sensibly in extreme situations, beat naive
dispatch, and correctly identify where extra supply is worth the most?

---

## 2. Objective

Validate the supply allocation and repositioning model on a small marketplace
whose correct answer can be worked out by hand, following the locked
Development Strategy: build Phase 10 early, validate it, and only then scale.

---

## 3. Data Sources

- `data/sample/toy_lunch.yaml` — a hand-crafted weekday lunch hour
- `config/city.yaml`, `config/economics.yaml`, `config/operations.yaml` — toy
  distances, illustrative economics and eligibility rules

The toy has 5 zones: **A** office (large food shortage), **B** residential
(surplus two-wheelers, 2 km from A), **C** mixed, **D** restaurant cluster and
**E** an isolated suburb beyond the 4 km repositioning limit.

---

## 4. Analytical Grain

**Zone × Partner type × Service** for one planning period (one hour).
Decisions are numbers of partners moved between zones; the evaluator in
Stage 3 works at **individual request** level.

---

## 5. Techniques Used

- Linear programming with OR-Tools GLOP (continuous, so duals are valid)
- Hand calculation as the ground truth
- Scenario stress testing
- Independent evaluator with Poisson demand draws and common random numbers
- Shadow prices (duals) verified by re-solving with ±1 partner

---

# 6. Result Set A — Stage 1: Optimizer vs Hand Calculation

<!-- AUTO:stage1 -->
**Repositioning decided by the optimizer**

| From | To | Partner type | Service | Partners | Cost |
|---|---|---|---|---|---|
| B | A | two_wheeler | food | 8 | ₹80 |

**Economics vs hand calculation**

| Item | Optimizer | Hand calculation | Match |
|---|---|---|---|
| Contribution | ₹4,080 | ₹4,080 | ✅ |
| Repositioning cost | ₹80 | ₹80 | ✅ |
| Unserved penalty | ₹150 | ₹150 | ✅ |
| Objective | ₹3,850 | ₹3,850 | ✅ |

Unserved demand: E food = 6

_Generated 2026-10-03 by a report script — do not edit by hand._
<!-- /AUTO:stage1 -->

# 7. Result Set B — Stage 2: Stress Tests

<!-- AUTO:stage2 -->
| Scenario | Status | Objective | Unserved units | Repositioning cost | Expected behaviour |
|---|---|---|---|---|---|
| No supply | OPTIMAL | −₹2,505 | 95 | ₹0 | Nothing moves; all demand unserved |
| 10× supply | OPTIMAL | ₹4,320 | 0 | ₹0 | Everything served, no repositioning |
| A food = 1,000 (impossible) | OPTIMAL | −₹19,700 | 964 | ₹160 | All reachable two-wheelers do food; no crash |
| Free repositioning | OPTIMAL | ₹3,930 | 6 | ₹0 | Same service outcome, ₹80 better |
| C mobility 8 → 80 (spike) | OPTIMAL | ₹2,468 | 68 | ₹203 | A food stays fully served; only spare partners go to C |
| 80% food service floor | INFEASIBLE |  |  |  | Reported infeasible (E cannot reach 80%) |
| 100% mobility service floor | OPTIMAL | ₹3,850 | 6 | ₹80 | Floor met exactly |

_Generated 2026-10-03 by a report script — do not edit by hand._
<!-- /AUTO:stage2 -->

# 8. Result Set C — Stage 3: Optimized Plan vs Naive Dispatch

Both policies are scored by the same evaluator on **realized** demand, with
identical demand and arrival order per draw. The optimizer never scores itself.

<!-- AUTO:stage3 -->
| Metric (mean per lunch hour) | Baseline | Optimized |
|---|---|---|
| Contribution | ₹3,890 | ₹3,986 |
| Repositioning cost | ₹0 | ₹80 |
| Dispatch deadhead | ₹346 | ₹132 |
| Unserved penalty | ₹263 | ₹199 |
| **Net value** | ₹3,281 | ₹3,574 |
| Service level — mobility | 98.4% | 96.8% |
| Service level — food | 86.2% | 90.4% |
| Utilization | 83.1% | 85.2% |

**Uplift:** ₹293 per period (8.9% of baseline net), 95% CI ₹278 to ₹308. Optimized wins in **99%** of 500 demand draws.

_Generated 2026-10-03 by a report script — do not edit by hand._
<!-- /AUTO:stage3 -->

# 9. Result Set D — Stage 4: Marginal Value of Supply

Each row prices one partner three ways: the LP dual, the gain from re-solving
with one more partner, and the loss from one fewer. Because the objective is
concave in supply, **gain(+1) ≤ dual ≤ loss(−1)** must always hold; the tests
check it for every row.

<!-- AUTO:stage4 -->
| Zone | Partner type | Dual | Add +1 | Lose −1 | Add ≠ lose |
|---|---|---|---|---|---|
| A | two_wheeler | ₹10 | ₹10 | ₹10 |  |
| A | four_wheeler | ₹10 | ₹0 | ₹10 | yes |
| B | two_wheeler | ₹0 | ₹0 | ₹0 |  |
| B | four_wheeler | ₹0 | ₹0 | ₹0 |  |
| C | two_wheeler | ₹0 | ₹0 | ₹18 | yes |
| C | four_wheeler | ₹0 | ₹0 | ₹18 | yes |
| D | two_wheeler | ₹0 | ₹0 | ₹20 | yes |
| D | four_wheeler | ₹0 | ₹0 | ₹20 | yes |
| E | two_wheeler | ₹195 | ₹195 | ₹195 |  |
| E | four_wheeler | ₹0 | ₹0 | ₹180 | yes |

**Top bottlenecks (value of one more partner):** 1. Zone E two-wheeler — ₹195; 2. Zone A two-wheeler — ₹10

_Generated 2026-10-03 by a report script — do not edit by hand._
<!-- /AUTO:stage4 -->

---

# 10. Key Observations

### 10.1 The optimizer reproduces the hand answer exactly
It moves surplus two-wheelers from B to A for food, never sends
four-wheelers to food (ineligible) and sends nothing to E (unreachable).
Every economic component matches the hand calculation (Result Set A).

### 10.2 It fails safely
With no supply it moves no one; with excess supply it repositions no one;
impossible demand does not break it; and an unachievable service floor is
reported as **infeasible** rather than returning a misleading plan.

### 10.3 Services compete, and the optimizer chooses correctly
In the mobility-spike test, two-wheelers stay on food — where each earns
more per hour — and only spare partners cover the spike.

### 10.4 It beats naive dispatch, with an honest trade-off
The gain comes from moving partners once before the peak instead of paying
deadhead per order, and from reserving two-wheelers for food. Mobility
service level is slightly lower, because partners reserved on the forecast
cannot help when ride demand comes in above forecast.

### 10.5 Duals alone can hide risk
Where the solution is degenerate, adding a partner and losing one have
different values — e.g. an extra four-wheeler in E is worth nothing, but
losing one is costly. The dual reports only one side.

---

# 11. Business Interpretation

The allocation engine at the heart of PULSE is correct, robust and
economically sensible on a problem small enough to verify by hand. Its
advantage over naive dispatch comes from **anticipation** (positioning supply
before demand peaks) and **prioritisation** (putting scarce flexible partners
where they earn most).

---

# 12. Business Implication

- Phase 10B should report **both** the value of adding supply and the cost of
  losing it, not the dual alone.
- Forecast accuracy (Phase 9) directly limits the optimizer's benefit, because
  reservations are made on forecast demand.
- The headline Bengaluru figure must come from the city-scale run, not the toy.

---

# 13. Scope Control

This analysis intentionally does **not** include:

- City-scale optimization on Bengaluru data
- Multi-period repositioning
- Incentive economics or scenario re-optimization
- Power BI

These are addressed in Phases 10–12. Open items X-01 (one shared simulator for
baseline and optimizer) and X-02 (Bengaluru economics) in
`01_Business_Understanding/Assumptions.md` must be resolved first.

---

# 14. Reproducibility

```bash
pytest tests/test_optimization.py tests/test_evaluator.py tests/test_duals.py
python scripts/report_optimizer.py
```

The tests are the authoritative check; the report script regenerates every
table above from the code. Tables are never edited by hand.

---

## Conclusion

On a hand-verifiable toy marketplace, the PULSE optimizer is **correct**
(matches the hand calculation), **robust** (passes all stress tests),
**valuable** (beats naive dispatch on realized demand) and **diagnostic**
(identifies and prices bottlenecks, including hidden supply-loss risk).
It is ready to be scaled to Bengaluru once the open items are resolved.
