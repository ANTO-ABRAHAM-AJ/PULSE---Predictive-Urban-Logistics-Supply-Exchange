# Phase 11 — Incentive Economics + Scenario Simulation
## 01. Incentive Design

**Code:** `src/pulse/optimization/incentives.py` · **Settings:** `config/bengaluru/policy.yaml`

---

## 1. Business Question

Phase 10 left two kinds of loss untouched: zones nobody can reach (the
airport) and hours when the whole city is short (the morning commute,
citywide shortages in Phase 8). Can paying partners to come online fix them
profitably?

---

## 2. The Incentive Modelled

A **guaranteed-hour bonus**: the platform secures extra two-wheeler partners
in a target zone for a time window and pays each a bonus per hour, **whether or
not they get jobs** — the conservative way to cost an incentive. The extra
partners start in the target zone, are dispatched like everyone else, and may
be repositioned by the Phase 10 policy.

---

## 3. Targeting — Without Looking at the Test Weeks

1. Run the Phase 10 profit policy on the **validation weekdays** (weeks 9–12).
2. Record the LP shadow price of one more two-wheeler in every zone and hour.
3. Target a zone-hour when its average value exceeds the bonus.
4. Size each target to cover the jobs still lost there (2 jobs per partner-hour,
   at most 6 partners); group consecutive hours into windows.

The holdout weeks are then simulated once with each programme.

---

## 4. Price Uncertainty (Assumption E-07)

What it costs to attract an extra partner for an hour is not known, so each
programme is tested at three prices — **₹40, ₹60 and ₹80 per partner-hour** —
and results are reported across that range. A higher price means fewer
zone-hours clear the value test, so the programme is smaller.

<!-- AUTO:targets -->
| Bonus per partner-hour | Zone-hours targeted | Partner-hours per weekday | Largest targets (partner-hours) |
|---|---|---|---|
| ₹40 | 211 | 799 | KIA (144), ECY (73), WHF (42), MAN (38), KRP (36) |
| ₹60 | 98 | 394 | KIA (144), ECY (42), WHF (27), BEL (19), MAN (19) |
| ₹80 | 62 | 266 | KIA (120), WHF (25), ECY (20), MAR (15), KRP (13) |

_Generated 2026-10-04 by a report script — do not edit by hand._
<!-- /AUTO:targets -->

---

## 5. Stress Scenarios

| Scenario | What changes |
|----------|--------------|
| Rain every day | Every day behaves like a rain day: rides +15%, food +30%, 20% fewer two-wheeler log-ins (Assumptions D-08, S-04) |
| Festival evening | Demand +40% from 17:00 to 22:00 across the city |
| Partner shortage | 15% of partner-days are lost (e.g. a strike or a holiday week) |
| Demand surge | All demand +20% |

Each is run under the status quo, the profit and service policies, and the
profit policy plus the ₹60 programme, on every second holdout day.

---

## 6. What the Model Does Not Capture

- **Partner response is assumed, not learned.** The model assumes partners can
  be secured at the tested price; the price range stands in for that uncertainty.
- **No crowding out of normal log-ins.** Incentive partners are assumed to be
  additional, not partners who would have logged in anyway.
- **Guaranteed-hour bonuses only.** Per-job boosts (paid only when a job is
  completed) could be cheaper, but would need a behavioural model of partner
  response that PULSE does not have.
