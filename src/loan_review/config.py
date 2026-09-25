"""Underwriting thresholds.

These are simplified, illustrative values for a portfolio project. They are
NOT real lending guidelines from any agency or lender.
"""

from pydantic import BaseModel


class Policy(BaseModel):
    min_credit_score: int = 620
    preferred_credit_score: int = 740
    max_dti: float = 0.43  # back-end debt-to-income
    warn_dti: float = 0.36
    max_ltv: float = 0.97
    pmi_ltv: float = 0.80  # above this, mortgage insurance is expected
    min_employment_years: float = 2.0
    required_documents: tuple[str, ...] = (
        "pay_stub",
        "w2",
        "bank_statement",
        "appraisal",
    )


DEFAULT_POLICY = Policy()
