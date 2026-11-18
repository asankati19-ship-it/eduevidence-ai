PRAGMA foreign_keys = ON;
BEGIN IMMEDIATE;

CREATE TABLE IF NOT EXISTS learners (
    id INTEGER PRIMARY KEY,
    display_name TEXT NOT NULL,
    external_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS courses (
    id INTEGER PRIMARY KEY,
    code TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    course_id INTEGER NOT NULL REFERENCES courses(id),
    title TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    storage_name TEXT NOT NULL UNIQUE,
    sha256 TEXT NOT NULL CHECK(length(sha256) = 64),
    size_bytes INTEGER NOT NULL CHECK(size_bytes > 0),
    page_count INTEGER NOT NULL CHECK(page_count > 0),
    status TEXT NOT NULL CHECK(status IN ('processing','indexed','error','retired')),
    active_revision INTEGER NOT NULL DEFAULT 0,
    job_id TEXT,
    error_code TEXT,
    error_message TEXT,
    text_pages INTEGER,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    retired_at TEXT
);
CREATE UNIQUE INDEX IF NOT EXISTS documents_live_hash ON documents(sha256) WHERE retired_at IS NULL;
CREATE INDEX IF NOT EXISTS documents_scope ON documents(course_id, status, id);
CREATE TABLE IF NOT EXISTS document_chunks (
    id INTEGER PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id),
    revision INTEGER NOT NULL CHECK(revision > 0),
    page_number INTEGER NOT NULL CHECK(page_number > 0),
    chunk_number INTEGER NOT NULL CHECK(chunk_number > 0),
    content TEXT NOT NULL CHECK(length(content) > 0),
    content_hash TEXT NOT NULL CHECK(length(content_hash) = 64),
    created_at TEXT NOT NULL,
    UNIQUE(document_id, revision, chunk_number),
    UNIQUE(id, document_id, page_number)
);
CREATE INDEX IF NOT EXISTS chunks_document_page ON document_chunks(document_id, revision, page_number);
CREATE TABLE IF NOT EXISTS questions (
    id INTEGER PRIMARY KEY,
    learner_id INTEGER NOT NULL REFERENCES learners(id),
    course_id INTEGER REFERENCES courses(id),
    document_id INTEGER REFERENCES documents(id),
    conversation_id TEXT,
    question_text TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('processing','answered','abstained','provider_error','validation_error','processing_error')),
    request_id TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL,
    completed_at TEXT
);
CREATE INDEX IF NOT EXISTS questions_conversation ON questions(conversation_id, id);
CREATE INDEX IF NOT EXISTS questions_status ON questions(status, id);
CREATE TABLE IF NOT EXISTS retrieved_sources (
    question_id INTEGER NOT NULL REFERENCES questions(id),
    chunk_id INTEGER NOT NULL REFERENCES document_chunks(id),
    rank INTEGER NOT NULL CHECK(rank > 0),
    score REAL NOT NULL CHECK(score >= 0 AND score <= 1.000001),
    PRIMARY KEY(question_id, chunk_id),
    UNIQUE(question_id, rank)
);
CREATE TABLE IF NOT EXISTS answers (
    id INTEGER PRIMARY KEY,
    question_id INTEGER NOT NULL UNIQUE REFERENCES questions(id),
    status TEXT NOT NULL CHECK(status IN ('answered','abstained','provider_error','validation_error','processing_error')),
    body TEXT,
    reason TEXT,
    provider TEXT NOT NULL,
    model TEXT,
    provider_response_id TEXT,
    prompt_version TEXT NOT NULL,
    api_outcome TEXT NOT NULL,
    error_code TEXT,
    retryable INTEGER NOT NULL DEFAULT 0 CHECK(retryable IN (0,1)),
    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms INTEGER,
    created_at TEXT NOT NULL,
    UNIQUE(id, question_id)
);
CREATE TABLE IF NOT EXISTS answer_citations (
    answer_id INTEGER NOT NULL,
    question_id INTEGER NOT NULL,
    chunk_id INTEGER NOT NULL,
    document_id INTEGER NOT NULL,
    page_number INTEGER NOT NULL,
    evidence_quote TEXT NOT NULL,
    position INTEGER NOT NULL CHECK(position > 0),
    PRIMARY KEY(answer_id, chunk_id),
    UNIQUE(answer_id, position),
    FOREIGN KEY(answer_id, question_id) REFERENCES answers(id, question_id),
    FOREIGN KEY(question_id, chunk_id) REFERENCES retrieved_sources(question_id, chunk_id),
    FOREIGN KEY(chunk_id, document_id, page_number) REFERENCES document_chunks(id, document_id, page_number)
);
CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY,
    answer_id INTEGER NOT NULL REFERENCES answers(id),
    learner_id INTEGER NOT NULL REFERENCES learners(id),
    rating TEXT NOT NULL CHECK(rating IN ('helpful','not_helpful')),
    comment TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE(answer_id, learner_id)
);
CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY,
    learner_id INTEGER REFERENCES learners(id),
    question_id INTEGER REFERENCES questions(id),
    document_id INTEGER REFERENCES documents(id),
    request_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    outcome TEXT NOT NULL,
    detail TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS audit_request ON audit_events(request_id, id);
CREATE INDEX IF NOT EXISTS audit_event_type ON audit_events(event_type, id);

INSERT OR IGNORE INTO learners(id, display_name, external_id, created_at)
VALUES (1, 'Demo Learner', 'synthetic-local-learner', strftime('%Y-%m-%dT%H:%M:%fZ','now'));
INSERT OR IGNORE INTO courses(id, code, title, created_at) VALUES
(1, 'PY-101', 'Python Programming', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
(2, 'AI-201', 'AI & Machine Learning', strftime('%Y-%m-%dT%H:%M:%fZ','now')),
(3, 'LMS-001', 'LMS Policies', strftime('%Y-%m-%dT%H:%M:%fZ','now'));

PRAGMA user_version = 1;
COMMIT;

