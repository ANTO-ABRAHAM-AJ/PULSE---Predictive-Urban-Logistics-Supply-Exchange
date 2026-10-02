"""Load shared parameters (config/) and scenario data into one instance dict."""
from __future__ import annotations

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = REPO_ROOT / "config"


def _read_yaml(path: Path) -> dict:
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_config(config_dir: Path | str = CONFIG_DIR) -> dict:
    """Merge city, economics and operations config into one dict."""
    config_dir = Path(config_dir)
    cfg: dict = {}
    for name in ("city", "economics", "operations"):
        cfg.update(_read_yaml(config_dir / f"{name}.yaml"))
    return cfg


def _full_distance_matrix(zones: list[str], upper: dict) -> dict:
    """Mirror the upper-triangle distances and set the diagonal to 0."""
    dist = {i: {j: None for j in zones} for i in zones}
    for i in zones:
        dist[i][i] = 0.0
    for i, row in upper.items():
        for j, d in row.items():
            dist[i][j] = float(d)
            dist[j][i] = float(d)
    missing = [(i, j) for i in zones for j in zones if dist[i][j] is None]
    if missing:
        raise ValueError(f"Missing distances for zone pairs: {missing}")
    return dist


def build_instance(cfg: dict, data: dict) -> dict:
    """Combine config + period data into the structure the model expects."""
    zones = list(cfg["zones"])
    inst = {
        "period": data.get("period", ""),
        "zones": zones,
        "services": list(cfg["services"]),
        "partner_types": list(cfg["partner_types"]),
        "eligibility": cfg["eligibility"],
        "distance_km": _full_distance_matrix(zones, cfg["distance_km"]),
        "max_reposition_km": float(cfg["max_reposition_km"]),
        "jobs_per_partner": cfg["jobs_per_partner_per_period"],
        "contribution": cfg["contribution_per_unit"],
        "penalty": cfg["unserved_penalty_per_unit"],
        "cost_per_km": cfg["reposition_cost_per_km"],
        "min_service_level": cfg["min_service_level"],
        "supply": data["supply"],
        "demand": data["demand"],
    }
    _validate(inst)
    return inst


def _validate(inst: dict) -> None:
    for z in inst["zones"]:
        for k in inst["partner_types"]:
            if inst["supply"][z][k] < 0:
                raise ValueError(f"Negative supply at {z}/{k}")
        for s in inst["services"]:
            if inst["demand"][z][s] < 0:
                raise ValueError(f"Negative demand at {z}/{s}")
    for s, a in inst["min_service_level"].items():
        if not 0.0 <= a <= 1.0:
            raise ValueError(f"min_service_level for {s} must be in [0, 1]")


def load_instance(data_path: Path | str, config_dir: Path | str = CONFIG_DIR) -> dict:
    """Load config + a period data file (e.g. data/sample/toy_lunch.yaml)."""
    return build_instance(load_config(config_dir), _read_yaml(Path(data_path)))
