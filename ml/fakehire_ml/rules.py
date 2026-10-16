"""Rule engine: hand-written red flags that a model trained on US data would miss.

Design:
- Every red flag is its own class (Open/Closed principle: add a rule by adding a
  class, never by editing the engine).
- Every rule has a weight between 0 and 1 = "how suspicious is this on its own".
- A "hard" rule (asking for money) is so strong that the final score gets a floor.
"""
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .posting import Posting


@dataclass(frozen=True)
class RuleHit:
    rule: str
    message: str  # shown to the user as a red flag
    weight: float
    hard: bool
    scored: bool = True


class Rule(ABC):
    name: str
    message: str
    weight: float
    hard: bool = False
    scored: bool = True   # False = show the flag to the user, but don't add it to the score

    @abstractmethod
    def matches(self, posting: Posting) -> bool: ...

    def check(self, posting: Posting) -> RuleHit | None:
        if self.matches(posting):
            return RuleHit(self.name, self.message, self.weight, self.hard, self.scored)
        return None


class RegexRule(Rule):
    """A rule that fires when its regular expression appears anywhere in the text."""
    pattern: re.Pattern

    def matches(self, posting: Posting) -> bool:
        return bool(self.pattern.search(posting.text))


# ---------- the red flags ----------

class AsksForMoney(RegexRule):
    name = "asks_for_money"
    message = "Asks you to pay a fee or deposit. Real employers never charge candidates."
    weight = 0.9
    hard = True
    pattern = re.compile(
        r"(registration|training|joining|processing|security|refundable|application|kit)\s+"
        r"(fee|fees|charge|charges|deposit|amount)"
        r"|pay\s+(a\s+|the\s+)?(fee|deposit|rs\.?|inr|₹)"
    )
    # "There is NO registration fee" is a good sign, not a red flag.
    negation = re.compile(r"\b(no|not|never|without|free of|zero)\b[\w\s]{0,15}$")

    def matches(self, posting: Posting) -> bool:
        text = posting.text
        for m in self.pattern.finditer(text):
            before = text[max(0, m.start() - 25):m.start()]
            if not self.negation.search(before):
                return True
        return False


class OffPlatformContact(RegexRule):
    name = "off_platform_contact"
    message = "Moves the conversation to WhatsApp, Telegram or a personal phone number."
    weight = 0.6
    # Just mentioning WhatsApp is normal (marketing jobs). The red flag is being told
    # to CONTACT someone there, or a WhatsApp/Telegram number.
    pattern = re.compile(
        r"(contact|message|ping|text|reach|send|call|chat|connect)\w*\s+(\w+\s+){0,3}"
        r"(on|via|at|through)\s+(whats\s?app|telegram)"
        r"|(whats\s?app|telegram)\s*(no\.?|number|:)?\s*\+?\d"
    )


class FreeEmailRecruiter(RegexRule):
    name = "free_email_recruiter"
    message = "Recruiter uses a free email address (Gmail, Yahoo...) instead of a company domain."
    weight = 0.5
    pattern = re.compile(r"[\w.+-]+@(gmail|yahoo|hotmail|outlook|rediffmail|ymail)\.(com|in|co\.in)")


class TooGoodToBeTrue(RegexRule):
    name = "too_good_to_be_true"
    message = "Promises easy or guaranteed money, or skips the interview."
    weight = 0.4
    pattern = re.compile(
        r"earn\s+(up\s+to\s+)?(rs\.?|₹|\$|inr)\s?\d"
        r"|no\s+interview"
        r"|guaranteed\s+(income|job|placement|salary|earning)"
        r"|easy\s+money"
        # money paid per day/hour ("Rs 800 per day", "₹500/day"), or "daily payout".
        # NOT just "per week": "5 days per week" is a normal schedule (bug found in manual testing).
        r"|(rs\.?|₹|inr)\s?[\d,]+\s*(/-\s*)?(per|a|/)\s*(day|hour)"
        r"|daily\s+(payout|payment|income|earning)"
    )


class UrgencyPressure(RegexRule):
    name = "urgency_pressure"
    message = "Pressures you to act fast (limited seats, immediate joining)."
    weight = 0.25
    pattern = re.compile(
        r"immediate(ly)?\s+joining|limited\s+(seats|slots|vacancies)|hurry"
        r"|urgent(ly)?\s+(hiring|requirement)"
    )


class MissingCompanyProfile(Rule):
    name = "missing_company_profile"
    message = "No information about the company."
    weight = 0.35
    # The ML model already uses "has_company_profile" as a feature. Scoring it here too
    # counted the same evidence twice and lowered test PR-AUC from 0.86 to 0.82.
    scored = False

    def matches(self, posting: Posting) -> bool:
        return not posting.company_profile


DEFAULT_RULES: list[Rule] = [
    AsksForMoney(),
    OffPlatformContact(),
    FreeEmailRecruiter(),
    TooGoodToBeTrue(),
    UrgencyPressure(),
    MissingCompanyProfile(),
]


# ---------- the engine ----------

@dataclass
class RuleResult:
    score: float                      # 0..1
    hits: list[RuleHit] = field(default_factory=list)
    hard: bool = False                # True if any hard rule fired


class RuleEngine:
    def __init__(self, rules: list[Rule] | None = None):
        self.rules = rules if rules is not None else DEFAULT_RULES

    def evaluate(self, posting: Posting) -> RuleResult:
        hits = [hit for rule in self.rules if (hit := rule.check(posting))]

        # Combine weights with "noisy-OR": each red flag independently has a chance
        # to be the giveaway. score = 1 - (chance that NONE of them is).
        # Two 0.5 flags -> 1 - 0.5*0.5 = 0.75. More flags push towards 1, never past it.
        all_innocent = 1.0
        for hit in hits:
            if hit.scored:
                all_innocent *= 1 - hit.weight

        return RuleResult(score=round(1 - all_innocent, 3), hits=hits, hard=any(h.hard for h in hits))
