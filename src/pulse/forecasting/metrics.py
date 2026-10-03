"""Forecast accuracy metrics (KPI_Dictionary.md, section 7)."""
import numpy as np


def wape(actual, forecast) -> float:
    """Weighted absolute percentage error: sum|F - A| / sum(A), in %."""
    a, f = np.asarray(actual, float), np.asarray(forecast, float)
    return float(100 * np.abs(f - a).sum() / a.sum())


def bias(actual, forecast) -> float:
    """(sum F - sum A) / sum A, in %. Positive = over-forecast."""
    a, f = np.asarray(actual, float), np.asarray(forecast, float)
    return float(100 * (f.sum() - a.sum()) / a.sum())


def skill(model_wape: float, benchmark_wape: float) -> float:
    """Share of the benchmark's error removed, in % (1 - model / benchmark)."""
    return float(100 * (1 - model_wape / benchmark_wape))
