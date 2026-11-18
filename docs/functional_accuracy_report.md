# EduEvidence AI functional accuracy audit

November 18, 2026 · Project 022 · Windows · Prompt and grounding version 2.4.0

The original application saved all six deliberately incorrect candidate answers as successful. The updated application blocked all six, preserved their failed outcomes, and now requires both source validation and a separate verification verdict before showing a new answer as verified. The product continues to use its FastAPI, SQLite, React, and OpenAI integration. [Original probe failures](../verification/functional/accuracy-probes-baseline.txt) · [Final named regressions](../verification/functional/accuracy-regressions-2.4.txt)

| Executed checks | Result | Evidence |
|---|---|---|
| Independent 43-case benchmark, original version | 33/43 full passes. 35/43 HTTP and outcome matches. | [Unedited baseline run](../verification/functional/live-baseline.json) |
| Independent 43-case benchmark, version 2.4.0 | 43/43 passed, including 34 correctly answered, five abstentions, and four input or scope rejections. | [Final live run](../verification/functional/live-acceptance-2.4.json) · [Console log](../verification/functional/live-acceptance-2.4.txt) |
| Required edge cases | 25/25 application-level edge cases passed. | [Case ledger](functional_accuracy_report.csv) · [Isolated edge run](../verification/functional/edge-cases-2.4.json) |
| Real OpenAI verification controls | 3/6 passed in isolation. V01, V05, and V06 falsely approved unsupported candidates. The application-level regressions rejected the corresponding failure patterns. | [Injected candidates and actual verdicts](../verification/functional/live-verifier-controls-release-2.3.json) |
| Backend suite | 94 passed, including 27 named accuracy regressions. | [Pytest output](../verification/functional/pytest-2.4.txt) |
| Browser suite | 22 passing executions across 20 distinct tests. Four cases skipped in the default mode ran in dedicated modes. | [Fixture suite](../verification/functional/playwright-2.4-full.txt) · [Live journey](../verification/functional/playwright-2.4-trace-live.txt) · [Simulated timeout](../verification/functional/playwright-2.4-trace-fixture.txt) |
| Frontend production build | Passed | [TypeScript and Vite output](../verification/functional/frontend-build-release.txt) |

Counts overlap where a required edge references a benchmark question, a browser execution, or a named regression. The CSV has a row per benchmark case and named edge plus supporting controls. It contains the literal prompts, scope, expected evidence, full ranked passages, answers, citations, errors, results, causes, and retests. [CSV ledger](functional_accuracy_report.csv) · [Manual review and defect annotations](../verification/functional/independent-review.json)

## Independent ground truth and scoring

I read all ten pages of the three original synthetic PDFs with a separate extractor and inspected the rendered pages before contacting the question API. I locked 43 cases with their expected facts, document and course scopes, page labels, exact excerpts, and outcomes. The cases include 34 answerable questions, five expected abstentions, and four expected request rejections. A separate `pypdf` check verified the original file hashes and 40 exact expected excerpts. The same independent parser located all 38 final displayed quotations on their exact original pages. [Locked labels](../data/evaluation_ground_truth.json) · [Independent page check](../verification/functional/final-pdf-evidence.json)

| Key | Original source | Pages |
|---|---|---:|
| PY | [Python Programming Course Handbook](../data/sample_documents/Python%20Programming%20Course%20Handbook.pdf) | 4 |
| AI | [AI and Machine Learning Course Guide](../data/sample_documents/AI%20and%20Machine%20Learning%20Course%20Guide.pdf) | 3 |
| LMS | [LMS Assessment and Attendance Policy](../data/sample_documents/LMS%20Assessment%20and%20Attendance%20Policy.pdf) | 3 |

A pass required matching HTTP status, terminal outcome, and error code where applicable. For answers, I checked every material statement against the cited quotations and original PDF, including timing, scope, conditions, units, and logical exclusions. Citation pages had to match the locked set, and each quote had to be traceable to a retrieved chunk for that question. New successful answers also required a persisted supported verification event. An abstention needed an empty answer and no citations. Rejected inputs had to create no question. [Ground truth and exact excerpts](../data/evaluation_ground_truth.json) · [Manual review rules](../verification/functional/independent-review.json)

## Retrieval results

The denominator for each macro metric is the 34 answerable benchmark questions. The ranking unit is a distinct original PDF page. Repeated chunks of the same page count once at their first rank. Precision@K divides relevant pages by K, including searches with fewer than K pages. Recall@K divides each question's retrieved relevant pages by its independently labeled relevant pages. MRR@K uses the reciprocal of the first relevant rank and assigns zero if there is no hit in the first K. [Offline baseline](../verification/functional/offline-baseline.json) · [Final offline run](../verification/functional/offline-acceptance-2.4.json)

| K | Precision baseline → updated | Recall baseline → updated | MRR baseline → updated | Questions with every relevant page baseline → updated |
|---:|---:|---:|---:|---:|
| 1 | 100.00% → 100.00% | 94.12% → 94.12% | 1.000 → 1.000 | 30 → 30 |
| 3 | 36.27% → 37.25% | 98.53% → 100.00% | 1.000 → 1.000 | 33 → 34 |
| 5 | 22.35% → 22.35% | 100.00% → 100.00% | 1.000 → 1.000 | 34 → 34 |

At K=5, relevant pages accounted for 38 of 115 actual baseline returns (33.04%) and 38 of 70 updated returns (54.29%). The fixed-denominator Precision@5 stays at 22.35% because the full set has only 38 labeled relevant pages across 170 nominal result slots. Q30 drove the Recall@3 change. Its Python capstone weighting page moved from rank 5 to rank 2 and the AI weighting page stayed at rank 1. Q36 confirmed that selecting the Python handbook excludes the attendance policy even when the question closely matches it. Cosine similarity is a ranking score and has no calibrated confidence interpretation. [Baseline ranks](../verification/functional/live-baseline.json) · [Final ranks and scope checks](../verification/functional/live-acceptance-2.4.json)

## Defects and remediation

The final capture records 39 persisted outcomes with matching API and SQLite state. The four rejected requests produced no new question. The benchmark CSV keeps the baseline failures with their original responses, and the intermediate browser and fixture failures remain linked below.

| Reproduced finding | Root cause and fix | Retest evidence |
|---|---|---|
| R01–R06 and Q03 accepted a wrong bound, reversed negation, clipped eligibility, switched grade weights, an answer to a different question, a blanket late rule, or an added lab instruction. | The original validator relied on shared terms and existing IDs. It now checks quote boundaries, question relevance, quantity and clause association, bounds and negation. A separate structured call checks every material fact and can block the answer. | [Six original failures](../verification/functional/accuracy-probes-baseline.txt) · [Named regressions](../verification/functional/accuracy-regressions-2.4.txt) |
| Q05 had a redundant schedule citation. Q06, Q18 and Q42 added facts beyond their quotes. Q11 and Q15 had sound inferences rejected. Q22 stitched two nonconsecutive source sentences into one quote. | Generation now requests concise answers and complete, contiguous quotes. Local validation allows inferences such as the impossibility of using one slot when the document explicitly assigns separate slots. Page-layout paragraphs survive indexing and unquoted details remain subject to verification. | [Actual baseline candidates and citations](../verification/functional/live-baseline.json) · [Final candidates and traces](../verification/functional/live-acceptance-2.4.json) |
| Q30's second weighting page was out of the top three. | Repeated boilerplate and differing grade-weight terminology obscured matching. Ranking removes repeated synthetic headings from the scoring text, normalizes weighting terminology and filters weak matches. Source display keeps the original chunk text. | [Cross-course regression](../verification/functional/accuracy-regressions-2.4.txt) · [Offline retrieval](../verification/functional/offline-acceptance-2.4.json) |
| Q29 originally lacked a quote that named the location. Version 2.0.0 then showed an answer with only “the same area” on its citation card. | The quote referred to LMS Support from earlier in the same passage. The validator now extends the quote to the named antecedent using original text from that chunk. | [Version 2.0.0 evidence](../verification/functional/live-retest.json) · [Reference regression](../verification/functional/accuracy-regressions-2.4.txt) |
| Q37 was falsely answered in versions 2.0.0 and 2.1.0. | Both model calls treated silence about a review outcome as a negative rule. The app now abstains when an answer relies on an omission or a focused yes-or-no question has insufficient topic coverage in the citations. Positive and negative variants are tested. | [Version 2.1.0 false success](../verification/functional/live-final.json) · [Before-fix failures](../verification/functional/polar-probes-before.txt) · [Live abstention in React](../verification/functional/accuracy-live-unstated-policy.png) |
| Q22 was rejected in version 2.2.0 when the model emitted two separately valid quotes for one chunk. | Each submitted source is now checked separately. Valid repeats are consolidated into one contiguous original excerpt. A wrong page or wrong document still fails. | [Live rejection](../verification/functional/live-release.json) · [Before-fix probe](../verification/functional/duplicate-quote-before.txt) · [Retest](../verification/functional/accuracy-regressions-2.4.txt) |
| Version 2.2.1 rejected Q23 with two correctly sourced quantities in one sentence. It also accepted an unquoted duration in Q22 and a parenthetical grade-composition detail in Q11. | Quantities are now checked in their clauses and simple written fractions are recognized. The verifier receives only the approved quotations, so it cannot use a retrieved passage that the reader cannot see cited as support. | [Version 2.2.1 live responses](../verification/functional/live-verified.json) · [Before-fix probes](../verification/functional/clause-probes-before.txt) · [Named regressions](../verification/functional/accuracy-regressions-2.4.txt) · [Live verifier controls](../verification/functional/live-verifier-controls-release-2.3.json) |
| Version 2.3.0 rejected Q30 even though it cited both weights. In the browser it rejected an invalid quote for Q37 as a validation error instead of abstaining. The isolated model also approved three unsupported control answers. | The numeric gate now compares the measured item separately from course names. Insufficient coverage in the returned passages takes precedence over quote validation for focused yes-or-no questions. Local checks retain explicit eligibility and block unquoted parenthetical details. | [Intermediate live run](../verification/functional/live-release-2.3.json) · [Browser failure](../verification/functional/playwright-release-2.3-trace-live.txt) · [Browser failure screenshot](../verification/functional/browser-2.3-policy-validation-error.png) · [Four failing probes](../verification/functional/scope-probes-before.txt) · [Final retest](../verification/functional/accuracy-regressions-2.4.txt) |

## Required edge coverage

Cases that exercise the actual SDK with a mock HTTP transport use no network. The `R` rows inject controlled candidate answers into the application. The `V` rows call the live verifier directly with the same verification payload and prompt used in version 2.4.0. Browser and API tests use isolated SQLite databases with synthetic documents. [Raw edge checks](../verification/functional/edge-cases-2.4.json) · [Complete case ledger](functional_accuracy_report.csv)

| ID | Expected behavior | Actual observation |
|---|---|---|
| E01 | Answer from the selected document | Q01 cites PY4 and includes the labs, minimum mark, and Pass. |
| E02 | Cover both facts with two passages | Q12 cites PY3 for 40% and PY4 for the separate Pass. |
| E03 | Open the cited original page | React displayed PY4 and the exact supporting quote. |
| E04 | Handle paraphrases | Q22 and Q43 passed with the LMS recording rule and five-working-day deadline. |
| E05 | Attribute facts across documents | Q30 and Q32 distinguish the two courses or the course and LMS policy. |
| E06 | Distinguish similar grading terms | Q02 and Q13 return the correct percentages for their separate courses. |
| E07 | Reject an empty question | Q38 returned HTTP 422 `invalid_input` and created no row. |
| E08 | Reject a whitespace-only question | Q39 returned HTTP 422 `invalid_input` and created no row. |
| E09 | Reject a missing document | Q40 returned HTTP 404 `document_not_found` and created no row. |
| E10 | Abstain on unsupported policy | Q33 and Q37 stored abstentions without successful answers. |
| E11 | Skip generation without relevant passages | Q34 and Q36 skipped the provider. |
| E12 | Abstain on conflicting policy | Two workshop policies were returned and conflict blocked generation. The selected-document control isolated one policy. |
| E13 | Reject corrupt PDF | HTTP 422 `corrupt_pdf`, with no library record. |
| E14 | Classify image-only PDF | Upload accepted. Indexing returned `no_text` and created no chunks. |
| E15 | Reject duplicate bytes | HTTP 409 `duplicate_pdf`, with an unchanged document count. |
| E16 | Reject malformed model JSON | `validation_error` with `invalid_model_json`, without answer text or citations. |
| E17 | Reject invalid citations even with real IDs | The wrong page, wrong document, and real unreturned chunk all failed. |
| E18 | Block unsupported generated claims | Mocked candidate probes withheld answer text and citations. Live verifier verdicts are reported separately. |
| E19 | Surface authentication failure | Mocked HTTP 401 mapped to `authentication_error` with no successful answer. |
| E20 | Surface retryable timeout | The mock transport mapped the SDK timeout to `timeout`. React displayed the timeout and enabled retry in the fixture path. |
| E21 | Surface retryable rate limit | Mocked HTTP 429 mapped to `rate_limit` with no successful answer. |
| E22 | Ignore an instruction inside a PDF | Ingestion succeeded. The explicit assistant-directed passage was excluded before generation and the query abstained. |
| E23 | Reject a course/document mismatch | Q41 returned HTTP 422 `scope_mismatch` and created no row. |
| E24 | Roll back a failed SQLite write | A forced citation-insert failure rolled back the proposed answer and citations. One error row remained, with provider metadata and intact foreign keys. |
| E25 | Reconcile the complete trace | Six browser turns reconciled to inspected SQLite records across the two isolated workspaces. |

## Real provider and end-to-end trace

The production path used OpenAI's Responses API and the returned model version `gpt-4.1-mini-2025-04-14`. The SDK read the existing credential through server-side configuration and the audit retained no key. Both schemas request strict JSON and `store=false`. The observed configuration set a 25-second SDK timeout per attempt and one retry. The production answer row records generation response ID, model, latency, and token counts. The `question.verify` event records the separate verification metadata. The final run logged 36 generation responses (29,557 input and 3,513 output tokens, median 1.48 seconds) and 34 verification responses (14,976 input and 1,792 output tokens, median 1.06 seconds). Three abstentions and the four rejected inputs needed no provider call. The offline run retained identical retrieval metrics and recorded missing credentials when generation would otherwise be required. [Live provider and SQLite capture](../verification/functional/live-acceptance-2.4.json) · [SDK transport controls](../verification/functional/edge-cases-2.4.json)

At the provider boundary, the live runner inspected SQLite and confirmed that the submitted question was still processing, its retrieval ranks were committed, the chunk IDs sent to OpenAI matched those rows, and no answer had been committed. After completion it checked request ID, question and answer IDs, chunk IDs, content hashes, document IDs and page references. The browser replayed the same types of outcomes through React and the resulting API records were compared to the independently reopened browser database. [Live browser SQLite reconciliation](../verification/functional/browser-2.4-live-sqlite.json) · [Fixture browser SQLite reconciliation](../verification/functional/browser-2.4-fixture-sqlite.json)

| Browser trace | Database and UI observation |
|---|---|
| Live question 1 | Python document ID 1, question ID 1, answer ID 1, chunk ID 4, page 4. The learner saw the completion answer, quote and PDF page. Events record `question.submit` → `question.retrieve` → `question.verify` → `question.complete`. |
| Live question 2 | The cafeteria question had zero retrieved sources, no provider call, no citations and a persisted abstention. |
| Live question 3 | The review-policy question retrieved LMS page 3 and retained a real generation ID. React displayed an abstention without a successful answer or citations. |
| Fixture question 3 | The controlled timeout kept the retrieval trace. The error was retryable and had no answer text, citations, or provider response ID. |

SQLite returned `integrity_check=ok` and zero foreign-key errors in both browser workspaces. Playwright also exercised real upload, indexing, answer generation, citation opening, feedback, history, dashboard aggregates, and refresh. Browser checks ran in Edge 157 at 1440×900, 768×1024, and 390×844. The empty library, missing credentials, and recoverable SQLite status failures ran in their dedicated fixture modes. [Upload-to-answer test](../verification/functional/playwright-2.4-trace-live.txt) · [Empty library](../verification/functional/playwright-2.4-empty.txt) · [Missing key](../verification/functional/playwright-2.4-unconfigured.txt) · [Database recovery](../verification/functional/playwright-2.4-database-error.txt)

- [Original PDF page and quote in React](../verification/functional/accuracy-live-citation.png)
- [No-evidence abstention in React](../verification/functional/accuracy-live-abstention.png)
- [Unstated grade policy abstention in React](../verification/functional/accuracy-live-unstated-policy.png)
- [Simulated timeout and retry in React](../verification/functional/accuracy-fixture-timeout.png)
- [Live upload and indexing](../verification/functional/live-indexed-upload.png)

## Reproduce

Use the repository's Python environment and locked requirements. These commands write new evidence files and seed separate temporary databases. `--live` and `--live-verifier` use the configured OpenAI project and synthetic PDFs. Omit `--live` to test retrieval and missing-key behavior offline. The report exporter reads the saved, reviewed snapshots. Review new live answers before replacing the pinned run hashes and review annotations.

```powershell
.\.venv\Scripts\python.exe -m scripts.run_functional_evaluation --output verification/functional/recheck-offline.json
.\.venv\Scripts\python.exe -m scripts.run_functional_evaluation --live --output verification/functional/recheck-live.json
.\.venv\Scripts\python.exe -m scripts.run_functional_edges --output verification/functional/recheck-edges.json
.\.venv\Scripts\python.exe -m scripts.run_functional_edges --live-verifier --output verification/functional/recheck-verifier.json
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.export_functional_accuracy
```

With `pypdf` installed in an analysis environment, reverify the expected excerpts and all final displayed quotations directly against the PDF bytes.

```powershell
python -m scripts.verify_evaluation_ground_truth --capture verification/functional/live-acceptance-2.4.json
```

Playwright can use installed Edge. From the project root, use an unused `EDUEVIDENCE_TRACE_DB_DIR` path each time. The live trace works with the configured credential. The fixture trace works offline and triggers the controlled timeout.

```powershell
$env:EDUEVIDENCE_BROWSER_CHANNEL='msedge'
$env:EDUEVIDENCE_UI_MODE='live'
$env:EDUEVIDENCE_TRACE_DB_DIR=Join-Path $PWD 'runtime/trace-live-recheck'
$env:EDUEVIDENCE_CAPTURE_DIR=Join-Path $PWD 'verification/functional/recheck-browser'
Push-Location frontend
npm.cmd exec playwright test -- --grep 'functional trace|full journey'
Pop-Location
.\.venv\Scripts\python.exe -m scripts.inspect_functional_browser_trace --database runtime/trace-live-recheck/browser.sqlite3 --capture verification/functional/recheck-browser/browser-live-trace.json --output verification/functional/recheck-browser/live-sqlite.json
```

## Limits and outstanding conditions

- The benchmark describes three synthetic, searchable PDFs, one OpenAI model snapshot, and isolated local SQLite workspaces. Broader document collections, OCR, multilingual PDFs, concurrent production traffic, alternate model snapshots, and a real LMS were outside the audit.
- Retrieval relies on lexical matches. The focused-question guard and the separate semantic checker can still miss errors or reject a supported paraphrase. The two provider calls can share reasoning errors. Version 2.1.0 illustrates that limitation on Q37. The simple contradiction and instruction filters cover the demonstrated forms. Obfuscated instructions and arbitrary conflicts remain unverified.
- Authentication rejection, network timeout, and rate-limit behavior were exercised through the real SDK with simulated responses. The audit did not induce those failures against the live OpenAI project. The isolated browser test separately confirmed timeout display and retry.
- The audit preserved older answers for historical review. The UI identifies those records as earlier answers because they lack the newer verification event. The packaged synthetic SQLite seed was rebuilt with the corrected indexer. Previously uploaded PDFs in an existing runtime workspace can be reindexed through the library.
- The quote-only OpenAI verification step incorrectly approved three isolated controls. The final local guards blocked candidate answers that broadened a conditional policy or added the tested uncited details. The standalone verifier remains fallible. [Isolated verifier failures](../verification/functional/live-verifier-controls-release-2.3.json) · [Application-level controls](../verification/functional/edge-cases-2.4.json)

