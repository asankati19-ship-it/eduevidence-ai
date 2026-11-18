# API configuration

Create a root `.env` from `.env.example`. The FastAPI process reads environment variables first and the file second. Restart the backend after changing either. Relative file paths resolve from the project root.

| Variable | Default | Role |
|---|---|---|
| `OPENAI_API_KEY` | Empty | Key for the official OpenAI API. Store it only in the environment or ignored `.env`. |
| `OPENAI_MODEL` | `gpt-4.1-mini` | A Responses API model with Structured Outputs access. |
| `OPENAI_TIMEOUT_SECONDS` | 25 | SDK timeout per attempt, up to 120 seconds. |
| `OPENAI_MAX_RETRIES` | 1 | SDK retries after the initial attempt, bounded to two. |
| `DATABASE_PATH` | `runtime/eduevidence.sqlite3` | Writable SQLite database. |
| `UPLOAD_DIRECTORY` | `runtime/uploads` | Container for server-named PDFs. |
| `RETRIEVAL_TOP_K` | 5 | Maximum ranked passages retained per question. |
| `MIN_RETRIEVAL_SCORE` | 0.18 | Best-passage cosine similarity floor. |
| `MIN_QUERY_TERMS` | 2 | Distinct content terms required in the question. |
| `MIN_QUERY_OVERLAP` | 1 | Required number of shared content terms in an eligible passage. |
| `CHUNK_WORDS` / `CHUNK_OVERLAP` | 135 / 24 | Page-local chunk window and overlap. Reindex existing PDFs after a change. |
| `MAX_PDF_MB` / `MAX_PDF_PAGES` | 20 / 120 | File and page limits. |

The provider sends the learner's question and selected ranked passages to the official OpenAI Responses endpoint. After local schema and citation checks, a separate structured call checks the candidate against the validated quotations. Both calls use strict schemas, the configured per-attempt timeout and retry limit, and `store=false`. Provider access, limits and retention policies are managed by your OpenAI project.

The status screen reports whether a key is configured. A live supported question verifies access. The `answers` record stores the generation model, response ID, token counts and latency when the provider supplies them. The `question.verify` audit event carries the verification outcome and corresponding metadata. A provider or verification error has an explicit status and suppresses the proposed answer and citations. Older answers lack a verification event and appear as historical answers in the UI.

[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses) · [Responses API reference](https://developers.openai.com/api/reference/resources/responses/methods/create)

## Endpoints

| Method | Route | Behavior |
|---|---|---|
| GET | `/health`, `/system/status` | SQLite reachability and redacted configuration |
| GET | `/courses` | Synthetic LMS catalog |
| GET | `/documents`, `/documents/{id}` | Active document collection and metadata |
| POST | `/documents/upload` | Multipart `file`, `course_id`, optional `title`. Returns 202 and indexing status. |
| GET | `/documents/{id}/pages/{page}` | Rendered PNG of the 1-based page |
| POST | `/documents/{id}/reindex` | Returns 202 with the current job status |
| DELETE | `/documents/{id}` | Retires an active PDF, returns 204 |
| POST | `/questions` | Persists a trace and returns 201 with the outcome |
| GET | `/questions/history`, `/questions/{id}` | Filtered history and the full trace |
| POST | `/answers/{id}/feedback` | Records or updates the learner's rating |
| GET | `/analytics/overview`, `/audit/events` | SQL aggregates and audit rows |

Collection endpoints use `limit` and `offset`. Completed work returns a question ID even when the answer status is an abstention or provider failure. Request validation and resource failures use an `error` envelope and HTTP 4xx/5xx. Use `X-Request-ID` to correlate API responses and audit rows. The browser calls these routes through Vite's `/api` proxy.

