import pytest

from loan_review.agents.policy import check, monthly_payment, ratios
from loan_review.models import LoanApplication, Severity


def make(**kw) -> LoanApplication:
    base = dict(credit_score=760, annual_income=120_000, monthly_debt=300,
                loan_amount=300_000, property_value=400_000, interest_rate=6.0,
                term_years=30, employment_years=5,
                documents=["pay_stub", "w2", "bank_statement", "appraisal"])
    base.update(kw)
    return LoanApplication(**base)


def test_monthly_payment_matches_amortization_formula():
    assert monthly_payment(300_000, 6.0, 30) == pytest.approx(1798.65, abs=0.01)
    assert monthly_payment(120_000, 0, 10) == pytest.approx(1000)


def test_ratios():
    r = ratios(make())
    assert r["ltv"] == 0.75
    assert 0.2 < r["dti"] < 0.3


def severities(app, rule):
    return [f.severity for f in check(app) if f.rule == rule]


@pytest.mark.parametrize("score,expected", [(600, Severity.FAIL), (700, Severity.WARNING),
                                            (760, Severity.INFO)])
def test_credit_tiers(score, expected):
    assert severities(make(credit_score=score), "credit_score") == [expected]


def test_high_dti_fails():
    assert severities(make(monthly_debt=4000), "dti") == [Severity.FAIL]


def test_ltv_above_pmi_threshold_warns():
    assert severities(make(loan_amount=360_000), "ltv") == [Severity.WARNING]


def test_missing_documents_warn():
    findings = [f for f in check(make(documents=["w2"])) if f.rule == "documents"]
    assert "bank_statement" in findings[0].message


def test_missing_rate_is_noted():
    assert severities(make(interest_rate=None), "interest_rate") == [Severity.INFO]
