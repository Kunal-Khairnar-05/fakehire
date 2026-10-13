"""Tests for how the model probability and rules combine into the final verdict."""
from fakehire_ml.rules import RuleHit, RuleResult
from fakehire_ml.scoring import combine

NO_RULES = RuleResult(score=0.0)
MONEY = RuleHit("asks_for_money", "Asks you to pay", 0.9, hard=True)


def test_clean_posting_is_safe():
    v = combine(0.05, NO_RULES)
    assert v.score == 3          # 100 * 0.65 * 0.05 = 3.25 -> 3
    assert v.label == "Safe"


def test_confident_model_alone_reaches_suspicious():
    v = combine(0.8, NO_RULES)
    assert v.score == 52         # 100 * 0.65 * 0.8
    assert v.label == "Suspicious"


def test_hard_rule_forces_likely_scam_even_if_model_unsure():
    v = combine(0.1, RuleResult(score=0.9, hits=[MONEY], hard=True))
    assert v.score == 70         # 6.5 + 31.5 = 38, raised to the floor of 70
    assert v.label == "Likely scam"
    assert v.flags == [MONEY]
