"""Writer agent: produces the underwriter-facing review memo."""

from __future__ import annotations

from ..llm import LLM
from ..models import Decision, Finding, LoanApplication, RiskAssessment, Severity

SYSTEM = (
    "You write concise loan review memos for a human underwriter. Use only "
    "the facts given. Keep the decision exactly as stated. Use markdown."
)

_LABEL = {
    Decision.APPROVE: "APPROVE",
    Decision.REFER: "REFER TO UNDERWRITER",
    Decision.DECLINE: "DECLINE",
    Decision.NEEDS_INFO: "NEEDS MORE INFORMATION",
}


def template_memo(
    app: LoanApplication,
    decision: Decision,
    findings: list[Finding],
    risk: RiskAssessment | None,
    missing: list[str],
) -> str:
    lines = [f"## Loan review: {app.applicant_name or 'Unknown applicant'}", ""]
    lines.append(f"**Recommendation:** {_LABEL[decision]}")
    if risk:
        lines.append(f"**Risk:** {risk.score}/100 ({risk.band})")
    lines.append("")
    if missing:
        lines.append("### Missing required fields")
        lines += [f"- {m}" for m in missing]
        lines.append("")
    issues = [f for f in findings if f.severity != Severity.INFO]
    if issues:
        lines.append("### Issues")
        lines += [f"- **{f.severity.value.upper()}** ({f.rule}): {f.message}" for f in issues]
        lines.append("")
    passed = [f for f in findings if f.severity == Severity.INFO]
    if passed:
        lines.append("### Checks passed")
        lines += [f"- {f.message}" for f in passed]
        lines.append("")
    if risk:
        lines.append("### Risk summary")
        lines.append(risk.narrative)
        lines.append("")
    lines.append("_Automated pre-review. A licensed underwriter makes the final decision._")
    return "\n".join(lines)


def write(
    app: LoanApplication,
    decision: Decision,
    findings: list[Finding],
    risk: RiskAssessment | None,
    missing: list[str],
    llm: LLM,
) -> str:
    draft = template_memo(app, decision, findings, risk, missing)
    polished = llm.complete(SYSTEM, draft).strip()
    # Guardrail: reject a rewrite that drops or changes the recommendation.
    if polished and _LABEL[decision] in polished:
        return polished
    return draft
