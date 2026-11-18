"""Test-only adapter for deterministic, offline UI and API verification."""

from dataclasses import dataclass, field
import json
from time import sleep

from backend.app.core.errors import ProviderError
from backend.app.services.provider import ProviderResult


PYTHON_QUESTION = "What are the Python Programming course completion requirements?"
PYTHON_QUOTE = (
    "To complete the Python Programming course, submit all four graded labs, "
    "achieve at least 70% overall, and earn a Pass on the capstone project."
)
ATTENDANCE_QUOTE = "Learners must attend at least 75% of scheduled live sessions."
CONFLICT_QUESTION = "What are the workshop attendance requirements?"
RETRY_QUESTION = "What are the Python Programming course completion requirements for learners in the handbook?"
DELAY_QUESTION = "Which course completion requirements are listed in the Python Programming handbook?"
MARKDOWN_QUESTION = "List the Python Programming course completion requirements as Markdown."
LONG_QUESTION = "What are the course completion requirements across the Python Programming handbooks?"
MARKDOWN_ANSWER = (
    "**Completion requirements**\n\n"
    "- Submit all four graded labs.\n"
    "- Achieve at least 70% overall.\n"
    "- Earn a Pass on the capstone project."
)


@dataclass
class FixtureProvider:
    name: str = "offline_fixture"
    model: str = "offline-citation-fixture-v1"
    configured: bool = True
    calls: list = field(default_factory=list)
    override: object = None
    verifications: list = field(default_factory=list)
    verification_override: str | Exception | None = None

    def generate(self, question, passages):
        self.calls.append((question, passages))
        if question == RETRY_QUESTION and sum(asked == question for asked, _ in self.calls) == 1:
            raise ProviderError("timeout", "The offline provider simulated a timeout. Try again.", True)
        if question == DELAY_QUESTION:
            sleep(2)
        if self.override:
            if isinstance(self.override, Exception):
                raise self.override
            return self.result(self.override(question, passages))
        if question == CONFLICT_QUESTION:
            return self.result({
                "status": "abstained", "answer": None, "citations": [],
                "abstention_reason": "The two retrieved workshop policies give conflicting attendance requirements.",
            })
        if "completion requirements" in question.lower():
            quote, page, title = PYTHON_QUOTE, 4, "Python Programming Course Handbook"
        elif "minimum live-session attendance" in question.lower():
            quote, page, title = ATTENDANCE_QUOTE, 2, "LMS Assessment and Attendance Policy"
        else:
            return self.result({
                "status": "abstained", "answer": None, "citations": [],
                "abstention_reason": "The fixture has no verified answer for this example.",
            })
        matches = [row for row in passages if row["page_number"] == page and quote in row["content"]]
        passage = next((row for row in matches if row["document_title"] == title), None) or (matches[0] if matches else None)
        if passage is None:
            return self.result({
                "status": "abstained", "answer": None, "citations": [],
                "abstention_reason": "The expected source is outside this search scope.",
            })
        if question == LONG_QUESTION:
            response = answer_with(passage, quote, "\n\n".join([PYTHON_QUOTE] * 18))
            response["citations"] = [answer_with(row, quote)["citations"][0] for row in matches]
            return self.result(response)
        return self.result(answer_with(passage, quote, MARKDOWN_ANSWER if question == MARKDOWN_QUESTION else None))

    def verify(self, question, passages, answer):
        self.verifications.append((question, passages, answer))
        if isinstance(self.verification_override, Exception):
            raise self.verification_override
        outcome = self.verification_override or "supported"
        payload = {"outcome": outcome, "reason": "Explicit offline verification fixture."}
        return ProviderResult(json.dumps(payload), self.model, "offline-verification-fixture", 27, 6, 1)

    def result(self, payload):
        text = payload if isinstance(payload, str) else json.dumps(payload)
        return ProviderResult(text, self.model, "offline-fixture-response", 33, 14, 1)


def answer_with(passage, quote, answer=None):
    return {
        "status": "answered", "answer": answer or quote,
        "citations": [{
            "chunk_id": passage["chunk_id"], "document_id": passage["document_id"],
            "page_number": passage["page_number"], "evidence_quote": quote,
        }], "abstention_reason": None,
    }

