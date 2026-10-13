"""Combines the model probability and the rule score into the final 0-100 verdict."""
from dataclasses import dataclass, field

from .rules import RuleHit, RuleResult

MODEL_WEIGHT = 0.65
RULE_WEIGHT = 0.35
HARD_RULE_FLOOR = 70        # asking for money -> at least "Likely scam"
SUSPICIOUS_FROM = 40
SCAM_FROM = 70


@dataclass
class Verdict:
    score: int                          # 0..100
    label: str                          # Safe / Suspicious / Likely scam
    p_model: float
    rule_score: float
    flags: list[RuleHit] = field(default_factory=list)


def label_for(score: float) -> str:
    if score >= SCAM_FROM:
        return "Likely scam"
    if score >= SUSPICIOUS_FROM:
        return "Suspicious"
    return "Safe"


def combine(p_model: float, rules: RuleResult) -> Verdict:
    score = 100 * (MODEL_WEIGHT * p_model + RULE_WEIGHT * rules.score)
    if rules.hard:
        score = max(score, HARD_RULE_FLOOR)
    score = round(score)
    return Verdict(score=score, label=label_for(score), p_model=round(p_model, 4),
                   rule_score=rules.score, flags=rules.hits)
