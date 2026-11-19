# Testing report

**Current release decision — FAIL.** See the [November 19 hosted submission review](cloud_submission_review.md) for application revision `1ef04f9`, live browser outcomes, and test logs. The results below are archived from the earlier evaluation.


This report preserves the original implementation test run. The [final readiness report](final_readiness_report.md) records the final acceptance results.

**Run date:** November 18, 2026  
**Environment:** Windows, Python 3.12.10, Node.js 26.13.0, Microsoft Edge via Playwright

| Verification | Observed result | Evidence |
|---|---|---|
| Pytest | 67 passed | [Pytest output](../verification/pytest.txt) |
| TypeScript and Vite production build | Exit 0 | [Build output](../verification/frontend-build.txt) |
| Playwright | 7 passed using the labeled offline fixture | [Browser test output](../verification/playwright.txt) |
| Live OpenAI acceptance | Six answered with the expected citation pages. Two abstained before generation. All eight passed on the rescored captured output. | [Raw result](../verification/live-acceptance.json) · [Rescored result](../verification/live-acceptance-reviewed.json) |
| Live browser | Real OpenAI answer, page 4 shown, feedback and three request events persisted | [Browser trace](../verification/live-browser.json) · [Edge output](../verification/live-browser.txt) |
| SQLite | Integrity checks passed and foreign-key checks returned zero violations for the sample and demonstration runtime | [Integrity output](../verification/sqlite-integrity.txt) |

The offline suite checks file validation, actual text extraction, searchable and image-only PDF behavior, checksums, page and chunk identity, reindexing, retirement, request limits, course and document scope, ambiguity, vocabulary mismatch, evidence support, SDK error translation, feedback, audit records and SQLite rollback. Provider transport tests use deterministic fixtures. The live evidence separately records actual calls to OpenAI.

The first Windows sandbox run could not create the loopback sockets that Python's TestClient event loop uses. The suite passed with loopback access. Initial browser checks exposed ambiguous form labels and focus restoration after Escape. Both controls were corrected and rerun. The backend suite emits one upstream Starlette HTTPX deprecation warning. Paths containing the local machine profile were redacted in the copied command logs.

See the [functional accuracy report](functional_accuracy_report.md) for the late-work paraphrase check and supported claims.

