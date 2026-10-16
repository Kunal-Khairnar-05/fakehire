"""Model quality gate: CI fails if a newly trained model is worse than these floors.

train.py writes ml/models/model_<version>.metrics.json. In CI the model is retrained
from scratch before this runs, so these numbers are always fresh.
The floors sit a little below today's results (full F1 ~0.80, short PR-AUC ~0.62),
so normal noise passes but a real regression fails.
"""
import json
from pathlib import Path

import pytest

METRICS = Path(__file__).resolve().parents[1] / "models" / "model_v1.1.metrics.json"

pytestmark = pytest.mark.skipif(not METRICS.exists(), reason="no metrics file; run ml/train.py")


def product(test_set: str) -> dict:
    """The 'what users get' row (rules + model) for the full or short test set."""
    metrics = json.loads(METRICS.read_text())
    return next(row for row in metrics["product"] if row["test set"] == test_set)


def test_full_postings_f1_floor():
    assert product("full")["f1"] >= 0.75


def test_full_postings_false_alarm_ceiling():
    # Flagging real postings as scams erodes trust: at most 2% of real postings
    assert product("full")["false_alarm_rate"] <= 0.02


def test_short_inputs_pr_auc_floor():
    # Step 4b: short pasted snippets must stay clearly better than v1.0's 0.52
    assert product("short")["pr_auc"] >= 0.55
