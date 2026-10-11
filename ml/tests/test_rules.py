"""Unit tests for the rule engine. Run from the project root:  python -m pytest ml/tests -v"""
from fakehire_ml.posting import Posting
from fakehire_ml.rules import AsksForMoney, FreeEmailRecruiter, OffPlatformContact, RuleEngine

LEGIT = Posting(
    title="Backend Developer Intern",
    company_profile="Acme Corp builds payment software for small businesses.",
    description="Work on our Python APIs. Interview process: two technical rounds.",
)

SCAM = Posting(
    title="Data Entry Work From Home",
    description=(
        "No interview! Pay a registration fee of Rs 1999 to confirm your seat. "
        "Contact HR on WhatsApp 9876543210 or mail hr.amazon.jobs@gmail.com"
    ),
)


def test_money_rule_fires_on_fee_request():
    assert AsksForMoney().matches(SCAM)


def test_money_rule_ignores_normal_posting():
    assert not AsksForMoney().matches(LEGIT)


def test_no_fee_is_not_a_red_flag():
    assert not AsksForMoney().matches(Posting(description="There is no registration fee for this program."))


def test_whatsapp_number_detected():
    assert OffPlatformContact().matches(SCAM)


def test_whatsapp_as_a_skill_is_not_flagged():
    assert not OffPlatformContact().matches(Posting(description="Run our WhatsApp and Instagram campaigns."))


def test_gmail_recruiter_detected():
    assert FreeEmailRecruiter().matches(SCAM)


def test_legit_posting_scores_zero():
    result = RuleEngine().evaluate(LEGIT)
    assert result.score == 0
    assert result.hits == []


def test_scam_scores_high_and_is_hard():
    result = RuleEngine().evaluate(SCAM)
    assert result.score > 0.9
    assert result.hard is True
    assert "asks_for_money" in {h.rule for h in result.hits}


def test_noisy_or_two_half_flags_make_075():
    # Only the WhatsApp and Gmail rules (0.5 each) -> 1 - 0.5 * 0.5 = 0.75
    engine = RuleEngine([OffPlatformContact(), FreeEmailRecruiter()])
    result = engine.evaluate(Posting(description="message us on whatsapp or mail x@gmail.com"))
    assert result.score == 0.75
