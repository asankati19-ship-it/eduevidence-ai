"""Capture a preregistered PDF benchmark through the real FastAPI application."""

import argparse
from contextlib import closing
from hashlib import sha256
import json
from pathlib import Path
import re
import sqlite3
from statistics import mean
from tempfile import TemporaryDirectory
from uuid import uuid4

from fastapi.testclient import TestClient
from pydantic import SecretStr

from backend.app.core.config import ROOT, Settings
from backend.app.main import create_app
from backend.app.services.provider import OpenAIProvider
from scripts.seed_data import SAMPLE_DOCS, seed


GROUND_TRUTH = ROOT / "data/evaluation_ground_truth.json"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_ground_truth():
    truth = read_json(GROUND_TRUTH)
    for entry in truth["documents"].values():
        path = SAMPLE_DOCS / entry["filename"]
        if sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError(f"Source checksum changed: {path.name}")
    ids = [case["id"] for case in truth["questions"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Ground-truth test IDs must be unique.")
    return truth


class ObservedProvider:
    """Observe committed state at the SDK boundary without changing the response."""

    def __init__(self, provider, database_path):
        self.provider = provider
        self.database_path = database_path
        self.name = provider.name
        self.model = provider.model
        self.configured = provider.configured
        self.observation = None

    def generate(self, question, passages):
        with closing(sqlite3.connect(self.database_path)) as con:
            question_id, status = con.execute(
                "SELECT id,status FROM questions WHERE question_text=? ORDER BY id DESC LIMIT 1",
                (question,),
            ).fetchone()
            stored = [row[0] for row in con.execute(
                "SELECT chunk_id FROM retrieved_sources WHERE question_id=? ORDER BY rank", (question_id,),
            )]
            prior_answer = con.execute("SELECT id FROM answers WHERE question_id=?", (question_id,)).fetchone()
        self.observation = {
            "question_id": question_id, "question_status": status, "stored_retrieval": stored,
            "sent_retrieval": [source["chunk_id"] for source in passages], "answer_already_committed": bool(prior_answer),
        }
        result = self.provider.generate(question, passages)
        self.observation["raw_structured_output"] = result.text
        return result

    def verify(self, question, passages, answer):
        check = self.provider.verify(question, passages, answer)
        self.observation["raw_verification_output"] = check.text
        self.observation["verification_response_id"] = check.response_id
        return check


def inspect_sqlite(path, question_id):
    with closing(sqlite3.connect(path)) as con:
        con.row_factory = sqlite3.Row
        question = dict(con.execute("SELECT * FROM questions WHERE id=?", (question_id,)).fetchone())
        answer = dict(con.execute("SELECT * FROM answers WHERE question_id=?", (question_id,)).fetchone())
        ranked = [dict(row) for row in con.execute(
            """SELECT r.question_id,r.chunk_id,r.rank,r.score,c.document_id,c.page_number,c.content_hash
               FROM retrieved_sources r JOIN document_chunks c ON c.id=r.chunk_id
               WHERE r.question_id=? ORDER BY r.rank""", (question_id,),
        )]
        cites = [dict(row) for row in con.execute(
            """SELECT ac.*,r.rank,d.original_filename,d.sha256
               FROM answer_citations ac
               JOIN document_chunks c ON c.id=ac.chunk_id AND c.document_id=ac.document_id
                   AND c.page_number=ac.page_number
               JOIN retrieved_sources r ON r.question_id=ac.question_id AND r.chunk_id=ac.chunk_id
               JOIN documents d ON d.id=c.document_id
               WHERE ac.question_id=? ORDER BY ac.position""", (question_id,),
        )]
        events = [dict(row) for row in con.execute(
            "SELECT * FROM audit_events WHERE question_id=? ORDER BY id", (question_id,),
        )]
        return {"question": question, "answer": answer, "ranked_sources": ranked, "citations": cites, "events": events}


def count_questions(path):
    with closing(sqlite3.connect(path)) as con:
        return con.execute("SELECT COUNT(*) FROM questions").fetchone()[0]


def check_trace(payload, captured, observation):
    question_id = payload["id"]
    assert captured["question"]["id"] == question_id
    assert captured["question"]["status"] == payload["status"]
    assert captured["question"]["request_id"] == payload["request_id"]
    assert captured["answer"]["id"] == payload["answer"]["id"]
    assert captured["answer"]["status"] == payload["status"] == payload["answer"]["status"]
    for name in ("body", "reason", "error_code", "api_outcome", "provider", "model", "prompt_version", "provider_response_id",
                 "input_tokens", "output_tokens", "latency_ms"):
        assert captured["answer"][name] == payload["answer"][name]
    keys = ("chunk_id", "document_id", "page_number", "rank")
    assert [[row[key] for key in keys] for row in captured["ranked_sources"]] == [
        [row[key] for key in keys] for row in payload["sources"]
    ]
    assert all(
        stored["content_hash"] == sha256(source["content"].encode("utf-8")).hexdigest()
        for stored, source in zip(captured["ranked_sources"], payload["sources"], strict=True)
    )
    assert [[row[key] for key in keys] for row in captured["citations"]] == [
        [row[key] for key in keys] for row in payload["citations"]
    ]
    scoped_ids = [source["chunk_id"] for source in captured["ranked_sources"]]
    for cite, public in zip(captured["citations"], payload["citations"], strict=True):
        assert cite["evidence_quote"] == public["evidence_quote"]
        assert cite["answer_id"] == captured["answer"]["id"] and cite["question_id"] == question_id
        assert cite["chunk_id"] in scoped_ids
    question_events = [row for row in captured["events"] if row["request_id"] == payload["request_id"]]
    expected_order = ["question.submit", "question.retrieve", "question.complete"]
    checks = [event for event in question_events if event["event_type"] == "question.verify"]
    if checks:
        expected_order.insert(2, "question.verify")
        if observation and observation.get("verification_response_id"):
            assert json.loads(checks[0]["detail"])["response_id"] == observation["verification_response_id"]
    if payload["status"] == "answered" and captured["answer"]["prompt_version"] != "1.0.0":
        assert len(checks) == 1 and checks[0]["outcome"] == "supported"
    if "verification_passed" in payload["answer"]:
        assert payload["answer"]["verification_passed"] == (
            payload["status"] == "answered" and any(event["outcome"] == "supported" for event in checks)
        )
    assert [row["event_type"] for row in question_events] == expected_order
    assert question_events[-1]["outcome"] == payload["status"]
    if observation:
        assert observation["question_id"] == question_id and observation["question_status"] == "processing"
        assert not observation["answer_already_committed"]
        assert observation["stored_retrieval"] == observation["sent_retrieval"] == scoped_ids
    if payload["status"] != "answered":
        assert not payload["citations"] and payload["answer"]["body"] is None


def questions_payload(case, documents):
    scope = dict(case["scope"])
    key = scope.pop("document", None)
    if key:
        scope["document_id"] = documents[key]["id"]
    return {"question": case["question"], **scope}


def run_case(client, settings, provider, case, docs, conversation_id):
    provider.observation = None
    before = count_questions(settings.database_path)
    inputs = questions_payload(case, docs)
    response = client.post("/questions", json={**inputs, "conversation_id": conversation_id})
    payload = response.json()
    checks = {}
    captured = None
    if response.status_code == 201:
        captured = inspect_sqlite(settings.database_path, payload["id"])
        check_trace(payload, captured, provider.observation)
        checks["request_id_matches"] = response.headers["x-request-id"] == payload["request_id"]
        checks["database_lineage"] = True
        checks["one_new_question"] = count_questions(settings.database_path) == before + 1
        indexed = {document["id"]: document for document in docs.values()}
        checks["scope_respected"] = all(
            (not inputs.get("document_id") or row["document_id"] == inputs["document_id"])
            and (not inputs.get("course_id") or indexed[row["document_id"]]["course_id"] == inputs["course_id"])
            for row in payload["sources"]
        )
    elif response.status_code < 500:
        checks["rejected_before_persistence"] = count_questions(settings.database_path) == before
    return {
        "id": case["id"], "request": inputs, "http_status": response.status_code, "response": payload,
        "provider_observation": provider.observation, "checks": checks, "sqlite": captured,
    }


def retrieval_metrics(cases, rows, cutoffs=(1, 3, 5)):
    positives = {case["id"]: case for case in cases if case["expected"]["evidence"]}
    selected = [row for row in rows if row["id"] in positives]
    if not selected:
        return {}
    result = {"judged_questions": len(selected), "unit": "distinct original PDF page", "cutoffs": {}}
    for k in cutoffs:
        precision, recall, reciprocal_rank = [], [], []
        returned = hit_count = 0
        for row in selected:
            relevant = {
                (item["document"], item["page"]) for item in positives[row["id"]]["expected"]["evidence"]
            }
            ranking = list(dict.fromkeys(
                (source["document_key"], source["page_number"]) for source in row["response"].get("sources", [])
            ))[:k]
            hits = set(ranking) & relevant
            returned += len(ranking)
            hit_count += len(hits)
            precision.append(len(hits) / k)
            recall.append(len(hits) / len(relevant))
            reciprocal_rank.append(next((1 / rank for rank, key in enumerate(ranking, 1) if key in relevant), 0))
        result["cutoffs"][str(k)] = {
            "precision": mean(precision), "recall": mean(recall), "mrr": mean(reciprocal_rank),
            "queries_with_full_recall": sum(value == 1 for value in recall),
            "returned_pages": returned, "relevant_returned_pages": hit_count,
            "precision_among_returned": hit_count / returned if returned else 0,
        }
    return result


def run(args):
    truth = load_ground_truth()
    cases = truth["questions"]
    chosen = set(args.case or ())
    if chosen:
        cases = [case for case in cases if case["id"] in chosen]
        if chosen != {case["id"] for case in cases}:
            raise SystemExit("One or more requested cases do not exist.")
    with TemporaryDirectory(prefix="eduevidence-benchmark-") as directory:
        folder = Path(directory)
        settings = Settings.from_environment().model_copy(update={
            "database_path": folder / "evaluation.sqlite3", "upload_directory": folder / "uploads",
            **({} if args.live else {"openai_api_key": SecretStr("")}),
        })
        base_provider = OpenAIProvider(settings)
        if args.live and not base_provider.configured:
            raise SystemExit("The requested live run requires configured OpenAI credentials.")
        seed(settings, verbose=False)
        provider = ObservedProvider(base_provider, settings.database_path)
        app = create_app(settings, provider, testing=True)
        conversation_id = str(uuid4())
        rows = []
        with TestClient(app) as client:
            docs = client.get("/documents", params={"limit": 100}).json()["items"]
            by_filename = {document["original_filename"]: document for document in docs}
            documents = {
                key: by_filename[item["filename"]] for key, item in truth["documents"].items()
            }
            keys_by_id = {item["id"]: key for key, item in documents.items()}
            for key, doc in documents.items():
                independent = truth["documents"][key]
                assert doc["sha256"] == independent["sha256"] and doc["page_count"] == independent["page_count"]
            for case in cases:
                row = run_case(client, settings, provider, case, documents, conversation_id)
                for item in row["response"].get("sources", []) + row["response"].get("citations", []):
                    item["document_key"] = keys_by_id[item["document_id"]]
                rows.append(row)
                outcome = row["response"].get("status") or row["response"].get("error", {}).get("code")
                print(f"{case['id']} {row['http_status']} {outcome}", flush=True)
        with closing(sqlite3.connect(settings.database_path)) as con:
            integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_key_errors = con.execute("PRAGMA foreign_key_check").fetchall()
            assert integrity == "ok" and not foreign_key_errors
    output = {
        "mode": "live_openai" if args.live else "offline_retrieval",
        "provider_configured": base_provider.configured,
        "requested_model": base_provider.model, "ground_truth_sha256": sha256(GROUND_TRUTH.read_bytes()).hexdigest(),
        "configuration": {
            "top_k": settings.retrieval_top_k, "chunk_words": settings.chunk_words,
            "chunk_overlap": settings.chunk_overlap, "min_score": settings.min_retrieval_score,
            "min_query_overlap": settings.min_query_overlap, "min_query_terms": settings.min_query_terms,
            "sdk_timeout_seconds": settings.openai_timeout_seconds, "sdk_max_retries": settings.openai_max_retries,
        },
        "sqlite_checks": {"integrity": integrity, "foreign_key_errors": foreign_key_errors},
        "retrieval_metrics": retrieval_metrics(cases, rows), "cases": rows,
    }
    write_json(args.output, output)
    print(json.dumps(output["retrieval_metrics"], indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true", help="Call the configured OpenAI provider using bundled synthetic documents.")
    parser.add_argument("--case", action="append", help="Limit to a named test ID, repeatable.")
    parser.add_argument("--output", type=Path, required=True, help="Write observed outcomes and inspected SQLite rows as JSON.")
    run(parser.parse_args())


if __name__ == "__main__":
    main()

