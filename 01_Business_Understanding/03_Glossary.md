# Phase 1 — 03. Glossary

Plain-language meanings of the terms used across PULSE. Exact formulas are in
`KPI_Dictionary.md`; the rules behind them are in `Assumptions.md`.

**Jump to:** [Marketplace](#marketplace) · [Supply](#supply) ·
[Pressure and shortages](#pressure-and-shortages) · [Forecasting](#forecasting) ·
[Optimization](#optimization) · [Incentives and stress tests](#incentives-and-stress-tests) ·
[Data and reporting](#data-and-reporting)

---

## Marketplace

| Term | Meaning | Where |
|---|---|---|
| **Job** | One ride request or one food order | All phases |
| **Service** | Mobility (rides) or food delivery | All phases |
| **Zone** | One of 24 operating areas of Bengaluru, built from BBMP ward boundaries | Phase 3, 6 |
| **Zone type** | Office, residential, restaurant cluster, mixed or transit hub; drives the shape of demand | Assumptions C-02 |
| **Zone-hour** | One zone in one hour, the basic unit of analysis (Zone × Time × Service) | All phases |
| **Daypart** | A block of the day: night (00–05), morning (06–10), midday (11–16), evening (17–21), late evening (22–23) | Phase 12 |
| **Demand** | Jobs requested, whatever happened to them | KPI Dictionary §4 |
| **Completion %** | Share of jobs completed (rides) or delivered (food) | KPI Dictionary §1–2 |
| **Lost to no partner** | A job cancelled because no eligible partner could arrive within 20 minutes; the failure PULSE targets | Assumptions O-04 |
| **Customer cancel** | A job cancelled by a customer tired of waiting; rises with waiting time | Assumptions O-04 |
| **Pickup ETA** | Minutes from assignment to the partner arriving | KPI Dictionary §1 |
| **Order-to-door** | Minutes from a food order being placed to delivery | KPI Dictionary §2 |
| **AOV** | Average order value of delivered food orders | KPI Dictionary §2 |
| **Take rate** | Platform revenue as a share of gross value (fares + order values) | Phase 5 |
| **Platform revenue** | What PULSE keeps after paying partners: fare minus payout, or commission plus delivery fee minus payout | KPI Dictionary §5 |
| **Contribution** | Platform revenue minus repositioning and incentive costs; the money test for every lever | KPI Dictionary §5 |

## Supply

| Term | Meaning | Where |
|---|---|---|
| **Partner** | A driver or delivery rider; one job at a time | Assumptions S-01 to S-05 |
| **Eligibility** | Two-wheelers serve rides and food; cabs serve rides only | Assumptions M-02 |
| **Home zone** | Where a partner starts each day; weighted to residential and outer zones | Assumptions S-01 |
| **Partner-hour** | One partner online for one hour | Phase 7 |
| **Online / busy / idle** | Logged in / on a job / logged in without a job | KPI Dictionary §3 |
| **Utilization** | Busy time ÷ online time | KPI Dictionary §3 |
| **Idle %** | Idle time ÷ online time; 52.8% citywide | Phase 7 |
| **Empty km** | Kilometres driven without a passenger or order: pickup drives plus repositioning | KPI Dictionary §3 |
| **Reach** | How far a partner can be sent: 20 minutes of driving, so about 5 km at weekday peak and 8.3 km otherwise | Assumptions C-06 |
| **Supply drift** | Partners ending up where their last job ended, so supply follows yesterday's demand, not the next hour's | Phase 7 |

## Pressure and shortages

| Term | Meaning | Where |
|---|---|---|
| **MPI (Marketplace Pressure Index)** | Work requested ÷ partners present, where work = rides ÷ 2 + orders ÷ 3. Above 1 means more work than supply | Phase 8 |
| **Local / neighbourhood / city MPI** | The same ratio for one zone, for all zones within 20 minutes, or for the whole city | Phase 8 |
| **Pressure state** | Under-supplied (MPI > 1.10), balanced (0.80–1.10), over-supplied (< 0.80) | KPI Dictionary §4 |
| **Shortage type** | Which lever can fix an under-supplied zone-hour: fix now, reposition ahead or citywide shortage | Phase 8 |
| **Fix now** | The neighbourhood has spare partners; better same-hour dispatch is enough (1% of lost jobs) | Phase 8 |
| **Reposition ahead** | The neighbourhood is short but the city is not; move partners *before* demand arrives (72% of lost jobs) | Phase 8, 10 |
| **Citywide shortage** | The whole city is short; only more partners online can help (22% of lost jobs) | Phase 8, 11 |

## Forecasting

| Term | Meaning | Where |
|---|---|---|
| **Week-ahead forecast** | A forecast of each zone-hour made a full week in advance | Phase 9 |
| **History / validation / holdout weeks** | Weeks 1–8 to learn, weeks 9–12 to choose settings, weeks 13–16 to test once | Phase 9, 10 |
| **Seasonal naive** | The benchmark: same hour last week | Phase 9 |
| **GBM + rain** | The chosen model: gradient boosting with calendar and rain features | Phase 9 |
| **WAPE** | Total absolute error ÷ total actual; used instead of MAPE because many zone-hours have zero demand | KPI Dictionary §7 |
| **Bias** | Whether forecasts run high or low overall | KPI Dictionary §7 |
| **Skill vs seasonal naive** | How much smaller the error is than the benchmark's (31%) | Phase 9 |
| **Warning (flag)** | A zone-hour predicted to be under-supplied | Phase 9 |
| **Flag rate** | Share of zone-hours flagged (28.8%) | Phase 9 |
| **Precision / recall** | Share of warnings that came true (80.1%) / share of real shortages that were warned (69.6%) | Phase 9 |
| **Lost jobs captured** | Share of later lost jobs that fell in flagged zone-hours (90.7%) | Phase 9 |

## Optimization

| Term | Meaning | Where |
|---|---|---|
| **Repositioning** | Moving idle partners to another zone ahead of demand, on platform instruction | Phase 10 |
| **LP (linear program)** | The optimization model, solved with OR-Tools each hour, that decides how many partners to move where | Phase 10 |
| **Dispatch reach** | Partners can serve a nearby zone without moving, at reduced capacity because of the pickup drive | Assumptions O-08 |
| **Status quo** | What history contains: nearest-partner dispatch, no repositioning | Assumptions O-05 |
| **Profit policy** | Repositioning that moves a partner only if the expected revenue covers the cost of the move | Phase 10 |
| **Service policy** | Repositioning that also values each served job at ₹20 of goodwill, so it moves partners more often | Phase 10 |
| **Perfect forecast** | The profit policy given the true future demand; an upper bound, not a real option | Phase 10 |
| **Replay with common random numbers** | Every policy faces exactly the same customers and orders, so differences come from the policy alone | Phase 10 |
| **95% range** | The spread of daily results; a gain whose range spans zero is "no measurable change" | Phase 10 |
| **Shadow price** | From the LP: what one more partner in a zone-hour would add to contribution | Phase 10, 12 |
| **Value of a completed job** | What one more served customer is worth to the business (retention, future orders). A judgement, set with the Policy Simulator slider | Phase 12 |
| **Break-even job value** | The job value above which a costlier policy beats the profit policy; about ₹19.5 for the service policy | Phase 10, 12 |
| **Net cost per recovered job** | Extra cost of a policy ÷ extra jobs it serves, both against the profit policy | Phase 11, 12 |

## Incentives and stress tests

| Term | Meaning | Where |
|---|---|---|
| **Guaranteed-hour bonus** | An incentive: a payment per hour to bring extra two-wheelers online in a target zone-hour, paid whether or not they get jobs | Assumptions E-07 |
| **Incentive programme** | A bonus level (₹40, ₹60 or ₹80) applied to the zone-hours with the highest value of supply | Phase 11 |
| **Break-even bonus** | The highest bonus per partner-hour at which the extra revenue still covers the cost; about ₹16 on a normal day, ₹26 on festival evenings | Phase 11, 12 |
| **Stress case** | A tested situation: normal, rain every day, festival evening, partner shortage, demand surge | Assumptions E-08 |
| **Lever ladder** | Levers ranked by cost per job won back: profit repositioning (free), service repositioning (about ₹17), bonuses (₹43–55) | Phase 11, 12 |

## Data and reporting

| Term | Meaning | Where |
|---|---|---|
| **Synthetic city** | Simulated Bengaluru data with known rules, so the analysis can be checked against the truth | Phase 3 |
| **Planted truth** | A pattern deliberately built into the data that later phases must rediscover | Assumptions §8 |
| **Model-based estimate** | A result from simulation, not measured real-world impact | All phases |
| **PULSE_DW** | The SQL Server data warehouse: star schema of facts and dimensions | Phase 4 |
| **Fact / dimension** | A table of events or measures (rides, orders, partner-hours) / a table describing them (zone, time, service) | Phase 4 |
| **Semantic layer** | The `pbi` SQL views shaped for Power BI | Phase 12 |
| **DAX measure** | A Power BI calculation; each one aggregates the SQL definition, never redefines it | Phase 12 |
| **Reconciliation** | Proving the same number in two systems: SQL vs Python (Phases 4–5), DAX vs SQL (Phase 12) | Phases 4, 5, 12 |
| **Zone playbook** | The recommended action for each zone, chosen by rules on its shortage mix and what each policy recovers | Phase 12 |
| **Drillthrough** | Right-clicking a zone in Power BI to open a page about that zone | Phase 12 |

Related: `01_Business_Problem.md` · `02_Operating_Model.md`.
