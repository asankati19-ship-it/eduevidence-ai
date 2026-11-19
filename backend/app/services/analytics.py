from backend.app.db.database import Database


AUDIT_SELECT = """
    SELECT e.*, q.question_text, d.original_filename AS document_filename
    FROM audit_events e
    LEFT JOIN questions q ON q.id=e.question_id
    LEFT JOIN documents d ON d.id=COALESCE(e.document_id,q.document_id)
"""


def overview(database: Database):
    with database.connection() as con:
        con.execute("BEGIN")
        documents = dict(con.execute("""
            SELECT count(*) AS total, count(*) FILTER(WHERE status='indexed') AS indexed,
                   count(*) FILTER(WHERE status='error') AS errors,
                   count(*) FILTER(WHERE status='processing') AS processing
            FROM documents WHERE retired_at IS NULL
        """).fetchone())
        documents["chunks"] = con.execute("""
            SELECT count(*) FROM document_chunks ch JOIN documents d ON d.id=ch.document_id
            WHERE d.status='indexed' AND ch.revision=d.active_revision
        """).fetchone()[0]
        questions = dict(con.execute("""
            SELECT count(*) AS total, count(*) FILTER(WHERE status='answered') AS answered,
                   count(*) FILTER(WHERE status='answered' AND EXISTS (
                       SELECT 1 FROM audit_events e WHERE e.question_id=questions.id
                         AND e.event_type='question.verify' AND e.outcome='supported'
                   )) AS verified,
                   count(*) FILTER(WHERE status='abstained') AS abstained,
                   count(*) FILTER(WHERE status='provider_error') AS provider_errors,
                   count(*) FILTER(WHERE status='validation_error') AS validation_errors,
                   count(*) FILTER(WHERE status='processing_error') AS processing_errors,
                   count(*) FILTER(WHERE status='processing') AS processing
            FROM questions
        """).fetchone())
        feedback = dict(con.execute("""
            SELECT count(*) AS total, count(*) FILTER(WHERE rating='helpful') AS helpful,
                   count(*) FILTER(WHERE rating='not_helpful') AS not_helpful FROM feedback
        """).fetchone())
        recent = [dict(row) for row in con.execute(AUDIT_SELECT + " ORDER BY e.id DESC LIMIT 8")]
        trend = [dict(row) for row in con.execute("""
            WITH RECURSIVE days(day) AS (
                SELECT date('now', '-6 days') UNION ALL
                SELECT date(day, '+1 day') FROM days WHERE day < date('now')
            )
            SELECT days.day, count(q.id) AS total, count(q.id) FILTER(WHERE q.status='answered') AS answered
            FROM days LEFT JOIN questions q ON q.created_at >= days.day AND q.created_at < date(days.day, '+1 day')
            GROUP BY days.day ORDER BY days.day
        """)]
        return {"documents": documents, "questions": questions, "feedback": feedback, "activity": recent, "trend": trend}


def audit_page(database, event_type, request_id, limit, offset):
    filters = []
    params = []
    for name, value in (("event_type", event_type), ("request_id", request_id)):
        if value:
            filters.append(f"e.{name}=?")
            params.append(value)
    where = " WHERE " + " AND ".join(filters) if filters else ""
    with database.connection() as con:
        con.execute("BEGIN")
        total = con.execute("SELECT count(*) FROM audit_events e" + where, params).fetchone()[0]
        items = [dict(row) for row in con.execute(
            AUDIT_SELECT + where + " ORDER BY e.id DESC LIMIT ? OFFSET ?", (*params, limit, offset),
        )]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

