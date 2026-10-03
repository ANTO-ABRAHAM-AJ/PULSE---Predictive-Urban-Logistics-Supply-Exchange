# Phase 6 — Hyperlocal Demand Intelligence

**Question answered:** *Where and when, exactly, is demand?* — at
**Zone × Hour × Service** grain, on a real map of Bengaluru.

![Demand Map of Bengaluru](./images/charts/demand_map.png)

## How it is built

| Layer | File | Purpose |
|-------|------|---------|
| Geography | `scripts/build_zone_geometry.py` → `config/bengaluru/zone_boundaries.geojson` | 24 zone polygons built from the 243 real BBMP wards (2022) |
| Analyses | `sql/01_…` to `sql/05_…` | One file per analysis; Result Sets A and B |
| Chart data | `sql/06_zone_hour_matrix.sql` | Zone × hour weekday matrix for the maps and heatmaps |
| Findings | `01_…md` to `05_…md` | ORGEE format; tables, headlines and charts generated |
| Evidence | `images/` (SSMS screenshots), `images/charts/` (generated) | |

```bash
python scripts/build_zone_geometry.py   # once: zone polygons from public ward data
python scripts/report_phase6.py         # all five documents + map + heatmaps
```

## Analyses

| # | Document | Business question |
|---|----------|-------------------|
| 01 | `01_Zone_Demand_Profile.md` | Which zones generate demand, for which service, and when do they peak? |
| 02 | `02_Time_of_Day_Patterns.md` | How does each zone type's demand move through the day? |
| 03 | `03_Demand_Pressure.md` | Where and when does demand go unserved? |
| 04 | `04_Restaurant_Density.md` | Where are restaurants, and how concentrated is food demand? |
| 05 | `05_Demand_Growth_and_Variability.md` | Is demand growing, and how sensitive is it to rain? |

## Geography and attribution

Zone polygons group real **BBMP ward boundaries (2022 delimitation)** to the
nearest PULSE zone centre; wards more than 6 km from any centre are left out
(shown grey). Kempegowda Airport lies outside BBMP limits and is drawn as a
2.5 km circle. Source: [DataMeet Municipal Spatial Data](https://github.com/datameet/Municipal_Spatial_Data/tree/master/Bangalore),
scraped from KSRSAC, licensed **CC BY-SA 2.5 India**. The derived file
`config/bengaluru/zone_boundaries.geojson` is shared under the same licence.
