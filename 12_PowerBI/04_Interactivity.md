# Phase 12 — 04. Interactivity Set-up

How to build each interactive feature used in `03_Report_Pages.md`. Each
section is independent; do them in this order the first time.

| # | Feature | Where it is used |
|---|---|---|
| 1 | Real Bengaluru zone map (Shape Map) | Pages 1, 3, 4, 8, 10 |
| 2 | Map metric switch | Page 3 |
| 3 | What-if sliders: job value, bonus | Pages 7, 9 |
| 4 | Drillthrough to Zone Detail | Every zone visual |
| 5 | Report-page tooltips | Every map and zone visual |
| 6 | Bookmarks: how-to-read overlays, reset, story mode | Every page |
| 7 | Navigation: page navigator, finding buttons | Every page |
| 8 | Play axis animation | Page 4 |
| 9 | Colours driven by data | Pages 7, 9, 10 |
| 10 | Sync slicers, edit interactions | Pages 2–9 |
| 11 | Performance check and export | Before the screenshots |

---

## 1. Real Bengaluru zone map (Shape Map)

The map file is `map/bengaluru_zones.json`: the 24 PULSE zones built in
Phase 6 from the 243 BBMP ward boundaries (DataMeet, CC BY-SA 2.5 India),
converted to TopoJSON (the format the Shape Map needs) by
`src/pulse/geo/topojson.py`.

1. **File → Options and settings → Options → Preview features → Shape map
   visual** → tick, OK, restart Power BI Desktop if asked. (In versions where
   Shape Map is already general, skip this.)
2. Add a **Shape map** visual. Location: `Dim_Zone[zone_code]`. Color
   saturation: the page's measure (e.g. `[Lost Jobs per Day]`).
3. Format → **Map settings → Map type: Custom map → Add map type** → choose
   `map/bengaluru_zones.json`.
4. Format → Map settings → **View map keys**: the keys are `zone_code`
   (WHF, KIA, …), the same codes as `Dim_Zone[zone_code]`, so every zone matches.
5. Projection *Mercator*; Zoom off; Default colour `#1E293B`; border `#0B1220`.
6. Fill colours: min `#1E293B` → max `#F87171` (or diverging, page notes).

The airport zone (KIA) is a 2.5 km circle around the terminal, because it lies
outside BBMP ward limits (Assumption C-03). It looks detached in the north-east
on purpose.

---

## 2. Map metric switch

`Map Metric` is a disconnected table (01_Data_Model.md, section 8). A tile
slicer on `Map Metric[Metric]` changes what `[Map Value]` returns.

Because the metrics have different units, give `[Map Value]` a **dynamic
format string**: select the measure → Measure tools → Format → *Dynamic* →
paste:

```dax
SWITCH (
    SELECTEDVALUE ( 'Map Metric'[Metric], "Jobs lost per day" ),
    "Completion %", "0.0%",
    "Partners idle %", "0.0%",
    "Pressure index (MPI)", "0.00",
    "Value of one more partner-hour", "₹#,0",
    "#,0"
)
```

Map title: Format → Title → fx → Field value → `[Map Title]`.

---

## 3. What-if sliders

### 3.1 Value of a completed job (page 7)

**Modeling → New parameter → Numeric range**: name `Job Value`, data type
Whole number, min 0, max 100, increment 1, default 20, *Add slicer to this page*
on. Power BI creates the table `Job Value` and a slider.

How it works: for each policy,

> value-adjusted gain per day = contribution change per day + job value × extra completed jobs per day

(both against the status quo replay). `[Best Lever at Job Value]` evaluates
that for every actionable scenario and returns the highest. Where two lines
cross on the line chart is that pair's break-even job value
(`[Break-even Job Value]`; service vs profit is about ₹20).

Make the line chart show every job value while the slider still moves the
reference line: select the slider → **Format → Edit interactions** → on the
line chart click **None**. Because the chart now ignores the slider, a
constant line cannot follow it; instead add an X-axis constant line fixed at
the service-vs-profit break-even (about 19.5). The best-lever card next to the
chart is what follows the slider.

### 3.2 Bonus per partner-hour (page 9)

New parameter → Numeric range: name `Bonus`, min 0, max 100, increment 1,
default 60.

> net per day at bonus B = (revenue with the bonus programme − revenue without) ÷ days − B × bought partner-hours ÷ days

This holds the simulated ₹60 programme's partner-hours fixed and asks how much
those hours are worth; it is zero exactly at `[Break-even Bonus]`, the same
definition as Phase 11 (`11_Incentive_Economics/sql/02_stress_scenarios.sql`).
It does **not** model partners' response to a different bonus; the three
simulated programmes (₹40/60/80) do, on page 9's ladder.

Edit interactions as in 3.1 (slider → None on the line chart); the bar chart
keeps the interaction and recolours via `[Bonus Pays Colour]`.

---

## 4. Drillthrough to Zone Detail

1. On the **Zone Detail** page: Visualizations → *Drill through* → add
   `Dim_Zone[zone_label]`; *Keep all filters* on.
2. Power BI adds a back button (top left); restyle it to match.
3. Hide the page (right-click the tab → Hide page).
4. Test: on page 2 right-click a zone row → **Drill through → Zone Detail**.
   The whole page, including the dynamic `[Zone Headline]`, is for that zone.

Visuals that use `Dim_Zone[zone_code]` instead of `zone_label` also drill,
because both columns are in `Dim_Zone`; add `zone_code` to the drillthrough
well as well if Power BI does not offer it.

---

## 5. Report-page tooltips

1. Zone Tooltip page → Format page → **Page information → Allow use as tooltip** on;
   **Canvas settings → Type: Tooltip** (320 × 240).
2. Build it (03, last section). Hide the page.
3. On each map and zone visual: Format → General → **Tooltips → Type: Report
   page → Page: Zone Tooltip**.

Hovering a zone now shows its mini dashboard with an hourly sparkline. If the
Shape Map in your version shows only default tooltips, the tooltip page still
works on the matrices, tables and bar charts.

---

## 6. Bookmarks

Open **View → Bookmarks** and **View → Selection**.

### 6.1 "How to read this page" overlay (every page)

1. Add a rectangle (`#0B1220`, 10% transparency) covering the page, and on it a
   text box with three lines: what the page shows, how to interact, the one
   finding. Group them as **Info overlay**.
2. Selection pane: show the overlay → bookmark **"<Page> – how to read"**
   (options: uncheck *Data*, check *Display*, *Selected visuals*: the overlay
   only).
3. Hide the overlay → bookmark **"<Page> – hide help"** (same options).
4. Info button → Action → Bookmark "<Page> – how to read"; add a "Close"
   button on the overlay → Action → Bookmark "<Page> – hide help".

### 6.2 Reset

Set every slicer to its default → bookmark **"<Page> – reset"** with *Data* on
and *Current page* on. Reset button → that bookmark.

### 6.3 Story mode (for the interview)

Create six bookmarks, in order, each on its page with the slicers set:

| # | Bookmark | Page | State |
|---|---|---|---|
| 1 | The problem | Command Center | Service = all |
| 2 | Where supply is | Supply & Idle Partners | Play axis at 19 |
| 3 | What kind of shortage | Pressure Index | Shortage donut, Reposition ahead selected |
| 4 | Seen a week ahead | Forecast & Early Warning | Model = GBM + rain |
| 5 | The decision | Policy Simulator | Job value = ₹20 |
| 6 | When to pay | Incentives & Stress Tests | Bonus = ₹25 |

Group them as **Story**. In the Bookmarks pane, **View** runs them as a
slideshow; or add Insert → Buttons → Navigator → **Bookmark navigator** on
page 1 (group Story) so a viewer can click through the story.

---

## 7. Navigation

- **Page navigator** (shared layout): updates itself when pages are added,
  renamed or hidden.
- **Finding buttons** on page 1: Insert → Buttons → Blank, icon "→", Action
  *Page navigation*, destination pages 4, 6, 7, 9. Tooltip text: "Open the
  evidence".
- Ctrl+click follows buttons in Desktop; plain click in the service and PDF.

---

## 8. Play axis animation (page 4)

The scatter chart has a native **Play axis** well. Put `Dim_Time[hour_of_day]`
there; press ▶ and the 24 zones move through the day. Format → Play axis →
speed 1 s. Click a bubble to leave a trail (the zone's path through the day).
For the screenshot, pause at hour 19.

---

## 9. Colours driven by data

- **Scenario colours:** bar/column charts by scenario → Format → Columns →
  Colour → fx → Format style *Field value* → `[Scenario Colour]`. The colours
  live in `Dim_Scenario[colour]` (SQL), so every chart uses the same one per
  policy.
- **Bonus pays / does not:** same, with `[Bonus Pays Colour]`.
- **Playbook:** table cell background → fx → Field value → `[Playbook Colour]`.
- **Pressure heat map:** matrix → Cell elements → Background colour → fx →
  Gradient, *Add a middle colour*: 0.5 / 1.0 / 2.0 as in page 5.

For line charts with a legend, set each series colour once by hand to the
`Dim_Scenario[colour]` value (line charts do not take field-value colours per
series).

---

## 10. Sync slicers and edit interactions

- **View → Sync slicers**: sync `period`, `service_name`, `day_type` and
  `zone_type` across pages 2–5 (observed data). Do **not** sync them to pages 6–9,
  which use the holdout or simulated data.
- Page 7 and 9 sliders: interactions → None on the line charts (section 3).
- Page 6 model slicer: interactions → None on the WAPE-by-model bar chart.

---

## 11. Performance check, save and export

1. **Optimize → Performance analyzer → Start recording → Refresh visuals.**
   Every visual should render in well under a second (the model is about one
   million rows, in memory). Save a screenshot as `images/performance_analyzer.png`.
2. Save the report as `12_PowerBI/PULSE_Command_Center.pbix`.
3. **File → Export → Export to PDF** → `12_PowerBI/PULSE_Command_Center.pdf`, so
   readers without Power BI can see every page.
4. Screenshot each page in reading view (View → Fit to page, then hide the
   panes) into `12_PowerBI/images/pages/` with the names listed in the README.
