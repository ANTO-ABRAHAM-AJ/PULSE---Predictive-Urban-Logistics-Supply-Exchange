# Phase 3 — Data Engineering (Synthetic Bengaluru)

**Question answered:** *Can a realistic two-service marketplace be simulated,
with known rules, so every later analysis can be checked against the truth?*

24 zones from real BBMP ward boundaries, 16 weeks, 850 partners, about 60,000
customers, 1,035 restaurants, and about 1.1 million ride requests and food
orders, all simulated under status-quo dispatch.

## Documents

| Document | What it covers |
|---|---|
| `Data_Generation_Framework.md` | How the city, demand, supply and every job are generated; each rule cites an ID in `01_Business_Understanding/Assumptions.md` |
| `Generation_Results.md` | Checks that the planted patterns appear, status-quo performance, and the supply mismatch the project sets out to fix |

## How it is built

| Layer | Location |
|---|---|
| Generator code | `src/pulse/generation/` |
| Settings | `config/bengaluru/` |
| Output | `data/processed/` (gitignored; rebuilt in about 2–4 minutes) |

```bash
python scripts/build_all.py          # demand -> supply -> events -> customers and restaurants
python scripts/report_generation.py  # regenerate Generation_Results.md
```
