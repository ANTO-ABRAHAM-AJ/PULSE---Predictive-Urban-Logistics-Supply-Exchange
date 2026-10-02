"""Stage 3: the evaluator must be trustworthy before we use it to compare policies."""
import sys
from pathlib import Path

import numpy as np
import pytest

from pulse.optimization import (baseline_plan, evaluate, optimized_plan,
                                solve_allocation)
from pulse.utils import load_instance

ROOT = Path(__file__).resolve().parents[1]
TOY = ROOT / "data" / "sample" / "toy_lunch.yaml"
sys.path.insert(0, str(ROOT / "scripts"))
from compare_policies import compare  # noqa: E402


@pytest.fixture(scope="module")
def inst():
    return load_instance(TOY)


def test_evaluator_agrees_with_lp_when_reality_equals_forecast(inst):
    """If realized demand equals the forecast, the evaluator must reproduce
    the LP's own objective (3850). This proves both use the same economics."""
    plan = optimized_plan(inst)
    res = evaluate(inst, plan, inst["demand"], np.random.default_rng(0))
    assert res.net == pytest.approx(solve_allocation(inst).objective)
    assert res.unserved["E", "food"] == 6


def test_every_request_is_either_served_or_unserved(inst):
    """Conservation: no request is lost or double counted."""
    realized = {z: {s: 7 for s in inst["services"]} for z in inst["zones"]}
    for plan in (baseline_plan(inst), optimized_plan(inst)):
        res = evaluate(inst, plan, realized, np.random.default_rng(1))
        for z in inst["zones"]:
            for s in inst["services"]:
                assert res.served[z, s] + res.unserved[z, s] == 7


def test_same_seed_gives_identical_results(inst):
    """Common random numbers only work if evaluation is reproducible."""
    plan = baseline_plan(inst)
    a = evaluate(inst, plan, inst["demand"], np.random.default_rng(5))
    b = evaluate(inst, plan, inst["demand"], np.random.default_rng(5))
    assert a.net == b.net and a.served == b.served


def test_baseline_never_repositions(inst):
    assert baseline_plan(inst)["move_cost"] == 0


def test_optimizer_beats_baseline_on_realized_demand(inst):
    """Stage 3 exit criterion: across many noisy demand draws the optimized
    plan earns more on average and wins the large majority of draws."""
    rows = compare(inst, draws=200, seed=7)
    diff = np.array([o.net - b.net for o, b in zip(rows["optimized"], rows["baseline"])])
    assert diff.mean() > 0
    assert np.mean(diff > 0) > 0.9
