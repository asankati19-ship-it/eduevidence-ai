"""Adversarial candidate answers for the functional accuracy audit."""

import pytest

from backend.tests.fixtures import PYTHON_QUOTE, answer_with


LATE_QUESTION = "Who may submit after the deadline, and how late may they submit?"
LATE_QUOTE = (
    "For assignments marked eligible for late submission, a learner may submit up to 48 hours after the deadline."
)
RECORDING_QUESTION = "Does watching a recording count toward live attendance?"
RECORDING_QUOTE = "Watching a recording does not count toward live attendance."
ATTENDANCE_QUOTE = "A live session counts when the learner is present for at least half of its scheduled duration."
WEIGHTS_QUESTION = "What percentage of the Python course mark comes from the labs and the capstone?"
WEIGHTS_QUOTE = (
    "Graded labs account for 60% of the course mark. The capstone project accounts for 40% of the course mark."
)
COMPLETION_QUESTION = "What are the Python Programming course completion requirements?"

PROBES = [
    ("R01", COMPLETION_QUESTION, 1, 4, PYTHON_QUOTE,
     PYTHON_QUOTE.replace("at least 70%", "at most 70%"), "unsupported_answer"),
    ("R02", RECORDING_QUESTION, 3, 2, RECORDING_QUOTE,
     "Watching a recording counts toward live attendance.", "unsupported_answer"),
    ("R03", LATE_QUESTION, 3, 1, "a learner may submit up to 48 hours after the deadline.",
     "A learner may submit up to 48 hours after the deadline.", "incomplete_evidence_quote"),
    ("R04", WEIGHTS_QUESTION, 1, 3, WEIGHTS_QUOTE,
     "Graded labs account for 40% of the course mark. The capstone project accounts for 60% of the course mark.",
     "unsupported_answer"),
    ("R05", COMPLETION_QUESTION, 1, 4, "A capstone resubmission is available once after written feedback.",
     "A capstone resubmission is available once after written feedback.", "question_mismatch"),
    ("R06", LATE_QUESTION, 3, 1, LATE_QUOTE,
     "A learner may submit any assignment up to 48 hours after the deadline.", "unsupported_answer"),
    ("R08", "Where and how do I submit each graded Python lab, including the required files?", 1, 3,
     "Submit each lab through the LMS Assessments area as a ZIP archive containing Python source files and a short README.",
     "Submit each graded Python lab through LMS Assessments as a ZIP with Python source and a short README. "
     "Include instructions for running the project.", "unsupported_answer"),
    ("R10", RECORDING_QUESTION, 3, 2, RECORDING_QUOTE,
     "Watching a recording does not count toward live attendance. " + ATTENDANCE_QUOTE, "unsupported_answer"),
    ("R11", COMPLETION_QUESTION, 1, 4, PYTHON_QUOTE,
     "No. Submit all four graded labs, achieve at least 70% overall (which includes the labs and capstone combined), "
     "and earn a Pass on the capstone.", "unsupported_answer"),
]


@pytest.mark.parametrize(("test_id", "question", "document", "page", "quote", "body", "error"), PROBES,
                         ids=[probe[0] for probe in PROBES])
def test_no_unsupported_claim_can_be_persisted_as_answered(seeded, provider, test_id, question, document, page, quote, body, error):
    def candidate(_, passages):
        source = next(row for row in passages if row["document_id"] == document and row["page_number"] == page)
        return answer_with(source, quote, body)

    provider.override = candidate
    response = seeded.post("/questions", json={"question": question, "document_id": document})
    assert response.status_code == 201
    trace = response.json()
    assert trace["status"] == "validation_error", (test_id, trace["status"], trace["answer"])
    assert trace["answer"]["error_code"] == error
    assert trace["answer"]["body"] is None and not trace["citations"]
    assert not provider.verifications


POLAR_ABSENCE_CASES = [
    ("Do the assessment review rules grant an automatic grade increase?",
     "The assessment review rules do not grant an automatic grade increase. The source does not mention one."),
    ("Do the assessment review rules grant an automatic grade increase?",
     "No, the assessment review rules do not grant an automatic grade increase."),
    ("Does filing an assessment review guarantee a higher mark?",
     "Filing an assessment review guarantees a higher mark."),
]


@pytest.mark.parametrize(("question", "body"), POLAR_ABSENCE_CASES, ids=["explicit-absence", "negative-claim", "positive-claim"])
def test_a_claim_of_absence_abstains_before_verification(seeded, provider, question, body):
    quote = "Request an assessment review in the LMS Support area within five working days after the grade is released."
    provider.override = lambda _, passages: answer_with(
        next(source for source in passages if quote in source["content"]), quote, body,
    )
    trace = seeded.post("/questions", json={"question": question, "document_id": 3}).json()
    assert trace["status"] == "abstained"
    assert not trace["citations"] and trace["answer"]["body"] is None
    assert trace["answer"]["provider_response_id"] == "offline-fixture-response"
    assert not provider.verifications


def test_unsupported_policy_abstains_even_if_a_candidate_misquotes_the_procedure(seeded, provider):
    question, body = POLAR_ABSENCE_CASES[1]
    quote = "The policy describes how to request a review within five working days of receiving a grade."
    provider.override = lambda _, passages: answer_with(passages[0], quote, body)
    trace = seeded.post("/questions", json={"question": question, "document_id": 3}).json()
    assert trace["status"] == "abstained" and not trace["citations"]
    assert not provider.verifications


def test_each_capstone_mark_is_matched_despite_course_names_in_the_answer(seeded, provider):
    question = "Compare capstone weighting for Python Programming and AI and Machine Learning."
    body = ("The capstone project weighting in the Python Programming course is 40% of the course mark, "
            "while in the AI and Machine Learning course, the capstone report accounts for 45% of the final mark.")
    quotes = {
        1: "Graded labs account for 60% of the course mark. The capstone project accounts for 40% of the course mark.",
        2: ("The AI and Machine Learning final mark consists of two quizzes worth 20% combined, "
            "a modeling notebook worth 35%, and a capstone report worth 45%."),
    }

    def candidate(_, passages):
        sources = [c for c in passages if c["page_number"] == 3 and c["document_id"] in quotes]
        response = answer_with(sources[0], quotes[sources[0]["document_id"]], body)
        response["citations"] = [answer_with(c, quotes[c["document_id"]])["citations"][0] for c in sources]
        return response

    provider.override = candidate
    trace = seeded.post("/questions", json={"question": question}).json()
    assert trace["status"] == "answered", trace["answer"]
    assert {(cite["document_id"], cite["page_number"]) for cite in trace["citations"]} == {(1, 3), (2, 3)}


@pytest.mark.parametrize(("question", "document", "quote", "body"), [
    ("Does a Python capstone Pass by itself satisfy course completion requirements?", 1, PYTHON_QUOTE,
     "No, you must submit all four graded labs, achieve at least 70% overall, and earn a Pass on the capstone."),
    ("Are all assignments eligible for the 48-hour late submission window?", 3, LATE_QUOTE,
     "No, only assignments marked eligible for late submission may be submitted up to 48 hours after the deadline."),
    ("If I catch up by replaying a session, does that count toward my live attendance?", 3, RECORDING_QUOTE,
     "Watching a recording does not count toward live attendance."),
    ("What file formats are required for the AI modeling notebook and capstone report, and can I submit them together in one slot?",
     2, "Submit the modeling notebook as an IPYNB file and the capstone report as a PDF in separate LMS Assessments slots.",
     "The modeling notebook must be IPYNB and the capstone report PDF. They cannot be submitted in one LMS Assessments slot."),
    ("What minimum percentage of scheduled live sessions must I attend, and how long must I stay for a session to count?",
     3, "Learners must attend at least 75% of scheduled live sessions. " + ATTENDANCE_QUOTE,
     "You must attend at least 75% of scheduled live sessions, and a live session counts if you are present for at least half of its scheduled duration."),
], ids=["separate-requirements", "preserved-eligibility", "paraphrased-negation", "separate-file-formats", "compound-quantities"])
def test_supported_qualifications_survive_the_local_checks(seeded, provider, question, document, quote, body):
    provider.override = lambda _, passages: answer_with(
        next(source for source in passages if quote in source["content"]), quote, body,
    )
    trace = seeded.post("/questions", json={"question": question, "document_id": document}).json()
    assert trace["status"] == "answered", trace["answer"]
    assert trace["answer"]["body"] == body and trace["answer"]["verification_passed"]
    assert trace["citations"][0]["evidence_quote"] == quote


@pytest.mark.parametrize("wrong_second_page", [False, True], ids=["joins-verbatim", "rejects-wrong-page"])
def test_two_quotes_for_one_retrieved_chunk(seeded, provider, wrong_second_page):
    body = "Watching a recording does not count toward live attendance. " + ATTENDANCE_QUOTE

    def candidate(_, passages):
        source = next(row for row in passages if RECORDING_QUOTE in row["content"])
        response = answer_with(source, RECORDING_QUOTE, body)
        response["citations"].append({
            **response["citations"][0],
            "page_number": 3 if wrong_second_page else 2,
            "evidence_quote": ATTENDANCE_QUOTE,
        })
        return response

    provider.override = candidate
    trace = seeded.post("/questions", json={"question": RECORDING_QUESTION, "document_id": 3}).json()
    if wrong_second_page:
        assert trace["status"] == "validation_error" and trace["answer"]["error_code"] == "invalid_citation"
        assert not trace["citations"] and not provider.verifications
    else:
        assert trace["status"] == "answered" and trace["answer"]["verification_passed"]
        citation, = trace["citations"]
        assert citation["page_number"] == 2
        assert citation["evidence_quote"] == ATTENDANCE_QUOTE + " " + RECORDING_QUOTE
        assert citation["evidence_quote"] in " ".join(citation["content"].split())


def test_a_relative_quote_adds_its_verbatim_antecedent(seeded, provider):
    question = "How do I ask for ordinary learning help instead of an assessment review?"
    quote = "Requests for general learning support can be submitted in the same area using the Course Support category."
    body = "Submit the request in LMS Support using the Course Support category."
    provider.override = lambda _, passages: answer_with(
        next(source for source in passages if quote in source["content"]), quote, body,
    )
    trace = seeded.post("/questions", json={"question": question, "document_id": 3}).json()
    assert trace["status"] == "answered" and trace["answer"]["verification_passed"]
    citation = trace["citations"][0]
    assert citation["page_number"] == 3
    assert citation["evidence_quote"].startswith("Request an assessment review in the LMS Support area")
    assert citation["evidence_quote"].endswith(quote)
    assert citation["evidence_quote"] in " ".join(citation["content"].split())


def test_earlier_answer_without_verification_is_preserved_but_uncounted(seeded):
    trace = seeded.post("/questions", json={"question": COMPLETION_QUESTION, "document_id": 1}).json()
    assert trace["answer"]["verification_passed"]
    with seeded.app.state.db.connection(write=True) as db:
        db.execute("DELETE FROM audit_events WHERE question_id=? AND event_type='question.verify'", (trace["id"],))
        db.execute("UPDATE answers SET prompt_version='1.0.0' WHERE question_id=?", (trace["id"],))
    earlier = seeded.get(f"/questions/{trace['id']}").json()
    assert earlier["answer"]["body"] == trace["answer"]["body"]
    assert not earlier["answer"]["verification_passed"]
    stats = seeded.get("/analytics/overview").json()["questions"]
    assert stats["answered"] == 1 and stats["verified"] == 0


@pytest.mark.parametrize("kind", ["verify_timeout", "verify_malformed"])
def test_verification_failures_never_save_success(kind):
    from scripts.run_functional_edges import sdk_transport

    trace, checks = sdk_transport(kind)
    assert all(checks.values()), {"checks": checks, "trace": trace}


def test_both_capstone_weighting_pages_survive_cross_course_ranking(seeded):
    question = "Compare capstone weighting for Python Programming and AI and Machine Learning."
    trace = seeded.post("/questions", json={"question": question}).json()
    assert {(source["document_id"], source["page_number"]) for source in trace["sources"][:3]} >= {(1, 3), (2, 3)}


def test_old_flattened_physical_page_can_still_supply_a_complete_quote():
    from backend.app.services.grounding import excerpt_span

    legacy = (
        "PY-101 / SYNTHETIC COURSE LIBRARY Python Programming Course Handbook "
        "Completion requirements The conditions for course completion " + PYTHON_QUOTE
    )
    assert excerpt_span(legacy, PYTHON_QUOTE) is not None
    assert excerpt_span(legacy, "achieve at least 70% overall, and earn a Pass on the capstone project.") is None

