"""LangGraph orchestration of the review agents.

    extract ──► (missing fields?) ──yes──► write
                     │ no
              ┌──────┴──────┐
              ▼             ▼
            policy        risk        (run in parallel)
              └──────┬──────┘
                     ▼
                  decide ──► write ──► END
"""

from __future__ import annotations

import operator
import time
from collections.abc import Callable
from typing import Annotated, TypedDict

from langgraph.graph import END, START, StateGraph

from .agents import extractor, policy, risk, writer
from .llm import LLM, get_llm
from .models import (
    Decision,
    Finding,
    LoanApplication,
    ReviewReport,
    RiskAssessment,
    Severity,
)


class ReviewState(TypedDict, total=False):
    text: str
    application: LoanApplication
    extraction_method: str
    missing: list[str]
    findings: list[Finding]
    risk: RiskAssessment
    decision: Decision
    memo: str
    trace: Annotated[list[dict], operator.add]  # merged across parallel branches


def _traced(name: str, fn: Callable[[ReviewState], dict]) -> Callable[[ReviewState], dict]:
    def node(state: ReviewState) -> dict:
        start = time.perf_counter()
        update = fn(state)
        ms = round((time.perf_counter() - start) * 1000, 2)
        update["trace"] = [{"node": name, "ms": ms}]
        return update

    return node


def decide(findings: list[Finding], assessment: RiskAssessment) -> Decision:
    severities = {f.severity for f in findings}
    if Severity.FAIL in severities:
        return Decision.DECLINE
    if Severity.WARNING in severities or assessment.band != "low":
        return Decision.REFER
    return Decision.APPROVE


def build_graph(llm: LLM | None = None):
    llm = llm or get_llm()

    def extract_node(state: ReviewState) -> dict:
        app, method = extractor.extract(state["text"], llm)
        return {"application": app, "extraction_method": method, "missing": app.missing_fields()}

    def policy_node(state: ReviewState) -> dict:
        return {"findings": policy.check(state["application"])}

    def risk_node(state: ReviewState) -> dict:
        return {"risk": risk.assess(state["application"], llm)}

    def decide_node(state: ReviewState) -> dict:
        return {"decision": decide(state["findings"], state["risk"])}

    def write_node(state: ReviewState) -> dict:
        decision = state.get("decision", Decision.NEEDS_INFO)
        memo = writer.write(
            state["application"],
            decision,
            state.get("findings", []),
            state.get("risk"),
            state.get("missing", []),
            llm,
        )
        return {"decision": decision, "memo": memo}

    def route_after_extract(state: ReviewState) -> list[str]:
        return ["write"] if state["missing"] else ["policy", "risk"]

    g = StateGraph(ReviewState)
    g.add_node("extract", _traced("extract", extract_node))
    g.add_node("policy", _traced("policy", policy_node))
    g.add_node("risk", _traced("risk", risk_node))
    g.add_node("decide", _traced("decide", decide_node))
    g.add_node("write", _traced("write", write_node))

    g.add_edge(START, "extract")
    g.add_conditional_edges("extract", route_after_extract, ["write", "policy", "risk"])
    g.add_edge(["policy", "risk"], "decide")  # waits for both branches
    g.add_edge("decide", "write")
    g.add_edge("write", END)
    return g.compile()


def review(text: str, llm: LLM | None = None, graph=None) -> ReviewReport:
    """Run one loan file through the graph and return a typed report.

    Pass a pre-compiled ``graph`` to skip rebuilding it on every call.
    """
    graph = graph or build_graph(llm)
    final = graph.invoke({"text": text, "trace": []})
    return ReviewReport(
        decision=final["decision"],
        application=final["application"],
        findings=final.get("findings", []),
        risk=final.get("risk"),
        memo=final["memo"],
        trace=final["trace"],
    )
