# Phase 5 — Marketplace Performance Analytics

**Question answered:** *What is happening?* — the baseline performance of the
PULSE marketplace under status-quo dispatch, measured from `PULSE_DW`.

## How it is built

| Layer | File | Purpose |
|-------|------|---------|
| KPI views | `sql/00_create_kpi_views.sql` | Four views at Zone × Hour grain holding sums (never rates). The single source of truth for every KPI and for Power BI. |
| Analyses | `sql/01_…` to `sql/05_…` | One file per analysis; each returns Result Set A and B. |
| Findings | `01_…md` to `05_…md` | ORGEE-format write-up; tables and headline numbers are generated. |
| Evidence | `images/` | SSMS screenshots of each result set. |

```bash
python scripts/report_phase5.py     # create/update the views, regenerate all five documents
```

## KPI views

| View | Grain | Key columns |
|------|-------|-------------|
| `dw.vw_Mobility_ZoneHour` | pickup zone × hour | requests, completed, cancellations by reason, ETA sum, km, GBV, payout, revenue |
| `dw.vw_Food_ZoneHour` | customer zone × hour | orders, delivered, cancellations by reason, prep / order-to-door sums, GMV, commission, fee, payout, revenue |
| `dw.vw_Supply_ZoneHour` | zone × hour × vehicle | partner-hours, online / busy / idle hours, empty km |
| `dw.vw_Marketplace_ZoneHour` | zone × hour × service | demand, completed, lost to no partner, gross value, payout, revenue |

Rates are always computed as `SUM(numerator) / SUM(denominator)` at the level
being reported (KPI_Dictionary.md rule 4).

## Analyses

| # | Document | Business question |
|---|----------|-------------------|
| 01 | `01_Marketplace_Overview.md` | How big is the marketplace and how well does it serve demand? |
| 02 | `02_Mobility_Performance.md` | Where and when do ride requests fail? |
| 03 | `03_Food_Delivery_Performance.md` | How reliable and fast is food delivery, and where does it fail? |
| 04 | `04_Supply_Utilization.md` | Is the problem too few partners, or partners in the wrong place? |
| 05 | `05_Marketplace_Economics.md` | Where does the marketplace's contribution come from? |
