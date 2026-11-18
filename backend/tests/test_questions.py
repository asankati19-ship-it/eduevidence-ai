import json
import sqlite3
from uuid import uuid4

from fastapi.testclient import TestClient
import pytest

from backend.app.core.config import ROOT
from backend.app.core.errors import ProviderError
from backend.app.db.database import utc_now
from backend.app.main import create_app
from backend.app.services.provider import PROMPT_VERSION
from backend.tests.conftest import pdf_bytes, upload
from backend.tests.fixtures import CONFLICT_QUESTION, PYTHON_QUESTION, PYTHON_QUOTE, answer_with


CASES = json.loads((ROOT / "data/expected_answers.json").read_text(encoding="utf-8"))


@pytest.mark.parametrize("case", CASES[:6], ids=["completion", "lab-submission", "capstone", "attendance", "late-work", "review"])
def test_independent_retrieval_benchmark(seeded, case):
    result = seeded.post("/questions", json={"question": case["question"], "course_id": case["course_id"]}).json()
    top = result["sources"][0]
    assert top["document_title"] == case["document"]
    assert top["page_number"] == case["page"]
    assert top["rank"] == 1
    assert all(fact in top["content"] for fact in case["required_facts"])
    assert 0 < top["score"] <= 1


def test_scopes_and_multiple_documents(seeded):
    result = seeded.post("/questions", json={"question": "LMS assessment submission guidelines for learners?"}).json()
    assert len({source["document_id"] for source in result["sources"]}) >= 2
    scoped = seeded.post("/questions", json={"question": "LMS assessment submission guidelines for learners?", "course_id": 2}).json()
    assert scoped["sources"] and {source["document_id"] for source in scoped["sources"]} == {2}
    mismatch = seeded.post("/questions", json={"question": PYTHON_QUESTION, "course_id": 2, "document_id": 1})
    assert mismatch.status_code == 422 and mismatch.json()["error"]["code"] == "scope_mismatch"


@pytest.mark.parametrize("question", [" ", "??!", "ab"])
def test_invalid_question_does_not_create_trace(seeded, question):
    assert seeded.post("/questions", json={"question": question}).status_code == 422
    assert seeded.get("/questions/history").json()["total"] == 0


@pytest.mark.parametrize("case", CASES[-2:], ids=["unsupported", "ambiguous"])
def test_abstains_before_provider(seeded, provider, case):
    result = seeded.post("/questions", json={"question": case["question"], "course_id": case["course_id"]}).json()
    assert result["status"] == "abstained" and result["answer"]["api_outcome"] == "skipped"
    assert result["citations"] == [] and provider.calls == []


def test_no_corpus_abstains(client, provider):
    trace = client.post("/questions", json={"question": PYTHON_QUESTION}).json()
    assert trace["status"] == "abstained" and trace["sources"] == []
    assert "no indexed passages" in trace["answer"]["reason"].lower()
    assert provider.calls == []


def test_conflicting_passages_are_supplied_for_model_abstention(client):
    for percent, title in [(75, "Workshop policy A"), (100, "Workshop policy B")]:
        response = upload(client, pdf_bytes([f"The workshop attendance requirements mandate attendance of {percent}% of live workshops."], title=title))
        assert response.status_code == 202
    trace = client.post("/questions", json={"question": CONFLICT_QUESTION}).json()
    assert trace["status"] == "abstained" and "conflicting" in trace["answer"]["reason"]
    assert len({source["document_id"] for source in trace["sources"]}) == 2


@pytest.mark.parametrize(("field", "value", "code"), [
    ("chunk_id", 999999, "invalid_citation"),
    ("document_id", 2, "invalid_citation"),
    ("page_number", 1, "invalid_citation"),
    ("evidence_quote", "This quotation was quietly fabricated.", "invalid_evidence_quote"),
])
def test_invalid_citation_rejected(seeded, provider, field, value, code):
    def altered(_, passages):
        response = answer_with(passages[0], PYTHON_QUOTE)
        response["citations"][0][field] = value
        return response
    provider.override = altered
    trace = seeded.post("/questions", json={"question": PYTHON_QUESTION, "document_id": 1}).json()
    assert trace["status"] == "validation_error"
    assert trace["answer"]["error_code"] == code
    assert trace["answer"]["body"] is None and trace["citations"] == []
    assert trace["answer"]["provider_response_id"] == "offline-fixture-response"


def test_valid_database_chunk_outside_retrieved_set_is_rejected(seeded, provider):
    unrelated = seeded.app.state.db.one("SELECT id,document_id,page_number,content FROM document_chunks WHERE document_id=2")
    provider.override = lambda _, __: answer_with(
        {**unrelated, "chunk_id": unrelated["id"]}, unrelated["content"],
    )
    trace = seeded.post("/questions", json={"question": PYTHON_QUESTION, "document_id": 1}).json()
    assert trace["answer"]["error_code"] == "invalid_citation"


@pytest.mark.parametrize(("payload", "code"), [
    ("not JSON", "invalid_model_json"),
    ({"status": "answered", "answer": "Course requirements.", "citations": [], "abstention_reason": None}, "invalid_answer"),
    ({"status": "abstained", "answer": "Should not be here.", "citations": [], "abstention_reason": None}, "invalid_abstention"),
])
def test_invalid_model_outputs_are_persisted(seeded, provider, payload, code):
    provider.override = lambda *_: payload
    trace = seeded.post("/questions", json={"question": PYTHON_QUESTION}).json()
    assert trace["status"] == "validation_error"
    assert trace["answer"]["error_code"] == code
    assert trace["answer"]["api_outcome"] == "invalid_response"


@pytest.mark.parametrize("claim", ["Earn at least 97% overall.", "The course requires a summer visa.", "Do not submit graded labs."])
def test_unsupported_claim_is_rejected_even_with_real_citation(seeded, provider, claim):
    provider.verification_override = "unsupported"
    provider.override = lambda _, passages: answer_with(passages[0], PYTHON_QUOTE, claim)
    trace = seeded.post("/questions", json={"question": PYTHON_QUESTION, "document_id": 1}).json()
    assert trace["answer"]["error_code"] == "unsupported_answer"
    assert trace["answer"]["body"] is None


@pytest.mark.parametrize("code", ["timeout", "rate_limit", "network_error", "provider_http_error"])
def test_provider_failures_never_substitute_an_answer(seeded, provider, code):
    provider.override = ProviderError(code, "A safe provider error", True)
    trace = seeded.post("/questions", json={"question": PYTHON_QUESTION}).json()
    assert trace["status"] == "provider_error"
    assert trace["answer"]["error_code"] == code
    assert trace["answer"]["retryable"] and trace["answer"]["body"] is None
    assert not trace["citations"] and trace["sources"]
    assert seeded.get("/analytics/overview").json()["questions"]["provider_errors"] == 1


def test_missing_key_preserves_retrieval_and_error(seeded, settings):
    with TestClient(create_app(settings, testing=True)) as client:
        response = client.post("/questions", json={"question": PYTHON_QUESTION, "document_id": 1}).json()
        assert response["answer"]["error_code"] == "missing_credentials"
        assert response["answer"]["api_outcome"] == "skipped"
        assert response["sources"] and not response["citations"]
        assert client.get("/system/status").json()["provider"]["configured"] is False


def test_sqlite_full_trace_feedback_history_and_audit(seeded):
    conversation = str(uuid4())
    response = seeded.post("/questions", json={"question": PYTHON_QUESTION, "course_id": 1, "document_id": 1, "conversation_id": conversation})
    assert response.status_code == 201
    item = response.json()
    assert item["status"] == "answered"
    assert item["answer"]["body"] == PYTHON_QUOTE
    citation = item["citations"][0]
    assert citation["evidence_quote"] == PYTHON_QUOTE and citation["page_number"] == 4
    assert citation["chunk_id"] in {source["chunk_id"] for source in item["sources"]}
    assert item["request_id"] == response.headers["x-request-id"]
    assert item["answer"]["prompt_version"] == PROMPT_VERSION and item["answer"]["input_tokens"] == 33
    answer_id = item["answer"]["id"]
    assert seeded.post(f"/answers/{answer_id}/feedback", json={"rating": "not_helpful"}).status_code == 200
    assert seeded.post(f"/answers/{answer_id}/feedback", json={"rating": "helpful", "comment": "Good evidence"}).status_code == 200
    assert seeded.get(f"/questions/{item['id']}").json()["answer"]["rating"] == "helpful"
    history = seeded.get("/questions/history", params={"conversation_id": conversation, "status": "answered"}).json()
    assert history["total"] == 1 and history["items"][0]["id"] == item["id"]
    statistics = seeded.get("/analytics/overview").json()
    assert statistics["documents"]["chunks"] == 10
    assert statistics["feedback"] == {"total": 1, "helpful": 1, "not_helpful": 0}
    assert statistics["questions"]["answered"] == 1
    events = seeded.get("/audit/events", params={"request_id": item["request_id"]}).json()["items"]
    assert [event["event_type"] for event in reversed(events)] == [
        "question.submit", "question.retrieve", "question.verify", "question.complete",
    ]
    assert seeded.get("/audit/events", params={"event_type": "answer.feedback"}).json()["total"] == 2


def test_foreign_keys_and_failed_transactions_roll_back(seeded):
    db = seeded.app.state.db
    with pytest.raises(sqlite3.IntegrityError), db.connection(write=True) as con:
        con.execute("INSERT INTO courses(code,title,created_at) VALUES ('TEMP','rollback',?)", (utc_now(),))
        con.execute("INSERT INTO retrieved_sources(question_id,chunk_id,rank,score) VALUES (99,99,1,0.7)")
    assert db.one("SELECT id FROM courses WHERE code='TEMP'") is None
    assert db.all("PRAGMA foreign_key_check") == []


def test_database_rejects_wrong_page_even_for_real_chunk(seeded):
    trace = seeded.post("/questions", json={"question": PYTHON_QUESTION, "document_id": 1}).json()
    citation = trace["citations"][0]
    with pytest.raises(sqlite3.IntegrityError), seeded.app.state.db.connection(write=True) as con:
        con.execute("UPDATE answer_citations SET page_number=999 WHERE answer_id=? AND chunk_id=?",
                    (trace["answer"]["id"], citation["chunk_id"]))


def test_foreign_origin_write_rejected(seeded):
    rejected = seeded.post("/questions", json={"question": PYTHON_QUESTION}, headers={"Origin": "https://external.example"})
    assert rejected.status_code == 403
    assert rejected.json()["error"]["code"] == "origin_denied"

