from time import perf_counter
import json
import logging

from backend.app.core.errors import AppError, ProviderError
from backend.app.db.database import audit, utc_now
from backend.app.services.grounding import (
    conflicting_evidence, has_directive, validate_answer, validate_verification,
)
from backend.app.services.provider import PROMPT_VERSION
from backend.app.services.retrieval import rank_passages


LOGGER = logging.getLogger(__name__)
SOURCE_SELECT = """
SELECT ch.id AS chunk_id, ch.document_id, ch.page_number, ch.chunk_number, ch.revision,
       ch.content, d.title AS document_title, d.original_filename, d.course_id
FROM document_chunks ch JOIN documents d ON d.id=ch.document_id
"""
QUESTION_SELECT = """
SELECT q.*, d.title AS document_title FROM questions q LEFT JOIN documents d ON d.id=q.document_id
"""


class QuestionService:
    def __init__(self, db, settings, provider, lms):
        self.db = db
        self.settings = settings
        self.provider = provider
        self.lms = lms

    def ask(self, data, request_id):
        learner_id = self.lms.learner()["id"]
        with self.db.connection(write=True) as con:
            if data.course_id and con.execute("SELECT id FROM courses WHERE id=?", (data.course_id,)).fetchone() is None:
                raise AppError(422, "invalid_course", "Select an existing course.")
            if data.document_id:
                document = con.execute("SELECT course_id,status FROM documents WHERE id=?", (data.document_id,)).fetchone()
                if document is None or document["status"] == "retired":
                    raise AppError(404, "document_not_found", "Active document not found.")
                if document["status"] != "indexed":
                    raise AppError(409, "document_unavailable", "This document is not ready for questions.")
                if data.course_id and data.course_id != document["course_id"]:
                    raise AppError(422, "scope_mismatch", "The selected document is outside the selected course.")

            question_id = con.execute(
                """INSERT INTO questions
                   (learner_id,course_id,document_id,conversation_id,question_text,status,request_id,created_at)
                   VALUES (?,?,?,?,?,'processing',?,?)""",
                (learner_id, data.course_id, data.document_id, str(data.conversation_id) if data.conversation_id else None,
                 data.question, request_id, utc_now()),
            ).lastrowid
            audit(con, request_id, "question.submit", "accepted", question_id=question_id, document_id=data.document_id)

        params = (data.course_id, data.course_id, data.document_id, data.document_id)
        result = None
        verification = None
        phase = "retrieval"
        started = perf_counter()
        try:
            corpus = self.db.all(
                SOURCE_SELECT + """ WHERE d.status='indexed' AND ch.revision=d.active_revision
                AND (? IS NULL OR d.course_id=?) AND (? IS NULL OR d.id=?) ORDER BY ch.id""", params,
            )
            eligible = [source for source in corpus if not has_directive(source["content"])]
            excluded = len(corpus) - len(eligible)
            ranked, reason = rank_passages(data.question, eligible, self.settings)
            if not reason and conflicting_evidence(data.question, ranked):
                reason = "The selected materials give conflicting values for this policy. Select the document that applies."
            if reason and excluded and not ranked:
                reason = "The selected material does not provide usable evidence. Text directed at the assistant was excluded."
            detail = f"{len(ranked)} passages"
            if excluded:
                detail += f", {excluded} instruction-bearing passages excluded"
            with self.db.connection(write=True) as con:
                con.executemany(
                    "INSERT INTO retrieved_sources(question_id,chunk_id,rank,score) VALUES (?,?,?,?)",
                    [(question_id, row["chunk_id"], row["rank"], row["score"]) for row in ranked],
                )
                audit(con, request_id, "question.retrieve", "insufficient" if reason else "sufficient",
                      question_id=question_id, detail=detail)

            if reason:
                self.finish(question_id, request_id, "abstained", "skipped", reason=reason)
                return self.get(question_id)

            started = perf_counter()
            phase = "generation"
            result = self.provider.generate(data.question, ranked)
            phase = "validation"
            parsed = validate_answer(result.text, ranked, data.question)
            if parsed.status == "answered":
                phase = "verification"
                verification = {"outcome": "failed"}
                check = self.provider.verify(data.question, ranked, parsed)
                verification.update({
                    "model": check.model, "response_id": check.response_id,
                    "input_tokens": check.input_tokens, "output_tokens": check.output_tokens, "latency_ms": check.latency_ms,
                })
                phase = "validation"
                verdict = validate_verification(check.text)
                verification["outcome"] = verdict.outcome
                if verdict.outcome == "conflict":
                    self.finish(
                        question_id, request_id, "abstained", "completed",
                        reason="The selected materials contain conflicting applicable information.",
                        result=result, verification=verification,
                    )
                    return self.get(question_id)
                if verdict.outcome == "unsupported":
                    raise ProviderError("unsupported_answer", "The proposed answer did not pass evidence verification.", True)
            self.finish(
                question_id, request_id, parsed.status, "completed",
                body=parsed.answer, reason=parsed.abstention_reason, citations=parsed.citations,
                result=result, verification=verification,
            )
        except ProviderError as exc:
            if verification and verification["outcome"] == "failed":
                verification["error_code"] = exc.code
            self.finish(
                question_id, request_id, "validation_error" if phase == "validation" else "provider_error",
                "invalid_response" if phase == "validation" else ("skipped" if exc.code == "missing_credentials" else "failed"),
                reason=exc.message, error=exc.code, retryable=exc.retryable,
                result=result, verification=verification,
                elapsed=round((perf_counter() - started) * 1000),
            )
        except Exception as exc:
            LOGGER.error("question_failure request_id=%s type=%s", request_id, type(exc).__name__)
            self.finish(
                question_id, request_id, "processing_error", "interrupted",
                reason="The question could not be processed. Try again.", error="internal_processing_error", retryable=True,
                result=result, verification=verification,
            )
        return self.get(question_id)

    def finish(self, question_id, request_id, status, api_outcome, *, body=None, reason=None,
               citations=(), result=None, error=None, retryable=False, elapsed=None, verification=None):
        now = utc_now()
        with self.db.connection(write=True) as con:
            changed = con.execute(
                "UPDATE questions SET status=?,completed_at=? WHERE id=? AND status='processing'", (status, now, question_id),
            ).rowcount
            if not changed:
                return
            answer_id = con.execute(
                """INSERT INTO answers
                   (question_id,status,body,reason,provider,model,provider_response_id,prompt_version,
                    api_outcome,error_code,retryable,input_tokens,output_tokens,latency_ms,created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (question_id, status, body, reason, self.provider.name, result.model if result else self.provider.model,
                 result.response_id if result else None, PROMPT_VERSION, api_outcome, error, int(retryable),
                 result.input_tokens if result else None, result.output_tokens if result else None,
                 result.latency_ms if result and result.latency_ms is not None else elapsed, now),
            ).lastrowid
            con.executemany(
                """INSERT INTO answer_citations(answer_id,question_id,chunk_id,document_id,page_number,evidence_quote,position)
                   VALUES (?,?,?,?,?,?,?)""",
                [
                    (answer_id, question_id, c.chunk_id, c.document_id, c.page_number, c.evidence_quote, index)
                    for index, c in enumerate(citations, 1)
                ],
            )
            if verification is not None:
                audit(con, request_id, "question.verify", verification["outcome"], question_id=question_id,
                      detail=json.dumps(verification, separators=(",", ":")))
            audit(con, request_id, "question.complete", status, question_id=question_id, detail=error or api_outcome)

    def recover(self):
        for row in self.db.all("SELECT id,request_id FROM questions WHERE status='processing'"):
            self.finish(
                row["id"], row["request_id"], "processing_error", "interrupted",
                reason="Processing stopped before the answer completed. Try again.", error="interrupted", retryable=True,
            )

    def get(self, question_id):
        with self.db.connection() as con:
            con.execute("BEGIN")
            row = con.execute(QUESTION_SELECT + " WHERE q.id=?", (question_id,)).fetchone()
            if row is None:
                raise AppError(404, "question_not_found", "Question not found.")
            return self._trace(con, dict(row))

    def history(self, limit, offset, status=None, conversation_id=None, search=None):
        filters = []
        params = []
        for field, value in (("q.status", status), ("q.conversation_id", conversation_id)):
            if value:
                filters.append(f"{field}=?")
                params.append(value)
        if search:
            filters.append("instr(lower(q.question_text),lower(?))>0")
            params.append(search)
        where = " WHERE " + " AND ".join(filters) if filters else ""
        with self.db.connection() as con:
            con.execute("BEGIN")
            total = con.execute("SELECT COUNT(*) FROM questions q" + where, params).fetchone()[0]
            rows = con.execute(
                QUESTION_SELECT + where + " ORDER BY q.id DESC LIMIT ? OFFSET ?", (*params, limit, offset),
            ).fetchall()
            return {"items": [self._trace(con, dict(row)) for row in rows], "total": total, "limit": limit, "offset": offset}

    def _trace(self, con, row):
        question_id = row["id"]
        answer = con.execute(
            """SELECT a.*, f.rating, EXISTS (
                   SELECT 1 FROM audit_events e WHERE e.question_id=a.question_id
                     AND e.event_type='question.verify' AND e.outcome='supported'
               ) AND a.status='answered' AS verification_passed
               FROM answers a LEFT JOIN feedback f ON f.answer_id=a.id AND f.learner_id=?
               WHERE a.question_id=?""", (row["learner_id"], question_id),
        ).fetchone()
        sources = con.execute(
            SOURCE_SELECT.replace("SELECT", "SELECT r.rank, r.score,", 1)
            + " JOIN retrieved_sources r ON r.chunk_id=ch.id WHERE r.question_id=? ORDER BY r.rank", (question_id,),
        ).fetchall()
        citations = con.execute(
            SOURCE_SELECT.replace("SELECT", "SELECT a.evidence_quote, a.position, r.rank, r.score,", 1)
            + """ JOIN answer_citations a ON a.chunk_id=ch.id
            JOIN retrieved_sources r ON r.chunk_id=ch.id AND r.question_id=a.question_id
            WHERE a.question_id=? ORDER BY a.position""", (question_id,),
        ).fetchall()
        return {**row, "answer": dict(answer) if answer else None, "sources": [dict(x) for x in sources],
                "citations": [dict(x) for x in citations]}

    def feedback(self, answer_id, data, request_id):
        learner_id = self.lms.learner()["id"]
        now = utc_now()
        with self.db.connection(write=True) as con:
            row = con.execute(
                "SELECT question_id,status FROM answers WHERE id=?", (answer_id,),
            ).fetchone()
            if row is None:
                raise AppError(404, "answer_not_found", "Answer not found.")
            if row["status"] not in ("answered", "abstained"):
                raise AppError(409, "feedback_unavailable", "Feedback is available for answered or abstained questions.")
            con.execute(
                """INSERT INTO feedback(answer_id,learner_id,rating,comment,created_at,updated_at) VALUES (?,?,?,?,?,?)
                   ON CONFLICT(answer_id,learner_id) DO UPDATE SET
                   rating=excluded.rating,comment=excluded.comment,updated_at=excluded.updated_at""",
                (answer_id, learner_id, data.rating, data.comment, now, now),
            )
            audit(con, request_id, "answer.feedback", data.rating, question_id=row["question_id"])
        return {"answer_id": answer_id, "rating": data.rating}

