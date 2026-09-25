import pytest

from loan_review.agents.extractor import regex_extract
from loan_review.agents.risk import score
from loan_review.graph import review
from loan_review.llm import OfflineLLM
from loan_review.models import Decision


@pytest.mark.parametrize("name,decision", [
    ("01_strong_applicant.txt", Decision.APPROVE),
    ("02_borderline_applicant.txt", Decision.REFER),
    ("03_high_risk_applicant.txt", Decision.DECLINE),
    ("04_incomplete_file.txt", Decision.NEEDS_INFO),
])
def test_end_to_end_decisions(sample, name, decision):
    assert review(sample(name), OfflineLLM()).decision == decision


def test_incomplete_file_skips_policy_and_risk(sample):
    report = review(sample("04_incomplete_file.txt"), OfflineLLM())
    assert [t["node"] for t in report.trace] == ["extract", "write"]
    assert report.risk is None


def test_parallel_branches_both_recorded(sample):
    nodes = [t["node"] for t in review(sample("01_strong_applicant.txt"), OfflineLLM()).trace]
    assert {"policy", "risk"} <= set(nodes)
    assert nodes[0] == "extract" and nodes[-1] == "write"


def test_risk_score_is_monotonic_in_credit(sample):
    app = regex_extract(sample("02_borderline_applicant.txt"))
    low, _ = score(app.model_copy(update={"credit_score": 800}))
    high, _ = score(app.model_copy(update={"credit_score": 600}))
    assert low < high


def test_writer_guardrail_rejects_changed_decision(sample, scripted_llm):
    llm = scripted_llm({"memo": "Looks great, APPROVE immediately."})
    report = review(sample("03_high_risk_applicant.txt"), llm)
    assert report.decision == Decision.DECLINE
    assert "**Recommendation:** DECLINE" in report.memo


def test_writer_accepts_faithful_rewrite(sample, scripted_llm):
    llm = scripted_llm({"memo": "Summary for underwriter. Recommendation: DECLINE."})
    report = review(sample("03_high_risk_applicant.txt"), llm)
    assert report.memo == "Summary for underwriter. Recommendation: DECLINE."
