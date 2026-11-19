# EduEvidence AI final readiness report

**Current release decision — FAIL.** See the [November 19 hosted submission review](cloud_submission_review.md) for application revision `1ef04f9`, live browser outcomes, and test logs. The results below are archived from the earlier evaluation.


**READY FOR SUBMISSION**

Project 022 · LMS Document Q&A with Source Evidence · Career Lab Consulting · Review date November 18, 2026 · Submission deadline November 24, 2026

The reviewed Windows project met all 31 mandatory and enhanced requirements in the acceptance matrix. The application booted from a fresh installation, indexed the synthetic PDFs, returned grounded answers through the configured OpenAI API, displayed the cited original PDF pages, and persisted questions, feedback, and audit events in SQLite. The classified scope is the supplied local synthetic assignment. Independent evaluation remains pending. [Acceptance matrix](acceptance_matrix.md) · [Clean installation](../verification/acceptance/installation.md) · [Package verification](../verification/acceptance/package-verification.txt)

## What was verified

- **Application.** React and TypeScript provide Overview, Document Library, Knowledge Assistant, Question History, Feedback & Analytics, Audit Logs, and System Health. FastAPI handles PDF validation, ingestion and revision, scoped TF-IDF retrieval, structured responses, citation verification, feedback, and reporting. [Architecture](architecture.md) · [Final fixture browser run](../verification/acceptance/browser/playwright-fixture-final.txt)
- **Fresh live CLI.** The documented eight-question command produced six correct answers and two abstentions. All eight checks passed, including provider IDs, expected facts and page numbers, rendered source pages and feedback for answers, plus persisted history and audit events. [Live command output](../verification/acceptance/live-demo.txt) · [Responses](../verification/acceptance/live-demo.json)
- **Fresh ground-truth sample.** Q12 correctly cited two Python handbook pages for the 40% capstone weight and separate Pass. Q30 correctly attached 40% to Python and 45% to AI and Machine Learning. Q37 abstained when the assessment-review policy did not establish an automatic grade increase. The independent extractor matched all four displayed quotes to their physical PDF pages and rechecked 40 locked excerpts. The prior full live audit remains 43 of 43 cases with 38 independently checked displayed quotes. [Live sample](../verification/acceptance/live-ground-truth.json) · [Independent PDF proof](../verification/acceptance/independent-pdf.json) · [Full functional accuracy report](functional_accuracy_report.md)
- **Database and error persistence.** The final live upload saved question 4 and answer 4, with course document 4, chunk 14, and page 4. SQLite recorded submit, retrieve, verify, complete, and Helpful feedback. Three other live browser turns were reconciled to their SQLite records. The controlled timeout stored no answer body, citation, or provider ID, and the retry stored a separate answered turn. SQLite integrity checks passed with zero foreign-key errors. [Uploaded live answer](../verification/acceptance/browser/final-live-upload-sqlite.json) · [Live browser reconciliation](../verification/acceptance/browser/final-live-trace-sqlite.json) · [Timeout and retry SQLite records](../verification/acceptance/browser/browser-fixture-recovery-sqlite.json)
- **OpenAI.** The served snapshot was `gpt-4.1-mini-2025-04-14`. Live evidence contains response IDs, token usage, prompt version 2.4.0, and verification metadata. The credential was supplied through server configuration. Missing credentials were verified in a clean local run. Authentication rejection, rate limiting, timeout, and network error mapping were exercised by simulated SDK responses. [Provider demo evidence](../verification/acceptance/live-demo.json) · [Controlled errors](../verification/acceptance/edge-cases.json) · [API setup](api_configuration.md)

## Browser and UI

Edge exercised all seven pages at 1440×900, 768×1024, and 390×844. The suite checked navigation and keyboard focus, automated accessibility, horizontal overflow, upload and indexing states, wrong or duplicate uploads, reindexing and retirement, duplicate question submission, citation viewing, feedback, metrics after refresh, and recoverable errors. Chromium also loaded the clean installation with the expected dashboard values. Automated accessibility checks cover the tested rules and states. [Final fixture browser run](../verification/acceptance/browser/playwright-fixture-final.txt) · [Live browser run](../verification/acceptance/browser/playwright-live-final.txt) · [Chromium dashboard](../verification/acceptance/clean-overview.png)

The long uploaded-handbook question reproduced a split **Answered** badge in History at desktop width. The fix restored normal word wrapping for table badges. The journey now asserts a single-line result on desktop and mobile. A separate clean-install test initially matched two dashboard cards because its locator used a substring. An exact-label locator resolved the test harness failure. Both original failures and retests are retained. [History before fix](../verification/acceptance/browser/history-badge-reproduction.txt) · [Corrected desktop screenshot](../verification/acceptance/browser/final-live/live-history-with-answer-1440.png) · [Corrected mobile screenshot](../verification/acceptance/browser/final-live/live-history-with-answer-390.png) · [Clean-run diagnostic](../verification/acceptance/clean-startup-recheck.txt)

## Retrieval evaluation

The final offline run exercised all 43 locked cases. Metrics use the 34 answerable questions and count distinct original PDF pages. Fixed-denominator precision divides by K, including when fewer pages are returned. At K=5, 38 of 70 actual returns were relevant, or 54.29%. Scores are ranking signals. [Final retrieval artifact](../verification/acceptance/offline-benchmark.json) · [Independent labels](../data/evaluation_ground_truth.json)

| K | Precision | Recall | Mean reciprocal rank | All relevant pages retrieved |
|---:|---:|---:|---:|---:|
| 1 | 100.00% | 94.12% | 1.000 | 30/34 |
| 3 | 37.25% | 100.00% | 1.000 | 34/34 |
| 5 | 22.35% | 100.00% | 1.000 | 34/34 |

## Test execution

| Command or run | Observed result | Evidence |
|---|---|---|
| `.\.venv\Scripts\python.exe -m pytest -q` | 94 passed. One Starlette test-client deprecation warning | [Backend output](../verification/acceptance/backend.txt) |
| `.\.venv\Scripts\python.exe -m scripts.run_functional_edges --output verification/acceptance/edge-cases.json` | 23 passed. Includes mocked provider, invalid citation, persistence and rollback scenarios | [Output](../verification/acceptance/edge-cases.txt) |
| `.\.venv\Scripts\python.exe -m scripts.run_functional_evaluation --output verification/acceptance/offline-benchmark.json` | 43 cases captured. Retrieval metrics scored on 34 answerable cases. No live model calls | [Output](../verification/acceptance/retrieval.txt) |
| `.\.venv\Scripts\python.exe -m scripts.run_e2e_demo --isolated --full --output verification/acceptance/live-demo.json` | 8 passed | [Output](../verification/acceptance/live-demo.txt) |
| `.\.venv\Scripts\python.exe -m scripts.run_functional_evaluation --live --case Q12 --case Q30 --case Q37 --output verification/acceptance/live-ground-truth.json` | Three matched expected facts, citation sets or abstention | [Output](../verification/acceptance/live-ground-truth.txt) |
| `npm.cmd --prefix frontend run build` | TypeScript and Vite build passed after the table fix | [Output](../verification/acceptance/frontend-build.txt) |
| `npm.cmd run test:e2e` from `frontend` in fixture mode | 16 passed and four intentionally skipped by mode. Those cases passed in dedicated modes | [Final output](../verification/acceptance/browser/playwright-fixture-final.txt) |
| `npm.cmd run test:e2e -- --grep 'functional trace\|full journey'` in live mode | 2 passed after the table fix | [Final output](../verification/acceptance/browser/playwright-live-final.txt) |
| Dedicated Playwright fixture modes | Empty library, missing credentials, database error, trace and retry each passed. Total selected browser executions across modes was 23 | [Empty](../verification/acceptance/browser/playwright-empty.txt) · [Missing key](../verification/acceptance/browser/playwright-unconfigured.txt) · [Database error](../verification/acceptance/browser/playwright-database-error.txt) · [Fixture trace](../verification/acceptance/browser/playwright-fixture-trace.txt) · [Retry](../verification/acceptance/browser/playwright-recovery.txt) |

## Exact startup and demo

From the extracted project root in PowerShell, use Python 3.12 and the documented Node version. If the Windows launcher reports no suitable 3.12 runtime, invoke your installed Python 3.12 executable directly to create `.venv`. The clean run verified this fallback. [Windows README](../README.md) · [Installation checks and commands](../verification/acceptance/installation.md)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m scripts.seed_data
npm.cmd --prefix frontend ci
```

Put your OpenAI key in the ignored local `.env` or the backend process environment for live questions. Start FastAPI in that terminal.

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

In a second terminal run `npm.cmd --prefix frontend run dev` and open [Overview](http://127.0.0.1:5173). The walkthrough covers a live upload and answer, an unsupported question, and a labeled simulated failure with retry. Actual screenshots show the supporting PDF page and recovery state. [Exact demo steps](demo_script.md) · [Indexed PDF](../verification/acceptance/browser/final-live/live-indexed-upload.png) · [PDF citation](../verification/acceptance/browser/final-live/live-source-evidence.png) · [Abstention](../verification/acceptance/browser/final-live/accuracy-live-abstention.png) · [Simulated timeout](../verification/acceptance/browser/accuracy-fixture-timeout.png)

## Submission, known limitations, and blockers

The final ZIP includes the runnable frontend and backend, dependency locks, three original synthetic PDFs, clean sample SQLite database, schema, prompt pack, architecture and ER diagrams, test suites, acceptance matrix, setup and demo instructions, CSV evidence, execution logs, and browser screenshots. The export redacts local profile paths in text evidence while retaining its original working copies. The archive checks confirm a blank credential template, no private database, and matching original PDF hashes. [Submission checklist](submission_checklist.md) · [Security review](../verification/acceptance/submission-security.md) · [Final package verification](../verification/acceptance/package-verification.txt)

No mandatory blocker was reproduced in the reviewed environment. The standalone verifier still has three recorded false approvals. The application has separate local safeguards and the corresponding controlled cases passed. Live evidence covers the synthetic corpus and one model snapshot. Evaluator credentials, production authentication, tenant isolation, OCR, real-service outages, a dependency vulnerability-feed review, and public deployment were outside the verified scope. [Known limitations](known_limitations.md) · [Original verifier failures](../verification/functional/live-verifier-controls-release-2.3.json)

