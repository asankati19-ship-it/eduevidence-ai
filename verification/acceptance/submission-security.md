# Submission security and artifact inspection

Project 022 · Final acceptance

| Check | Observed result |
|---|---|
| Maintained source and packaged credentials | Scanned 223 maintained text files in the working tree and all text entries in the previous accuracy archive for common provider keys, GitHub tokens, AWS access keys, and private-key headers. Found zero matching secrets. The checked-in OpenAI credential template is blank. All 37 email-like archive hits were npm package/version banners. |
| Ignore rules | A disposable Git repository containing the project ignore file excluded all 14 tested credential, SQLite, log, cache, dependency and generated-output paths. All five intended sample and setup assets remained eligible. Used `git check-ignore --no-index --stdin -z`. |
| Prior package contents | ZIP CRC validation passed for 261 entries. All 30 expected asset paths were present, covering Windows setup, both dependency lockfiles, prompt pack, three PDFs, seed database, schema, diagrams, testing, demo, provenance and checklist. The filename check returned zero excluded runtime, credential, generated, log-extension and private SQLite entries. |
| Prior package host paths | Four historical evidence files contained absolute local profile paths. The required correction for the next package is to redact those paths from exported text evidence while retaining raw working evidence. See the list below. |
| Synthetic seed database | Reopened the archived SQLite seed in memory. `PRAGMA integrity_check` returned `ok` and `PRAGMA foreign_key_check` returned zero rows. Found one Demo Learner, three courses, three documents and ten chunks. Question, answer, retrieval, citation and feedback tables were empty. All three archived document hashes matched the synthetic PDFs. The archived seed matched the working seed byte for byte. |
| Installed backend dependencies | `.\.venv\Scripts\python.exe -m pip check` returned `No broken requirements found`. Pillow is imported by the fixture and edge runner and pinned in the tested lockfile. The flexible requirements file obtains it via ReportLab. |

The prior archive path findings were `verification/live-acceptance-reviewed.txt`, `verification/live-acceptance.txt`, `verification/pytest.txt` and `verification/ui/pytest.txt`. The previous packer applied path sanitization only under `verification/functional/`. The final export sanitizes text evidence across the full verification tree. The flexible requirements file now directly declares the already pinned Pillow dependency. [Final package check](package-verification.txt)

## Defensive controls

| Control | Implementation and verification |
|---|---|
| Key and diagnostics | Environment and local dotenv settings load the key into `SecretStr`. The official SDK uses it server side. Schema-constrained requests set `store=False`. System status exposes the configured flag and timing settings. Error logging uses request IDs and exception types. Inspected `backend/app/core/config.py`, `backend/app/services/provider.py`, `backend/app/api/routes.py` and `backend/app/main.py`. |
| PDF ingestion and storage | Request and file byte caps, page limits, genuine signature and parser checks, encrypted-file rejection, normalized display filenames, server-generated storage names, directory containment and content hashing. Inspected `backend/app/main.py`, `backend/app/services/pdf.py` and `backend/app/services/documents.py`. Six existing upload defense tests passed. |
| SQLite writes | Parameterized query values, per-connection foreign keys, serialized write transactions and rollback. Inspected `backend/app/db/database.py`, `database/schema.sql` and the service query paths. The foreign-key and rollback test passed. |
| Local browser boundary | Loopback server bind and trusted-host middleware. The write-origin test rejected a foreign origin. React answer rendering permits a restricted Markdown element set and skips raw HTML. Inspected `frontend/vite.config.ts`, `backend/app/main.py` and `frontend/src/components/AnswerMarkdown.tsx`. |
| Untrusted document content | The structured SDK fixture test passed. It checked strict output schema and that the source passage is placed inside the JSON evidence boundary. The main accuracy suite separately covers citation and evidence validation. |

The existing targeted suite returned 9 passed and one known Starlette test-client deprecation warning. It exercised filename containment, encrypted PDF rejection, file and body size limits, streamed body limits, page limits, SQLite constraints and rollback, foreign-origin writes, and structured SDK passage handling. The command was run from the project root.

```powershell
.\.venv\Scripts\python.exe -m pytest -q `
  backend/tests/test_documents.py::test_filename_sanitization_and_storage_path `
  backend/tests/test_documents.py::test_encrypted_pdf_rejected `
  backend/tests/test_documents.py::test_upload_size_limit `
  backend/tests/test_documents.py::test_http_body_limit `
  backend/tests/test_documents.py::test_streamed_body_limit_without_content_length `
  backend/tests/test_documents.py::test_page_count_limit `
  backend/tests/test_questions.py::test_foreign_keys_and_failed_transactions_roll_back `
  backend/tests/test_questions.py::test_foreign_origin_write_rejected `
  backend/tests/test_provider.py::test_sdk_structured_response_and_untrusted_passage_delimiting
```

## Scope and handoff

This review covers the local synthetic workspace, defensive regression cases, filesystem-visible source and the previous offline release archive. Git history, GitHub publication, a current dependency vulnerability feed, production authorization, and multi-tenant isolation remain outside verified scope. The submission checklist's live evaluator step still requires the evaluator's own configured credential.
