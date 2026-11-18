"""Run the real OpenAI route against independently specified synthetic answers."""

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import re
from uuid import uuid4

from fastapi.testclient import TestClient
import httpx

from backend.app.core.config import ROOT, Settings
from backend.app.main import create_app
from scripts.seed_data import seed


def fold(value):
    normalized = re.sub(r"[^\w%]+", " ", value.casefold()).strip()
    normalized = re.sub(r"\bper (?:each|every)\b", "per", normalized)
    normalized = re.sub(r"\b(\d+ percentage points) (?:are )?(?:deducted|subtracted)\b", r"\1", normalized)
    return re.sub(r"\b(4|5)\b", lambda match: {"4": "four", "5": "five"}[match[0]], normalized)


def matched_facts(anchors, body):
    actual = fold(body or "")
    return [anchor for anchor in anchors if fold(anchor) in actual]


def check_case(client, case, conversation):
    result = client.post("/questions", json={
        "question": case["question"], "course_id": case["course_id"], "conversation_id": conversation,
    })
    result.raise_for_status()
    trace = result.json()
    answer = trace["answer"]
    expected = case.get("status", "answered")
    citations = trace["citations"]
    anchors = case.get("required_facts", [])
    found = matched_facts(anchors, answer["body"])
    identity = next((citation for citation in citations if citation["document_title"] == case.get("document")
                     and citation["page_number"] == case.get("page")), None)
    audit = client.get("/audit/events", params={"request_id": trace["request_id"]})
    audit.raise_for_status()
    audit_types = {event["event_type"] for event in audit.json()["items"]}
    checks = {
        "status_matches": trace["status"] == expected,
        "expected_content_matches": len(found) == len(anchors),
        "page_matches": bool(identity) if expected == "answered" else not citations,
        "trace_audited": {"question.submit", "question.retrieve", "question.complete"} <= audit_types,
    }
    if expected == "answered":
        checks["real_api_completed"] = (
            answer["provider"] == "openai" and answer["api_outcome"] == "completed" and bool(answer["provider_response_id"])
        )
        if identity:
            response = client.get(f"/documents/{identity['document_id']}/pages/{identity['page_number']}")
            checks["page_rendered"] = response.status_code == 200 and response.content.startswith(b"\x89PNG")
            feedback = client.post(f"/answers/{answer['id']}/feedback", json={"rating": "helpful"})
            checks["feedback_persisted"] = feedback.status_code == 200 and client.get(
                f"/questions/{trace['id']}"
            ).json()["answer"]["rating"] == "helpful"
    return {"expectation": case, "trace": trace, "checks": checks, "matched_facts": found}


def run(client, full):
    cases = json.loads((ROOT / "data/expected_answers.json").read_text(encoding="utf-8"))
    selected = cases if full else [cases[0], cases[-2]]
    conversation = str(uuid4())
    results = [check_case(client, case, conversation) for case in selected]
    history = client.get("/questions/history", params={"conversation_id": conversation})
    history.raise_for_status()
    return {"mode": "live_openai", "history_count": history.json()["total"], "cases": results}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--isolated", action="store_true", help="Use a temporary seeded workspace and the real SDK.")
    mode.add_argument("--recheck", type=Path, help="Rescore fact matching on captured live JSON without calling the provider.")
    parser.add_argument("--full", action="store_true", help="Run all eight acceptance questions, including six answers and their verification calls.")
    parser.add_argument("--output", type=Path, help="Write the execution result as JSON.")
    args = parser.parse_args()
    if args.recheck:
        result = json.loads(args.recheck.read_text(encoding="utf-8"))
        result["fact_checks_recomputed_from"] = args.recheck.name
        for entry in result["cases"]:
            required = entry["expectation"].get("required_facts", [])
            entry["matched_facts"] = matched_facts(required, entry["trace"]["answer"]["body"])
            entry["checks"]["expected_content_matches"] = len(entry["matched_facts"]) == len(required)
    elif args.isolated:
        with TemporaryDirectory() as work:
            settings = Settings.from_environment().model_copy(update={
                "database_path": Path(work) / "demo.sqlite3", "upload_directory": Path(work) / "uploads",
            })
            seed(settings, verbose=False)
            with TestClient(create_app(settings, testing=True)) as client:
                result = run(client, args.full)
    else:
        with httpx.Client(base_url=args.base_url, timeout=180) as client:
            result = run(client, args.full)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for entry in result["cases"]:
        trace, checks = entry["trace"], entry["checks"]
        print(f"{trace['status']} | {trace['question_text']} | {trace['answer']['error_code'] or 'no error'}")
        print("  " + ", ".join(f"{name}={passed}" for name, passed in checks.items()))
    return 0 if result["history_count"] == len(result["cases"]) and all(
        all(case["checks"].values()) for case in result["cases"]
    ) else 1


if __name__ == "__main__":
    raise SystemExit(main())

