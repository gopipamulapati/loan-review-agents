"""Extraction agent: free-text loan file -> ``LoanApplication``.

It asks the LLM for strict JSON and validates it with Pydantic. If the model
is offline, returns bad JSON, or fails validation, it uses a regex parser,
so a bad model response never crashes the pipeline.
"""

from __future__ import annotations

import json
import re

from pydantic import ValidationError

from ..llm import LLM
from ..models import LoanApplication

SYSTEM = (
    "You extract mortgage application data. Reply with ONLY a JSON object with "
    "these keys (use null when a value is not stated, never guess): "
    "applicant_name, credit_score, annual_income, monthly_debt, loan_amount, "
    "property_value, interest_rate (percent, e.g. 6.5), term_years, "
    "employment_years, documents (list of snake_case document types)."
)

# label pattern -> field name
_LABELS: dict[str, str] = {
    r"applicant(?: name)?": "applicant_name",
    r"credit score|fico": "credit_score",
    r"annual (?:gross )?income": "annual_income",
    r"monthly debt(?: payments)?": "monthly_debt",
    r"loan amount": "loan_amount",
    r"(?:appraised )?property value|appraised value": "property_value",
    r"interest rate|rate": "interest_rate",
    r"term": "term_years",
    r"years (?:at current employer|employed)|employment(?: years)?": "employment_years",
    r"documents(?: provided)?": "documents",
}

_NUMBER = re.compile(r"-?\d[\d,]*\.?\d*")


def _to_number(raw: str) -> float | None:
    m = _NUMBER.search(raw)
    if not m:
        return None
    return float(m.group().replace(",", ""))


def regex_extract(text: str) -> LoanApplication:
    data: dict = {}
    for line in text.splitlines():
        if ":" not in line:
            continue
        label, _, value = line.partition(":")
        label, value = label.strip().lower(), value.strip()
        for pattern, field in _LABELS.items():
            if field in data or not re.fullmatch(pattern, label):
                continue
            if field == "applicant_name":
                data[field] = value or None
            elif field == "documents":
                data[field] = [
                    d.strip().lower().replace(" ", "_")
                    for d in re.split(r"[,;]", value)
                    if d.strip()
                ]
            else:
                num = _to_number(value)
                if num is not None:
                    is_int = field in {"credit_score", "term_years"}
                    data[field] = int(num) if is_int else num
            break
    return LoanApplication(**data)


def _parse_json(raw: str) -> dict | None:
    match = re.search(r"\{.*\}", raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None


def extract(text: str, llm: LLM) -> tuple[LoanApplication, str]:
    """Return the parsed application and which method produced it."""
    raw = llm.complete(SYSTEM, text)
    payload = _parse_json(raw) if raw else None
    if payload is not None:
        try:
            return LoanApplication(**payload), f"llm:{llm.name}"
        except ValidationError:
            pass
    return regex_extract(text), "regex"
