"""Export the audit ledger from captured runs and independently reviewed answers."""

import csv
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "verification/functional"
OUTPUT = ROOT / "docs/functional_accuracy_report.csv"
FIELDS = (
    "test_id", "case_type", "evidence_mode", "input_question", "input_scope", "source_document",
    "expected_answer", "expected_document_pages", "expected_source_evidence", "expected_citations",
    "expected_status", "expected_http_status", "expected_error_code",
    "baseline_actual_answer", "baseline_actual_status", "baseline_result", "baseline_failure_reason",
    "actual_retrieved_passages", "actual_answer", "actual_citations", "actual_status", "actual_http_status",
    "actual_error_code", "actual_reason", "provider_response_id", "verification_response_id",
    "pass_fail", "failure_reason", "root_cause", "fix_implemented", "retest_result", "evidence_file",
)


def read(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def serialize(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def stripped_sources(items):
    return [{
        key: row[key] for key in
        ("document_key", "document_id", "original_filename", "page_number", "chunk_id", "revision", "rank", "score", "content")
        if key in row
    } for row in items]


def stripped_citations(items):
    return [{
        key: row[key] for key in
        ("document_key", "document_id", "original_filename", "page_number", "chunk_id", "evidence_quote")
        if key in row
    } for row in items]


def source_filenames(scope, documents):
    if scope.get("document") in documents:
        return documents[scope["document"]]["filename"]
    if scope.get("document_id"):
        return ""
    return " | ".join(
        doc["filename"] for doc in documents.values() if not scope.get("course_id") or scope["course_id"] == doc["course_id"]
    )


def observed(payload, observation=None):
    answer = payload.get("answer") or {}
    error = payload.get("error") or {}
    status = payload.get("status") or "rejected"
    return {
        "actual_retrieved_passages": stripped_sources(payload.get("sources", [])),
        "actual_answer": answer.get("body"),
        "actual_citations": stripped_citations(payload.get("citations", [])),
        "actual_status": status,
        "actual_error_code": answer.get("error_code") or error.get("code") or payload.get("error_code"),
        "actual_reason": answer.get("reason") or error.get("message") or payload.get("error_message"),
        "provider_response_id": answer.get("provider_response_id"),
        "verification_response_id": (observation or {}).get("verification_response_id"),
    }


def audit_run(review, locked_hash):
    path = EVIDENCE / review["snapshot"]
    assert sha256(path.read_bytes()).hexdigest() == review["sha256"], f"Review does not identify {path.name}"
    run = read(path)
    assert run["ground_truth_sha256"] == locked_hash
    assert run["mode"] == "live_openai" and run["provider_configured"]
    answer_ids = {row["id"] for row in run["cases"] if row["response"].get("status") == "answered"}
    assert answer_ids == set(review["reviewed_answers"]), f"Every successful answer in {path.name} must have a review."
    return {row["id"]: row for row in run["cases"]}


def grade(case, row, review, require_verification=False):
    expected = case["expected"]
    payload = row["response"]
    outcome = observed(payload)
    failures = []
    for label in ("status", "error_code"):
        if outcome[f"actual_{label}"] != expected[label]:
            failures.append(f"Expected {label}={expected[label]}. Observed {outcome[f'actual_{label}']}.")
    if row["http_status"] != expected["http_status"]:
        failures.append(f"Expected HTTP {expected['http_status']}. Observed {row['http_status']}.")
    if not row["checks"] or not all(row["checks"].values()):
        failures.append(f"Failed scope or SQLite checks: {serialize(row['checks'])}")
    if outcome["actual_status"] == "answered":
        pages = {(cite["document_key"], cite["page_number"]) for cite in outcome["actual_citations"]}
        expected_pages = {(source["document"], source["page"]) for source in expected["evidence"]}
        if pages != expected_pages:
            failures.append(f"Required citation pages were {sorted(expected_pages)}. The answer displayed {sorted(pages)}.")
        if require_verification and not payload["answer"].get("verification_passed"):
            failures.append("The successful answer lacked a supported verification event.")
    if case["id"] in review.get("failures", {}):
        failures.append(review["failures"][case["id"]])
    return ("FAIL", " ".join(failures)) if failures else ("PASS", "")


def defect_details(test_id, defects):
    matches = [item for item in defects if test_id in item["tests"]]
    return {
        "root_cause": " ".join(f"{item['id']} {item['root_cause']}" for item in matches),
        "fix_implemented": " ".join(f"{item['id']} {item['fix']}" for item in matches),
    }


def question_rows(truth, review, baseline, final):
    for case in truth["questions"]:
        test_id = case["id"]
        expected = case["expected"]
        base = baseline[test_id]
        last = final[test_id]
        base_result, base_failure = grade(case, base, review["baseline"])
        result, reason = grade(case, last, review["final"], require_verification=True)
        outcome = observed(last["response"], last["provider_observation"])
        pages = [{"document": item["document"], "page": item["page"]} for item in expected["evidence"]]
        yield {
            "test_id": test_id, "case_type": f"benchmark/{case['category']}",
            "evidence_mode": ("live_openai" if outcome["provider_response_id"]
                              else "offline_branch_of_live_run"),
            "input_question": case["question"], "input_scope": case["scope"],
            "source_document": source_filenames(case["scope"], truth["documents"]),
            "expected_answer": expected["answer"], "expected_document_pages": pages,
            "expected_source_evidence": expected["evidence"], "expected_citations": pages,
            "expected_status": expected["status"], "expected_http_status": expected["http_status"],
            "expected_error_code": expected["error_code"], "baseline_actual_answer": base["response"].get("answer", {}).get("body"),
            "baseline_actual_status": observed(base["response"])["actual_status"],
            "baseline_result": base_result, "baseline_failure_reason": base_failure,
            **outcome, "actual_http_status": last["http_status"],
            "pass_fail": result, "failure_reason": reason, **defect_details(test_id, review["defects"]),
            "retest_result": result, "evidence_file": [
                f"verification/functional/{review[stage]['snapshot']}#{test_id}" for stage in ("baseline", "final")
            ],
        }


def supporting_rows(test_id, label, rows, evidence_file=None):
    """Summarize cases already represented individually elsewhere in the CSV."""
    names = [row["test_id"] for row in rows]
    ok = all(row["pass_fail"] == "PASS" for row in rows)
    return {
        "test_id": test_id, "case_type": "required_edge", "evidence_mode": sorted({row["evidence_mode"] for row in rows}),
        "input_question": [{"case": row["test_id"], "question": row.get("input_question")} for row in rows],
        "source_document": sorted({row["source_document"] for row in rows if isinstance(row.get("source_document"), str) and row["source_document"]}),
        "expected_answer": label, "expected_citations": {row["test_id"]: row.get("expected_citations") for row in rows},
        "expected_status": [row.get("expected_status") for row in rows],
        "actual_answer": {row["test_id"]: row.get("actual_answer") for row in rows},
        "actual_citations": {row["test_id"]: row.get("actual_citations") for row in rows},
        "actual_status": [row.get("actual_status") for row in rows],
        "actual_reason": f"Full passages and outcomes are in the individual rows {', '.join(names)}.",
        "pass_fail": "PASS" if ok else "FAIL", "retest_result": "PASS" if ok else "FAIL",
        "failure_reason": ", ".join(row["test_id"] for row in rows if row["pass_fail"] != "PASS"),
        "evidence_file": evidence_file or [row.get("evidence_file") for row in rows],
    }


def probes(rows, evidence_filename, review):
    for case in rows:
        test_id = case["id"]
        raw = case["observation"]
        observations = raw if isinstance(raw, list) else [raw]
        first = observations[0]
        response = first.get("response", {})
        seen = [observed(item.get("response", {})) for item in observations]
        success = "PASS" if case["passed"] else "FAIL"
        baseline = "FAIL" if test_id in review["failed_probes"] else None
        yield {
            "test_id": test_id, "case_type": ("regression" if test_id.startswith("R")
                                              else "required_edge" if int(test_id[1:]) <= 25 else "additional_edge"),
            "evidence_mode": case["mode"],
            "input_question": first.get("question") if len(observations) == 1 else [item["question"] for item in observations],
            "input_scope": first.get("scope") or first.get("filename"),
            "source_document": first.get("filename") or sorted({
                source["original_filename"] for item in seen for source in item["actual_retrieved_passages"]
            }),
            "expected_answer": case["expected"], "expected_status": review["probe_expected_status"][test_id],
            **seen[0], "actual_http_status": first.get("http_status"),
            "actual_retrieved_passages": [source for item in seen for source in item["actual_retrieved_passages"]],
            "actual_reason": {"observed": [item["actual_reason"] for item in seen], "checks": case["checks"],
                              "input_candidate": [item["supplied_candidate"] for item in observations if "supplied_candidate" in item]},
            "actual_error_code": seen[0]["actual_error_code"] or response.get("index_error"),
            "baseline_actual_status": "answered" if baseline else None, "baseline_result": baseline,
            "baseline_failure_reason": review["failed_probes"].get(test_id),
            "pass_fail": success, "failure_reason": ", ".join(key for key, result in case["checks"].items() if not result),
            **defect_details(test_id, review["defects"]), "retest_result": success,
            "evidence_file": f"verification/functional/{evidence_filename}#{test_id}",
        }


def verification_controls(rows, filename, truth, defects):
    for row in rows:
        source = row["source"]
        candidate = row["injected_candidate"]
        label = row["ground_truth_id"]
        test_id = row["id"]
        quote = candidate["citations"][0]["evidence_quote"]
        result = "PASS" if row["passed"] else "FAIL"
        yield {
            "test_id": test_id, "case_type": "verifier_control", "evidence_mode": "live_openai_verifier_only",
            "input_question": row["question"], "input_scope": {"ground_truth_id": label, "document_id": source["document_id"]},
            "source_document": source["document_title"], "expected_answer": truth[label]["expected"]["answer"],
            "expected_citations": truth[label]["expected"]["evidence"],
            "expected_status": row["expected"], "actual_retrieved_passages": [source],
            "actual_status": row["actual"], "actual_reason": {
                "injected_answer": candidate["answer"], "injected_quote": quote, "verification_reason": row["verification_reason"],
            },
            "verification_response_id": row["provider_response_id"], "pass_fail": result,
            "failure_reason": row["verification_reason"] if not row["passed"] else "",
            **defect_details(test_id, defects),
            "retest_result": result, "evidence_file": f"verification/functional/{filename}#{test_id}",
        }


def browser_edge(test_id, title, captures, evidence_files, single=False):
    records = [item for capture in captures for item in capture["cases"]]
    if single:
        records = records[:1]
        expected = ["answered"]
    else:
        expected = ["answered", "abstained", "abstained", "answered", "abstained", "provider_error"]
    traces = [item["browser_trace"] for item in records]
    outcomes = [observed(trace) for trace in traces]
    statuses = [outcome["actual_status"] for outcome in outcomes]
    passed = (
        statuses == expected
        and all(capture["integrity"] == "ok" and not capture["foreign_key_errors"] for capture in captures)
        and all(item["passed"] for item in records)
        and (not single or [(cite["document_id"], cite["page_number"]) for cite in traces[0]["citations"]]
             == [(traces[0]["document_id"], 4)])
    )
    result = "PASS" if passed else "FAIL"
    return {
        "test_id": test_id, "case_type": "required_edge", "evidence_mode": [capture["mode"] for capture in captures],
        "input_question": [trace["question_text"] for trace in traces],
        "source_document": sorted({trace["document_title"] for trace in traces if trace["document_title"]}),
        "expected_answer": title, "expected_status": expected,
        "expected_citations": ([{"document": "PY", "page": 4}] if single else "Only answered traces have citations."),
        "actual_retrieved_passages": [outcome["actual_retrieved_passages"] for outcome in outcomes],
        "actual_answer": [outcome["actual_answer"] for outcome in outcomes],
        "actual_citations": [outcome["actual_citations"] for outcome in outcomes], "actual_status": statuses,
        "actual_reason": [outcome["actual_reason"] for outcome in outcomes], "pass_fail": result, "retest_result": result,
        "failure_reason": "" if passed else "Browser status, PDF citation, or database lineage differed.",
        "evidence_file": [f"verification/functional/{name}" for name in evidence_files],
    }


def export():
    truth_path = ROOT / "data/evaluation_ground_truth.json"
    truth = read(truth_path)
    review = read(EVIDENCE / "independent-review.json")
    labels_hash = sha256(truth_path.read_bytes()).hexdigest()
    baseline = audit_run(review["baseline"], labels_hash)
    final = audit_run(review["final"], labels_hash)
    questions = {row["test_id"]: row for row in question_rows(truth, review, baseline, final)}
    by_id = {case["id"]: case for case in truth["questions"]}
    assert questions.keys() == baseline.keys() == final.keys()
    edges_file, verifier_file = "edge-cases-2.4.json", "live-verifier-controls-release-2.3.json"
    cases = {row["test_id"]: row for row in probes(read(EVIDENCE / edges_file)["cases"], edges_file, review)}
    controls = {
        row["test_id"]: row for row in
        verification_controls(read(EVIDENCE / verifier_file)["cases"], verifier_file, by_id, review["defects"])
    }
    browser_filenames = ("browser-2.4-live-sqlite.json", "browser-2.4-fixture-sqlite.json")
    live, fixture = (read(EVIDENCE / name) for name in browser_filenames)
    required = {
        test_id: supporting_rows(test_id, item["expected"], [questions[case] for case in item["cases"]])
        for test_id, item in review["benchmark_edges"].items()
    }
    required.update({key: value for key, value in cases.items() if value["case_type"] == "required_edge"})
    required["E03"] = browser_edge("E03", "The citation drawer displays the original handbook page 4 and its supporting text.",
                                   [live], [browser_filenames[0], "accuracy-live-citation.png"], single=True)
    required["E25"] = browser_edge("E25", "Browser traces reconcile to SQLite for successful, abstained, and provider-error outcomes.",
                                   [live, fixture], browser_filenames)
    required["E18"] = supporting_rows(
        "E18", "The full application must withhold unsupported candidate answers before persistence.",
        [row for key, row in cases.items() if key.startswith("R")],
    )
    assert sorted(required) == [f"E{index:02}" for index in range(1, 26)]
    ledger = [*questions.values(), *(required[key] for key in sorted(required)),
              *(row for key, row in sorted(cases.items()) if key not in required), *controls.values()]
    assert len({row["test_id"] for row in ledger}) == len(ledger)
    with OUTPUT.open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, FIELDS)
        writer.writeheader()
        for row in ledger:
            writer.writerow({key: serialize(value) if isinstance(value, (dict, list)) else value for key, value in row.items()})
    print(serialize({
        "saved_rows": len(ledger), "benchmark_baseline": Counter(row["baseline_result"] for row in questions.values()),
        "benchmark_final": Counter(row["pass_fail"] for row in questions.values()),
        "required_edges": Counter(row["pass_fail"] for row in required.values()),
        "other_probes": Counter(row["pass_fail"] for row in ledger if row["test_id"] not in questions and row["test_id"] not in required),
    }))


if __name__ == "__main__":
    export()
