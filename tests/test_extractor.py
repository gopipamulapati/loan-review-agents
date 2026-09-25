import json

from loan_review.agents.extractor import extract, regex_extract
from loan_review.llm import OfflineLLM


def test_regex_parses_currency_and_percent(sample):
    app = regex_extract(sample("01_strong_applicant.txt"))
    assert app.applicant_name == "Priya Raman"
    assert app.credit_score == 782
    assert app.annual_income == 150_000
    assert app.interest_rate == 6.5
    assert app.term_years == 30
    assert set(app.documents) == {"pay_stub", "w2", "bank_statement", "appraisal"}
    assert app.missing_fields() == []


def test_missing_fields_are_reported(sample):
    app = regex_extract(sample("04_incomplete_file.txt"))
    assert set(app.missing_fields()) == {"annual_income", "monthly_debt", "property_value"}


def test_offline_llm_uses_regex(sample):
    _, method = extract(sample("01_strong_applicant.txt"), OfflineLLM())
    assert method == "regex"


def test_valid_llm_json_is_used(sample, scripted_llm):
    payload = {"applicant_name": "From LLM", "credit_score": 700, "annual_income": 90000,
               "monthly_debt": 300, "loan_amount": 200000, "property_value": 300000}
    llm = scripted_llm({"extract": "Sure! " + json.dumps(payload)})
    app, method = extract(sample("01_strong_applicant.txt"), llm)
    assert method == "llm:scripted"
    assert app.applicant_name == "From LLM"


def test_invalid_llm_json_falls_back_to_regex(sample, scripted_llm):
    llm = scripted_llm({"extract": '{"credit_score": 9999}'})  # fails validation
    app, method = extract(sample("01_strong_applicant.txt"), llm)
    assert method == "regex"
    assert app.credit_score == 782
