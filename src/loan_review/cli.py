"""Command-line entry point: ``loan-review samples/*.txt``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .graph import build_graph, review
from .llm import get_llm


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Review loan files with a multi-agent graph.")
    p.add_argument("files", nargs="+", type=Path, help="Loan file(s) as plain text")
    p.add_argument("--json", action="store_true", help="Print the full JSON report")
    p.add_argument("--provider", help="offline | openai | bedrock (default: $LLM_PROVIDER)")
    args = p.parse_args(argv)

    graph = build_graph(get_llm(args.provider))
    for path in args.files:
        report = review(path.read_text(encoding="utf-8"), graph=graph)
        if args.json:
            print(json.dumps(report.model_dump(mode="json"), indent=2))
        else:
            print(f"\n=== {path.name} -> {report.decision.value} ===\n")
            print(report.memo)
            steps = " -> ".join(f"{t['node']} ({t['ms']} ms)" for t in report.trace)
            print(f"\ntrace: {steps}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
