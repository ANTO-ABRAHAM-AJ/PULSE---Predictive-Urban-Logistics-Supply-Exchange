# Phase 12 — 03. Report Pages

Ten pages tell one story, from *what is wrong* to *what to do about it*, plus a
drillthrough page that works from every zone visual. This file describes the
report **as built**.

| # | Page | Question it answers | Phases |
|---|---|---|---|
| 1 | Command Center | What is the state of the marketplace, in four sentences? | all |
| 2 | Marketplace Performance | Which services, zones and hours fail customers? | 5 |
| 3 | Demand Map | Where and when does demand arrive? | 6 |
| 4 | Supply & Idle Partners | Where are partners, and why are they idle? | 7 |
| 5 | Pressure Index | Where is demand above supply, and what kind of shortage is it? | 8 |
| 6 | Forecast & Early Warning | Can we see shortages a week ahead? | 9 |
| 7 | Policy Simulator | Which policy wins, and at what value of a customer? | 10 |
| 8 | Repositioning Flows | Who moves where, and what is one more partner worth? | 10 |
| 9 | Incentives & Stress Tests | When does paying partners pay? | 11 |
| 10 | Decision Playbook | What should each zone do on Monday? | 8–11 |
| — | Zone Detail *(hidden, drillthrough)* | Everything about one zone | all |

Columns below are written Table[column]; measures are written [Measure]
and all come from `dax/PULSE_measures.dax`. Interactivity set-up (map, what-ifs, drillthrough,
tooltips, bookmarks) is in `04_Interactivity.md`.

---

## Shared layout (build once on page 1, then duplicate the page)

Canvas 16:9, custom size larger than 1280 × 720 (the same size on every page). Theme: **View → Themes → Browse for themes →**
`theme/PULSE_Command_Center.json`.

```
┌──────────┬──────────────────────────────────────────────────────────────┐
│  PULSE   │  Page title          slicers / sliders      ⟲ Reset (p. 7, 9)│  header
│ Command  ├──────────────────────────────────────────────────────────────┤
│ Center   │                                                              │
│          │                    page content                              │
│ ▸ pages  │                                                              │
│ (page    │                                                              │
│ navigator│                                                              │
│  button) │                                                              │
├──────────┴──────────────────────────────────────────────────────────────┤
│ Synthetic Bengaluru · model-based estimates · ward map CC BY-SA 2.5 IN   │  footer
└─────────────────────────────────────────────────────────────────────────┘
```

| Element | How |
|---|---|
| Left rail | Rectangle, fill `#0F1724`, full height |
| Logo text | Text box "PULSE" (Segoe UI Semibold 20, `#2DD4BF`) and "Command Center" (10, `#9CA3AF`) |
| Page navigator | Insert → Buttons → Navigator → **Page navigator** in the left rail; orientation vertical; hidden pages are left out automatically; selected state fill `#2DD4BF` |
| Page title | Text box, Segoe UI Semibold 18 + the page's question in 10 pt grey |
| Reset button (pages 7 and 9) | Insert → Buttons → Reset; action **Bookmark** "Reset – Policy Simulator" / "Reset – Incentives" |
| Footer | Text box, 8 pt `#6B7280`: *Synthetic Bengaluru — model-based estimates, not real-world impact. Ward boundaries: BBMP (2022), DataMeet Municipal Spatial Data, CC BY-SA 2.5 India.* |

Card style everywhere: **new Card visual**, callout 26 pt, category label
under the value, rounded corners 10 px (from the theme).

---

## Page 1 — Command Center

**Question:** What is the state of the marketplace, in four sentences?
**Window:** all 16 weeks (cards, map), holdout (policy headline).

```
┌───────┬───────┬───────┬───────┬───────┐
│ card  │ card  │ card  │ card  │ card  │   y 80-170
├───────┴───────┴──────┬┴───────┴───────┤
│                      │ Finding 1   →  │
│   Bengaluru map      │ Finding 2   →  │   y 180-560
│   jobs lost per day  │ Finding 3   →  │
│                      │ Finding 4   →  │
├──────────────────────┴────────────────┤
│ jobs per day by hour: completed vs lost (both services)                 │   y 570-690
└───────────────────────────────────────┘
```

| Visual | Fields | Settings |
|---|---|---|
| Card (new), 5 cards in one visual | `[Demand per Day]` "Jobs per day"; `[Ride Completion %]` "Rides completed" with reference label `[Food Delivered %]` "Food delivered"; `[Idle %]` "Partner time idle"; `[Lost Jobs per Day]` "Jobs lost to no partner, per day"; `[Revenue per Day]` "Platform revenue per day" | Expected over 16 weeks: 9,811 · 71.9% (food 93.7%) · 52.8% · about 940 · about ₹337k |
| Shape map | Location `Dim_Zone[zone_code]`; Color saturation `[Lost Jobs per Day]`; Tooltips `[Lost Jobs per Day]`, `[Completion %]`, `[MPI]`, `[Zone Playbook]` | Map `map/bengaluru_zones.json`; colours min `#1E293B`, max `#F87171`; drillthrough to Zone Detail |
| 4 × Card (new) with text | `[Headline Problem]`, `[Headline Forecast]`, `[Headline Optimizer]`, `[Headline Incentives]` | Callout 12 pt, left aligned, word wrap |
| Line and stacked column chart | X `Dim_Time[hour_label]`; columns `[Completed per Day]`, line `[Lost Jobs per Day]` | Column colour `#2DD4BF`, line `#F87171`, secondary axis on; title "A day in Bengaluru: jobs completed vs lost, per hour" |
| Slicer (tiles) | `Dim_Service[service_name]` | Top right of the header; single select off; on pages 1–6 only (pages 7–10 use simulated data with no service split) |

**Story:** Partners are idle more than half their time, yet more than a quarter
of ride requests fail. The map shows where; the four findings say what was
found and lead to the page that proves it.

---

## Page 2 — Marketplace Performance

**Question:** Which services, zones and hours fail customers? **Window:** 16 weeks.

| Visual | Fields | Settings |
|---|---|---|
| Slicers (dropdown) | `Dim_Time[period]`, `Dim_Service[service_name]`, `Dim_Time[day_type]`, `Dim_Zone[zone_type]` | Header row; sync to pages 3–5 (View → Sync slicers) |
| Card (new), 7 cards | `[Completion %]`, `[Lost to No Partner %]`, `[Customer Cancel %]`, `[Avg Pickup ETA (min)]`, `[Avg Order-to-Door (min)]`, `[Revenue per Completed Job]`, `[Take Rate %]` | |
| Matrix | Rows `Dim_Zone[zone_type]` → `Dim_Zone[zone_label]`; values `[Demand per Day]`, `[Completion %]`, `[Lost to No Partner %]`, `[Revenue per Day]` | Data bars on demand; background colour scale on Completion % (red low → teal high); +/- icons on; drillthrough to Zone Detail |
| Line chart | X `Dim_Time[hour_label]`; Y `[Completion %]`; legend `Dim_Service[service_name]` | Title "Completion by hour: rides fail in the evening peak" |
| **Decomposition tree** | Analyze `[Lost Jobs]`; Explain by `Dim_Service[service_name]`, `Dim_Zone[zone_type]`, `Dim_Zone[zone_label]`, `Dim_Time[daypart]`, `Dim_Time[day_type]`, `Dim_Time[weather]` | Lock the first level (Service); AI split "High value" on; title "Where do lost jobs come from? Click + to drill" |

**Story:** Food is fine (about 94% delivered); rides are the problem, and the
decomposition tree walks from *Mobility* to *Office zones* to the *Evening*
in three clicks.

---

## Page 3 — Demand Map

**Question:** Where and when does demand arrive? **Window:** 16 weeks.

| Visual | Fields | Settings |
|---|---|---|
| Slicer (tiles) | `Map Metric[Metric]` | Single select, default "Demand per day" |
| Slicer (between, slider) | `Dim_Time[hour_of_day]` | "Hours shown on the map" |
| Shape map | Location `Dim_Zone[zone_code]`; Color saturation `[Map Value]`; tooltips `[Lost Jobs per Day]`, `[Completion %]`, `[MPI]`, `[Zone Playbook]` | Title: fx → `[Map Title]` |
| Matrix heat map | Rows `Dim_Zone[zone_label]`; columns `Dim_Time[hour_of_day]`; values `[Demand per Day]` | Background colour scale (`#111A27` → `#F59E0B`), font colour same as background (cells become a pure heat map), column width 24; row subtotals off |
| Line chart, **small multiples** | X `Dim_Time[hour_label]`; Y `[Demand per Day]`; legend `Dim_Zone[zone_type]`; small multiples `Dim_Service[service_name]` | 2 panels side by side: commute peaks for rides, meal peaks for food |
| Card (new) | `[Rain Demand Uplift %]` "Extra demand on rain days" | |

**Interaction:** drag the hour slider from 07 to 10 and then 18 to 21: demand
moves from homes to offices and back. Switch the map metric to see completion,
idle supply or pressure on the same map.

---

## Page 4 — Supply & Idle Partners

**Question:** Where are partners, and why are they idle? **Window:** 16 weeks.

| Visual | Fields | Settings |
|---|---|---|
| Card (new), 5 cards | `[Avg Partners Online]`, `[Utilization %]`, `[Idle %]`, `[Idle Partner-Hours per Day]`, `[Empty km per Busy Hour]` | |
| 100% stacked area chart | X `Dim_Time[hour_of_day]`; Y `[Online Partner-Hours]`; legend `Dim_Zone[zone_type]` | Title "Supply follows the commute: office zones' share of partners by hour" |
| **Scatter chart with play axis** | Details `Dim_Zone[zone_code]`; X `[Idle %]`; Y `[Lost to No Partner %]`; size `[Demand per Day]`; legend `Dim_Zone[zone_type]`; **Play axis** `Dim_Time[hour_of_day]` | Category labels on; title "Press play: idle partners and lost jobs are in different zones at the same hour" |
| Stacked column chart | X `Dim_Time[hour_label]`; Y `[Avg Partners Online]`; legend `Dim_Vehicle[vehicle_name]` | |
| Shape map | Color saturation `[Idle %]`; same tooltip fields as page 1 | |

**Story:** Press play on the scatter. At 09:00 the office zones fill with
partners; at 19:00 they empty while customers there still need rides. The
problem is *where* supply is, not how much exists.

---

## Page 5 — Pressure Index

**Question:** Where is demand above supply, and what kind of shortage is it?
**Window:** 16 weeks.

| Visual | Fields | Settings |
|---|---|---|
| Card (new), 4 cards | `[City MPI]`, `[Under-supplied Zone-Hours %]`, `[Reposition-Ahead Share of Lost %]`, `[Citywide Share of Lost %]` | Expected 72.3% and 22.0% for the two shares |
| Matrix heat map | Rows `Dim_Zone[zone_label]`; columns `Dim_Time[hour_of_day]`; values `[MPI]` | Visual filter `Dim_Time[day_type]` = Weekday; background colour **diverging**: min 0.5 `#2DD4BF`, centre 1.0 `#FBBF24`, max 2.0 `#F87171`; title "Pressure index, weekdays (above 1.10 = under-supplied)" |
| Donut chart | Legend `Fact_Pressure[shortage_type]`; values `[Pressure Lost Jobs]`; tooltips `Fact_Pressure[lever]` | Detail labels "Category, percent of total" |
| Stacked bar chart | Y `Dim_Zone[zone_code]`; X `[Pressure Lost Jobs per Day]`; legend `Fact_Pressure[shortage_type]` | Sorted descending; KIA and ECY on top |
| Slicer (tiles) | `Dim_Time[day_type]` | Edit interactions → *None* on the cards, donut and bar, so they keep all-day values |
| **Line chart (danger zone)** | X `Dim_Time[hour_of_day]`; Y `[MPI]`; legend `Dim_Zone[zone_type]` | Y axis 0–3; Analytics → Y constant line 1.1 shaded *After* (red, 90% transparent) and 0.8 shaded *Before* (teal); title "When each zone type crosses the shortage line". Replaced a Key influencers visual, whose text could not be resized to be readable |

**Story:** Most lost jobs (about 72%) happen where the neighbourhood is short but
the city has spare partners: those can be fixed by moving partners *before* the
peak. About 22% need more partners online. The line chart shows offices and
transit hubs crossing the shortage line at the commute peaks.

---

## Page 6 — Forecast & Early Warning

**Question:** Can we see shortages a week ahead? **Window:** holdout weeks 13–16.

| Visual | Fields | Settings |
|---|---|---|
| Slicer (dropdown, single select) | `Dim_Forecast_Model[model_name]` | Default "GBM + rain" |
| Card (new), 7 cards in one row | `[WAPE %]`, `[Forecast Bias %]`, `[Skill vs Seasonal Naive %]`, `[Flag Rate %]`, `[Precision %]`, `[Recall %]`, `[Lost Jobs Captured %]` | Expected for GBM + rain: 25.6%, −0.7%, 31.1%, 28.8%, 80.1%, 69.6%, 90.7% |
| Clustered bar chart | Y `Dim_Forecast_Model[model_name]`; X `[WAPE %]` | **Edit interactions**: model slicer → *None* on this chart; colour: fx rules on `Dim_Forecast_Model[is_benchmark]` (grey benchmark) |
| Line chart | X `Dim_Time[date_value]`; Y `[Actual Demand]`, `[Forecast Demand]` | Title "Holdout weeks: actual demand vs week-ahead forecast" |
| Matrix | Rows `Fact_Pressure_Forecast[outcome]`; values `[Warning Zone-Hours]`, `[Warning Lost Jobs]`, `[Share of Warning Lost Jobs %]` | Title "Week-ahead warnings vs what actually happened"; data bars on lost jobs; expected 88.4% of lost jobs in correct warnings |

**Story:** The rain-aware model beats the benchmark by about 31%. More useful:
the warnings flag about 29% of zone-hours, and those hold about 91% of the jobs
later lost, so a planner can act a week early on a short list.

---

## Page 7 — Policy Simulator

**Question:** Which policy wins, and at what value of a customer?
**Window:** holdout weeks 13–16, all scenarios replay the same customers.

```
┌────────────────────────────┬──────────────────────────┐
│ Job value slider  ₹20      │ BEST LEVER AT ₹20:       │
│ ───────●────────────────   │ Optimizer (service)      │
├────────────────────────────┴──────────────────────────┤
│ value-adjusted gain per day vs job value (one line    │
│ per policy; crossings = break-even)                   │
├──────────────────────────┬────────────────────────────┤
│ scenario scorecard table │ jobs recovered % by zone   │
└──────────────────────────┴────────────────────────────┘
```

| Visual | Fields | Settings |
|---|---|---|
| Slicer (single value, slider) | `Job Value[Job Value]` | Created by the what-if parameter; title "What is one completed job worth to the business (future orders, retention)? ₹" |
| Card (new) | `[Best Lever at Job Value]`, reference label `[Best Lever Gain per Day]` | Title fx → `[Best Lever Title]` |
| **Line chart** | X `Job Value[Job Value]` (continuous); Y `[Actionable Gain per Day]` (blank for status quo and perfect forecast, so no visual filter is needed); legend `Dim_Scenario[scenario_short]` | **Edit interactions**: Job Value slider → *None* on this chart, so all values show; series colours to match `Dim_Scenario[colour]`; X-axis constant line fixed at 19.5 labelled "Service beats profit from here" (a constant line cannot follow the slider once the slider's interaction with this chart is None); title "Each line is a policy. Where lines cross, the better policy changes" |
| Table (scorecard) | `Dim_Scenario[scenario_name]`, `[Contribution per Day]`, `[Contribution Uplift per Day]`, `[Econ Lost Jobs vs SQ %]`, `[Econ Extra Completed per Day]`, `[Econ Moves per Day]`, `[Break-even Job Value]` | Font colour rules on `[Contribution Uplift per Day]` (green ≥ 0, red < 0); totals off; Job Value slider → *None*; break-even blank where it has no meaning (expected: Service ₹19.5, bonuses ₹50.0 / ₹44.4 / ₹58.2) |
| Slicer (tiles) | `Dim_Scenario[scenario_short]` | Single select, default Profit; Edit interactions → *None* on the line chart, table and card, so it drives the zone chart only |
| Clustered bar chart | Y `Dim_Zone[zone_code]`; X `[Jobs Recovered %]` | Sorted descending; title "Share of lost jobs won back, by zone"; under Profit MAJ and ECY ≈ 35–40%, KIA and KOR ≈ 0% |
| Reset button | Bookmark "Reset – Policy Simulator" (Job Value 20, Profit) | |

**Story:** At ₹0 per customer the profit policy is best (it is free). Move the
slider: above about ₹20 per completed job the service policy wins; incentives
only win when a customer is worth far more. The decision becomes a single
business input, not a modelling argument.

---

## Page 8 — Repositioning Flows

**Question:** Who moves where, and what is one more partner worth?
**Window:** holdout weeks 13–16.

| Visual | Fields | Settings |
|---|---|---|
| Slicer (tiles, single) | `Dim_Scenario[scenario_short]` | Filtered to Profit and Service; default Profit |
| Shape map | Color saturation `[Net Partners Moved In per Day]`; tooltips `[Net Partners Moved In per Day]`, `[Moves per Day]`, `[Avg Move km]` | Diverging: min `#2DD4BF` (net senders), centre 0 `#1E293B`, max `#F87171` (net receivers) |
| Column chart | X `Dim_Time[hour_of_day]`; Y `[Moves per Day]` | Colour `#C084FC`; title "Moves by hour: partners are sent ahead of the evening peak" |
| Matrix heat map | Rows `Dim_Zone[zone_code]`; columns `Dim_Time[hour_of_day]`; values `[Value of One More Two-Wheeler]` | Background scale `#111A27` → `#F59E0B`; title "₹ value of one more two-wheeler, weekday holdout (LP shadow price)" |
| **Matrix (who moves where)** | Rows `Dim_Zone[zone_code]`; columns `Dim_Destination_Zone[dest_zone_code]`; values `[Moves per Day]` | Background colour scale `#111A27` → `#C084FC`; subtotals off. Used instead of the AppSource "Flow Map" visual, which needs a sign-in; the report uses built-in visuals only |

**Story:** Moves peak around 09–10 and 17–19, just before the busy hours; the
profit policy makes about 86 moves a day, the service policy about 178. The heat map shows
where a partner is worth most, which is what Phase 11 used to target bonuses.

---

## Page 9 — Incentives & Stress Tests

**Question:** When does paying partners pay? **Window:** holdout; stress tests 14 days.

| Visual | Fields | Settings |
|---|---|---|
| Slicer (single value, slider) | `Bonus[Bonus]` | "Bonus per guaranteed partner-hour, ₹" |
| Card (new) | `[Stress Cases Paying at Bonus]` "of 5 situations, a bonus at this level pays" | |
| Clustered bar chart | Y `Stress_Cases[stress_label]`; X `[Break-even Bonus]` | Bar colour fx → field value `[Bonus Pays Colour]`; X-axis constant line fx `[Selected Bonus]`; title "Highest bonus that still pays, per situation" |
| Line chart | X `Bonus[Bonus]`; Y `[Incentive Net per Day at Bonus]`; legend `Stress_Cases[stress_label]` | Edit interactions: Bonus slider → *None*; Y constant line at 0; title "Net ₹ per day by bonus level: a bonus pays only above the line" |
| Clustered column chart | X `Stress_Summary[stress_label]`; Y `[Stress Lost per Day]`; legend `Stress_Summary[policy_label]` | Colours: status quo grey, profit teal, service orange, incentive purple |
| Bar chart (lever ladder) | Y `Dim_Scenario[scenario_short]`; X `[Net Cost per Recovered Job]` | Visual filter: Service, +₹40, +₹60, +₹80 bonus; title "Cost per job won back, vs profit repositioning"; expected ₹17, ₹49, ₹43, ₹55 |
| Reset button | Bookmark "Reset – Incentives" (Bonus 60) | |

**Story:** Slide the bonus down from ₹60. At about ₹26 bonuses start to pay on
festival evenings and rain days; at ₹16 even on a normal day. Standing
programmes at ₹40–80 do not pay: use bonuses as a surge tool.

---

## Page 10 — Decision Playbook

**Question:** What should each zone do on Monday?

| Visual | Fields | Settings |
|---|---|---|
| Card (new), 3 cards (the lever ladder) | `[Ladder Profit Uplift per Day]` "1 · Profit repositioning: contribution per day"; `[Ladder Service Cost per Job]` "2 · Service repositioning: ₹ per job won back"; `[Ladder Bonus Cost per Job]` "3 · ₹60 bonus: ₹ per job won back" | Arrow shapes between cards; accent colours teal, orange, purple; expected +₹205, ₹16.8, ₹43.1 |
| Table (the playbook) | `Dim_Zone[zone_label]`, `Dim_Zone[zone_type]`, `[Lost Jobs per Day]`, `[Reposition-Ahead Share of Lost %]`, `[Citywide Share of Lost %]`, `[Jobs Recovered %]`, `[Zone Playbook]` | Visual filter `Dim_Scenario[scenario_code]` = optimizer_profit (total 935 lost per day, 13.0% won back); background fx on `[Zone Playbook]` → field value `[Playbook Colour]`; totals off; drillthrough to Zone Detail |
| Text box | Five recommendations (below) | |
| Text box | Limitations | |

**The five playbook actions** (`[Zone Playbook]`, in the order they are tested):
pre-position before the peak (profit policy wins back ≥ 20%); service setting
(profit policy skips the zone but the service setting wins back ≥ 10%);
repositioning cannot fix it (neither does); targeted bonus (≥ 30% of losses are
citywide shortages); otherwise repositioning plus same-hour dispatch.

**Recommendations text (keep it this short):**

1. **Run profit repositioning every day.** It wins back about 13% of lost jobs at
   no measurable cost.
2. **Switch to the service setting** if a completed job is worth more than about
   ₹20 to the business (Policy Simulator).
3. **Pre-position before the peak, not during it**, using the week-ahead
   warnings (they hold about 91% of lost jobs).
4. **Pay bonuses only on rain and festival days**, below about ₹25 per hour;
   never as a standing programme.
5. **Station dedicated supply at the red zones**, starting with the airport
   (KIA), where neither repositioning policy wins back jobs.

**Limitations:** synthetic city; model-based estimates; one replay of four
holdout weeks; partners assumed to follow every move.

---

## Zone Detail — drillthrough page (hidden)

**Drillthrough field:** `Dim_Zone[zone_label]` (keep all filters on). Page type
**Drillthrough**; Power BI adds the back button automatically.

| Visual | Fields |
|---|---|
| Title card | `[Zone Headline]` (dynamic sentence; tells the reader to drill through when no zone is chosen) |
| Card (new), 6 cards | `[Demand per Day]`, `[Completion %]`, `[Lost Jobs per Day]`, `[Idle %]`, `[MPI]`, `[Zone Playbook]` |
| Line and clustered column | X `Dim_Time[hour_of_day]`; columns `[Demand per Day]`; line `[Avg Partners Online]` |
| Stacked column | X `Dim_Time[hour_of_day]`; Y `[Pressure Lost Jobs per Day]`; legend `Fact_Pressure[shortage_type]` |
| Clustered bar | Y `Dim_Scenario[scenario_short]`; X `[Scenario Lost Jobs per Day]`; colour fx `[Scenario Colour]` |
| Column chart | X `Dim_Time[hour_of_day]`; Y `[Value of One More Two-Wheeler]` |

Right-click any zone in a map, matrix, table or bar → **Drill through → Zone Detail**.

---

## Tooltips (built-in)

A report-page tooltip (320 × 240) was tried and dropped: it was cramped and the
Shape Map ignores it. Each zone visual instead carries **tooltip fields**:

| Visual | Tooltip fields |
|---|---|
| Maps on pages 1, 3, 4; zone bars on pages 5 and 7 | `[Lost Jobs per Day]`, `[Completion %]`, `[MPI]`, `[Zone Playbook]` |
| Net-inflow map on page 8 | `[Net Partners Moved In per Day]`, `[Moves per Day]`, `[Avg Move km]` |

Tooltip background `#111A27` (Format → General → Tooltips).
