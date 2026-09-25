"""FastAPI service exposing the review graph."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel, Field

from . import __version__
from .graph import build_graph, review
from .llm import get_llm
from .models import ReviewReport

app = FastAPI(
    title="Loan Review Agents",
    version=__version__,
    description="Multi-agent mortgage pre-review built with LangGraph.",
)

_llm = get_llm()
_graph = build_graph(_llm)  # compile once at startup


class ReviewRequest(BaseModel):
    text: str = Field(min_length=20, description="Raw loan file text")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "llm": _llm.name, "version": __version__}


@app.post("/review", response_model=ReviewReport)
def review_endpoint(req: ReviewRequest) -> ReviewReport:
    return review(req.text, graph=_graph)
