# EduEvidence AI UI testing report

Project 022 · November 18, 2026

This report preserves the UI refresh test run. The [final readiness report](final_readiness_report.md) records the final browser checks and evidence.

## Environment and result

Microsoft Edge 157.0.4341.60 on Windows, Playwright 1.65.1, and axe-core for WCAG 2.0 and 2.1 A/AA rules that can be checked automatically. The application ran through Vite and FastAPI using disposable SQLite workspaces. The desktop live journey used the configured OpenAI provider and a synthetic course PDF.

**Result:** 16 Playwright tests passed in the fixture run. The same full journey passed with live OpenAI, and the separate empty-library, missing-credentials, and SQLite-error runs each passed. The production build passed. All 67 backend regression tests passed.

## Tested screens and viewports

| Screen | Actions and expected result | Actual result | Status |
|---|---|---|---|
| Overview | Open the workspace, inspect indexed documents and question metrics, then refresh | The live run showed the counts returned by SQLite before and after refresh. The chart and cards fit all tested widths. [Desktop screenshot](../verification/ui/desktop-overview.png) · [Mobile screenshot](../verification/ui/mobile-overview.png) | Pass |
| Document Library | Search and filter, navigate away and back, open a document, turn PDF pages, reindex, and confirm removal | Search and filter values survived navigation. PDF pages 1 and 2 rendered, Escape restored focus, and the uploaded variant reindexed and retired through FastAPI. [Desktop screenshot](../verification/ui/desktop-library.png) · [Tablet screenshot](../verification/ui/tablet-library.png) · [Mobile screenshot](../verification/ui/mobile-library.png) | Pass |
| Knowledge Assistant | Select course and document, submit with the keyboard, open a source, copy the answer, rate it, and reopen the thread | The response used the selected document. Scope, draft and conversation resumed across navigation. Copy included the PDF citation, and feedback persisted after refresh. [Desktop screenshot](../verification/ui/desktop-assistant.png) · [Live answer](../verification/ui/live-grounded-answer.png) · [Mobile screenshot](../verification/ui/mobile-assistant.png) | Pass |
| Question History | Find a stored question, open its trace, and filter by outcome | The saved answer, citation, and Helpful rating appeared in the trace. The unsupported question appeared under Abstained. [Desktop screenshot](../verification/ui/desktop-history.png) | Pass |
| Feedback & Analytics | Open analytics and compare outcomes and ratings with the persisted journey | The page loaded results and rating counts from the analytics endpoint. The live trace and overview reconciliation confirmed the database changes. [Desktop screenshot](../verification/ui/desktop-analytics.png) | Pass |
| Audit Logs | Follow a question trace to its request ID | The request filter showed the three matching events from the database. [Desktop screenshot](../verification/ui/desktop-audit.png) | Pass |
| System Health | Load backend settings and recover from a temporary SQLite failure | The first status request returned HTTP 503. The UI displayed the database message and request ID. Retry restored the SQLite connection and configuration fields. [Desktop screenshot](../verification/ui/desktop-settings.png) · [Error screenshot](../verification/ui/database-error.png) | Pass |

All seven routes passed at **1440 × 900 desktop**, **768 × 1024 tablet**, and **390 × 844 mobile**. Each viewport run checked route navigation, document and table width, JavaScript errors, and the selected axe rules, including detectable text contrast and accessible-name issues. Keyboard checks covered the skip link, visible focus outline, drawer tab order, Escape, focus restoration, and the question shortcut. The citation dialog also passed an axe scan with its retrieved passage expanded. [Tablet assistant](../verification/ui/tablet-assistant.png) · [Mobile navigation](../verification/ui/mobile-navigation.png)

## Live PDF-to-answer journey

| Actions | Expected result | Actual result | Status |
|---|---|---|---|
| Launch the app, open Document Library, and upload a PDF under Python Programming | The upload succeeds, then the document becomes available for questions | FastAPI returned HTTP 202. The browser showed upload success, Indexed, and the real page 1 preview. [Indexed upload](../verification/ui/live-indexed-upload.png) | Pass |
| Open Knowledge Assistant, select the uploaded handbook, and ask for its completion requirements | The answer states four graded labs, at least 70% overall, and a capstone Pass | OpenAI model `gpt-4.1-mini-2025-04-14` returned all three criteria. The answer passed the existing grounding checks. [Live answer](../verification/ui/live-grounded-answer.png) | Pass |
| Open the citation, inspect the quote, and expand the passage | The uploaded PDF opens on page 4 and the supporting passage matches | The citation referenced the uploaded document ID, page 4 and chunk 4. The PNG endpoint returned the corresponding page, and the excerpt showed the grading conditions. [Live source evidence](../verification/ui/live-source-evidence.png) | Pass |
| Submit Helpful feedback, check Question History and Overview, then refresh and revisit History | The answer, citation, rating, and database metrics persist | Indexed documents increased from 3 to 4, verified answers from 0 to 1, and Helpful ratings from 0 to 1. The same question, citation, and rating were present after refresh. [Persisted API evidence](../verification/ui/live-journey.json) | Pass |

## Failure states and edge cases

| Actions | Expected result | Actual result | Status |
|---|---|---|---|
| Delay the library response, then open an empty workspace | Show loading first and provide a usable upload action for an empty library | Loading stayed visible while the request was held. The first-upload action opened the form. [Empty library](../verification/ui/empty-library.png) | Pass |
| Delay upload and metadata responses, then upload a PDF without extractable text | Show uploading, acceptance and indexing, then explain why indexing failed | The upload sent one request, could not be closed while pending, and advanced through acceptance and Indexing. The final alert matched the backend message. [Uploading](../verification/ui/upload-in-progress.png) · [Indexing failure](../verification/ui/indexing-failed.png) | Pass |
| Upload invalid, corrupt and duplicate files | Reject each upload with the relevant backend message | The signature, unreadable PDF, and duplicate notices appeared for their corresponding files. | Pass |
| Submit whitespace and repeat the shortcut during a delayed ask | Block the empty submission and send the valid question once | Whitespace sent no request. Repeated submission during the valid request sent one POST. The UI showed generation after the backend had persisted retrieved passages. | Pass |
| Ask a cafeteria question outside the source material | Abstain and omit citations | The insufficient-evidence message appeared and the saved question was filterable under Abstained. | Pass |
| Trigger a provider timeout, then use Retry question | Show the backend failure and retry within the original scope | The labeled fixture produced an API timeout. Retry returned the expected page 4 citation, and the earlier failure remained visible in the conversation. | Pass |
| Run with missing OpenAI credentials | Explain the missing key in the assistant and System Health | The configuration and persisted question outcome reported missing credentials. [Missing credentials](../verification/ui/missing-credentials.png) | Pass |
| Exercise Markdown and mobile stress content | Render permitted formatting, keep untrusted content inert, and fit long content and citations | A three-item list survived refresh. The renderer removed active HTML, image and link elements in an answer-text-only test. A separate mobile answer over 2,000 characters used five backend-validated citations. The full long filename was available in a disclosure. [Long filename and citation](../verification/ui/mobile-long-filename-citation.png) | Pass |

## Visual review and remaining coverage

Reviewed the desktop screenshots for all seven screens and the tablet and mobile screenshots for Overview, Document Library, and Knowledge Assistant. The review checked text hierarchy, spacing, table readability, dialog layout, and navigation consistency. The first automated pass found visible-label and accessible-name mismatches in the brand link and library action. The final run passed after those names were corrected. The visual review also led to a balanced two-line dashboard headline and a disclosure for long source names.

Manual screen-reader sessions, Firefox, Safari, and physical touch devices remain outside this run. The current OpenAI prompt prefers plain prose. The Markdown case used grounded fixture text through the same answer persistence and browser rendering path.

## Execution evidence

- [Fixture Playwright run](../verification/ui/fixture-playwright.txt) · [Live Playwright run](../verification/ui/live-playwright.txt) · [Production build](../verification/ui/build.txt) · [Backend regression run](../verification/ui/pytest.txt)
- [Empty workspace run](../verification/ui/empty-playwright.txt) · [Missing credentials run](../verification/ui/credentials-playwright.txt) · [SQLite error run](../verification/ui/database-error-playwright.txt)

From the frontend folder, run `npm.cmd run test:e2e` for the fixture checks. Set `EDUEVIDENCE_BROWSER_CHANNEL=msedge` to use installed Edge. The live run uses `EDUEVIDENCE_UI_MODE=live` with `npm.cmd run test:e2e -- --grep "full journey"` and the backend's configured OpenAI key.

