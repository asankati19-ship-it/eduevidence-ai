# EduEvidence AI progress

## Streamlit deployment milestone

Added a Streamlit entrypoint with seven views backed by the existing FastAPI routes. Each browser session seeds an isolated synthetic SQLite workspace. The original React app and its local lockfile remain the local distribution. Streamlit's separate runtime pins compatible dependencies, including Pillow 12.3.0. [Deployment guide](docs/streamlit_deployment.md)

The full backend suite passed 96 tests. The clean Streamlit environment passed `pip check`. Local AppTest exercised all seven views, PDF upload and reindexing, page previews, a grounded answer, retry, feedback, and an abstention. The first install attempt found Streamlit's incompatibility with Pillow 13 in the existing lock. The separate runtime resolved it. An initial smoke assertion queried the wrong Streamlit image element type. The corrected check confirmed the page 4 preview.

## Final acceptance

Classification for Project 022 is **READY FOR SUBMISSION** for the local synthetic assignment. The latest checkpoint verified clean installation, SQLite seed and restore, four PDF quotes against original pages in the live sample, eight live CLI cases, 94 backend tests, and 23 selected browser executions. The fresh retrieval run reached 100% Recall@3 on 34 answerable questions. [Final readiness report](docs/final_readiness_report.md) · [Acceptance matrix](docs/acceptance_matrix.md)

Changed `frontend/src/styles.css` and `frontend/e2e/ui-journey.spec.ts` to correct and test mid-word History badge wrapping. `backend/requirements.txt` now explicitly declares the existing Pillow dependency. `scripts/run_e2e_demo.py` describes its two-stage provider calls. Updated the README, prompt-independent handoff documents, demo walkthrough, acceptance matrix, checklist, and historical report pointers.

The original badge regression failed at 1440 pixels before the CSS change. It passed on desktop and mobile in the final fixture and live journeys. Initial clean startup browser checks failed on an overly broad metric selector and the exact-label rerun passed. The submission ZIP redacts local profile paths from historical evidence. The standalone verifier's three prior false approvals remain documented. The evaluator's workstation and provider key remain external. [Reproduced UI defect](verification/acceptance/browser/history-badge-reproduction.txt) · [Clean installation and retest](verification/acceptance/installation.md) · [Package verification](verification/acceptance/package-verification.txt)

## Evaluator handoff

Prompt and grounding version 2.4.0 is the verified baseline. The working copy and saved project archives contain no `PROJECT_SPEC.md` or `AGENTS.md`. This checkpoint uses the original Project 022 brief, the repository README, the acceptance matrix, and the submission checklist.

Keep each milestone scoped to a specific requirement or reproduced defect. Reuse the existing React, FastAPI, SQLite, and OpenAI integration. Run targeted tests after each change and the full integration suite at major checkpoints. Record failures and limitations alongside passes.

### Files changed

- `PROGRESS.md` records the verified baseline, working rules, and open items.
- `docs/acceptance_matrix.md` points to the current retrieval, provider, and browser evidence.
- `prompts/prompt_versions.md` records the grounding changes through version 2.4.0.

### Verified baseline

The prior major checkpoint passed 43 of 43 live benchmark cases, 25 of 25 required application edge cases, 94 backend tests, and 22 Playwright executions. All 38 displayed quotations were checked against their original PDF pages. The final live browser journey verified upload, indexing, a grounded answer, citation viewing, feedback, history, and persisted metrics. [Accuracy report](docs/functional_accuracy_report.md) · [Live benchmark](verification/functional/live-acceptance-2.4.json) · [Browser run](verification/functional/playwright-2.4-trace-live.txt)

This documentation checkpoint reran the 27 offline accuracy regressions. All passed. The existing Starlette test-client deprecation warning remains. The first documentation check hit a Windows text-decoding error. The UTF-8 rerun validated all three documents' links, the prompt version, and the saved audit results.

### Failed tests and open items

- The standalone model verifier incorrectly approved V01, V05, and V06. The corresponding application-level controls passed with local evidence checks. Keep those regressions when changing retrieval, citations, or prompts. [Isolated verifier results](verification/functional/live-verifier-controls-release-2.3.json)
- Full live coverage remains limited to the three synthetic PDFs and one model snapshot. Provider authentication rejection, rate limiting, and timeout were simulated. [Audit limits](docs/functional_accuracy_report.md#limits-and-outstanding-conditions)
- A fresh evaluator run still needs an extracted archive. Live answering requires an evaluator-configured API key.
