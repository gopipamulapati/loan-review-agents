"""Typed data models shared by every agent in the graph."""

from __future__ import annotations

from enum import Enum
from typing import ClassVar

from pydantic import BaseModel, Field


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    FAIL = "fail"


class Decision(str, Enum):
    APPROVE = "approve"
    REFER = "refer_to_underwriter"
    DECLINE = "decline"
    NEEDS_INFO = "needs_more_info"


class LoanApplication(BaseModel):
    """Structured fields pulled out of a free-text loan file."""

    applicant_name: str | None = None
    credit_score: int | None = Field(default=None, ge=300, le=850)
    annual_income: float | None = Field(default=None, ge=0)
    monthly_debt: float | None = Field(default=None, ge=0)
    loan_amount: float | None = Field(default=None, gt=0)
    property_value: float | None = Field(default=None, gt=0)
    interest_rate: float | None = Field(default=None, gt=0, lt=30)
    term_years: int | None = Field(default=None, gt=0, le=40)
    employment_years: float | None = Field(default=None, ge=0)
    documents: list[str] = Field(default_factory=list)

    REQUIRED: ClassVar[tuple[str, ...]] = (
        "credit_score",
        "annual_income",
        "monthly_debt",
        "loan_amount",
        "property_value",
    )

    def missing_fields(self) -> list[str]:
        return [f for f in self.REQUIRED if getattr(self, f) is None]


class Finding(BaseModel):
    rule: str
    severity: Severity
    message: str
    value: float | None = None


class RiskAssessment(BaseModel):
    score: int = Field(ge=0, le=100, description="0 = lowest risk, 100 = highest")
    band: str
    drivers: list[str]
    narrative: str


class ReviewReport(BaseModel):
    decision: Decision
    application: LoanApplication
    findings: list[Finding] = Field(default_factory=list)
    risk: RiskAssessment | None = None
    memo: str
    trace: list[dict] = Field(default_factory=list)
