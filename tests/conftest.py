from pathlib import Path

import pytest

SAMPLES = Path(__file__).resolve().parent.parent / "samples"


@pytest.fixture
def sample():
    def _load(name: str) -> str:
        return (SAMPLES / name).read_text(encoding="utf-8")

    return _load


class ScriptedLLM:
    """Returns canned replies so the LLM code paths can be tested offline."""

    name = "scripted"

    def __init__(self, replies: dict[str, str]):
        self.replies = replies
        self.calls: list[str] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append(system)
        for key, reply in self.replies.items():
            if key in system:
                return reply
        return ""


@pytest.fixture
def scripted_llm():
    return ScriptedLLM
