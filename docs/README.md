# Documentation assets

Graphics used by the front-page `README.md`. Each comes in a dark and a light
version; GitHub shows the one that matches the reader's theme.

| File | What it shows |
|---|---|
| `assets/banner-*.svg` | Title banner: the 24 Bengaluru zones shaded by jobs lost per day |
| `assets/kpis-*.svg` | The six headline numbers, grouped Diagnose / Predict / Decide |
| `assets/lever-ladder-*.svg` | Jobs won back and cost per extra job for each lever |
| `assets/data/zone_lost_jobs.csv` | Zone values behind the banner map (refreshed from `PULSE_DW` when available) |

Rebuild them with:

```bash
python scripts/build_readme_assets.py
```

The full write-ups live in the phase folders: start with
`01_Business_Understanding/01_Business_Problem.md`.
