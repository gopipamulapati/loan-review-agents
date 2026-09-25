"""Policy agent: deterministic checks against underwriting thresholds.

Kept rule-based on purpose. Pass/fail rules should be auditable and
reproducible, so the LLM never decides them.
"""

from __future__ import annotations

from ..config import DEFAULT_POLICY, Policy
from ..models import Finding, LoanApplication, Severity

DEFAULT_RATE = 7.0  # used only when the file has no rate
ESCROW_RATE = 0.015  # taxes + insurance per year, as a share of property value


def monthly_payment(principal: float, annual_rate_pct: float, years: int) -> float:
    """Standard amortized principal + interest payment."""
    r = annual_rate_pct / 100 / 12
    n = years * 12
    if r == 0:
        return principal / n
    return principal * r * (1 + r) ** n / ((1 + r) ** n - 1)


def housing_payment(app: LoanApplication) -> float:
    rate = app.interest_rate or DEFAULT_RATE
    term = app.term_years or 30
    escrow = (app.property_value or 0) * ESCROW_RATE / 12
    return monthly_payment(app.loan_amount or 0, rate, term) + escrow


def ratios(app: LoanApplication) -> dict[str, float]:
    monthly_income = (app.annual_income or 0) / 12
    housing = housing_payment(app)
    dti = (housing + (app.monthly_debt or 0)) / monthly_income if monthly_income else 1.0
    ltv = (app.loan_amount or 0) / app.property_value if app.property_value else 1.0
    return {"dti": round(dti, 4), "ltv": round(ltv, 4), "housing_payment": round(housing, 2)}


def check(app: LoanApplication, policy: Policy = DEFAULT_POLICY) -> list[Finding]:
    findings: list[Finding] = []

    def add(rule: str, severity: Severity, message: str, value: float | None = None) -> None:
        findings.append(Finding(rule=rule, severity=severity, message=message, value=value))

    r = ratios(app)

    # Credit score
    cs = app.credit_score or 0
    if cs < policy.min_credit_score:
        add("credit_score", Severity.FAIL,
            f"Credit score {cs} is below the minimum {policy.min_credit_score}.", cs)
    elif cs < policy.preferred_credit_score:
        add("credit_score", Severity.WARNING,
            f"Credit score {cs} is below the preferred {policy.preferred_credit_score}.", cs)
    else:
        add("credit_score", Severity.INFO, f"Credit score {cs} meets the preferred tier.", cs)

    # Debt-to-income
    dti = r["dti"]
    if dti > policy.max_dti:
        add("dti", Severity.FAIL, f"DTI {dti:.1%} exceeds the maximum {policy.max_dti:.0%}.", dti)
    elif dti > policy.warn_dti:
        add("dti", Severity.WARNING,
            f"DTI {dti:.1%} is above the comfort level {policy.warn_dti:.0%}.", dti)
    else:
        add("dti", Severity.INFO, f"DTI {dti:.1%} is within limits.", dti)

    # Loan-to-value
    ltv = r["ltv"]
    if ltv > policy.max_ltv:
        add("ltv", Severity.FAIL, f"LTV {ltv:.1%} exceeds the maximum {policy.max_ltv:.0%}.", ltv)
    elif ltv > policy.pmi_ltv:
        add("ltv", Severity.WARNING,
            f"LTV {ltv:.1%} is above {policy.pmi_ltv:.0%}; mortgage insurance expected.", ltv)
    else:
        add("ltv", Severity.INFO, f"LTV {ltv:.1%} is within limits.", ltv)

    # Employment history
    years = app.employment_years
    if years is not None and years < policy.min_employment_years:
        add("employment", Severity.WARNING,
            f"Only {years:g} years at current employer "
            f"(prefer {policy.min_employment_years:g}+).", years)

    # Documentation
    missing = [d for d in policy.required_documents if d not in app.documents]
    if missing:
        add("documents", Severity.WARNING, f"Missing documents: {', '.join(missing)}.")

    if app.interest_rate is None:
        add("interest_rate", Severity.INFO,
            f"No rate given; assumed {DEFAULT_RATE}% for the payment estimate.", DEFAULT_RATE)
    return findings
