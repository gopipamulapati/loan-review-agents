"""Risk agent: turns the application into a 0-100 risk score with drivers.

The score is a transparent weighted formula. The LLM (when enabled) only
writes the plain-English narrative around numbers it is given, so it cannot
change the score.
"""

from __future__ import annotations

from ..llm import LLM
from ..models import LoanApplication, RiskAssessment
from .policy import ratios

SYSTEM = (
    "You are a mortgage credit analyst. In 2-3 sentences, explain the risk "
    "score using ONLY the facts provided. Do not invent numbers."
)


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def score(app: LoanApplication) -> tuple[int, list[str]]:
    r = ratios(app)
    cs = app.credit_score or 300

    # Each component is normalised to 0 (safe) .. 1 (risky).
    components = {
        "credit score": (_clamp((780 - cs) / (780 - 580)), 0.35),
        "debt-to-income": (_clamp((r["dti"] - 0.25) / (0.50 - 0.25)), 0.30),
        "loan-to-value": (_clamp((r["ltv"] - 0.60) / (0.97 - 0.60)), 0.25),
        "employment tenure": (_clamp((3 - (app.employment_years or 0)) / 3), 0.10),
    }
    total = sum(v * w for v, w in components.values())
    drivers = [
        name
        for name, (v, w) in sorted(components.items(), key=lambda kv: -kv[1][0] * kv[1][1])
        if v * w >= 0.05
    ]
    return round(total * 100), drivers


def band(value: int) -> str:
    if value < 30:
        return "low"
    if value < 60:
        return "moderate"
    return "high"


def assess(app: LoanApplication, llm: LLM) -> RiskAssessment:
    value, drivers = score(app)
    r = ratios(app)
    facts = (
        f"Risk score {value}/100 ({band(value)}). Credit score {app.credit_score}, "
        f"DTI {r['dti']:.1%}, LTV {r['ltv']:.1%}, "
        f"employment {app.employment_years} years. Main drivers: {', '.join(drivers) or 'none'}."
    )
    narrative = llm.complete(SYSTEM, facts).strip() or facts
    return RiskAssessment(score=value, band=band(value), drivers=drivers, narrative=narrative)
