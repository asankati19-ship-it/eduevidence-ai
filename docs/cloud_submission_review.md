# Project 022 submission decision

**FAIL for final submission.** Evaluated on November 19, 2026 against application commit `1ef04f9e165aa94e95e762e774caad51dde9db79`. The deployed app indexed the test PDF and retrieved sufficient evidence. The hosted generation step failed because the deployment had no OpenAI credential. A separate unit-notation fidelity issue in this revision also needs correction.

[Hosted application](https://appapppy-dvhx9tgh8xq6jfj7ctdaev.streamlit.app/)

| Check | Decision | Observable result |
|---|---|---|
| Overview and seven workspace pages | PASS | Opened Overview, Library, Assistant, History, Analytics, Audit Logs and System Health in a live browser. |
| UI review and deployment | PASS | Compared hosted Streamlit with the React AnswerCard implementation and archived React assistant screenshot. React groups answer status, source evidence and feedback around a chat card and keeps search scope beside it. Streamlit now groups course and document selection side by side, shows chronological messages, labeled answer status, contextual errors, saved feedback and expandable provider details. Metric cards and a primary Ask action clarify navigation. A Cloud import failure during hot reload was corrected with explicit Python packages. |
| Synthetic upload and indexing | PASS | Uploaded Juniper-Lab.pdf through the live file chooser. The library increased from three to four documents and showed two pages and two indexed chunks. |
| Known question | FAIL | Asked “What is the Juniper calibration interval?” The expected answer is 17 days on page 2. History recorded provider_error and the audit table recorded sufficient retrieval. No answer body appeared. |
| Live OpenAI response | NOT VERIFIED | The app selected openai and gpt-4.1-mini. Its actual outcome was skipped, error missing_credentials, response ID null. A separate local SDK attempt with configured credentials ended in network_error without a response ID. |
| Citation from a live answer | NOT VERIFIED | Opened original page 2 from Document Library. An answer citation requires a successful verified response. The Streamlit fixture test separately exercised a verified citation and page preview. |
| Helpful feedback on the live answer | NOT VERIFIED | No verified answer was available to rate. Analytics showed zero helpful and zero not-helpful ratings. Backend tests exercised feedback persistence. |
| History and audit | PASS | History showed two questions. The known question had three matching events: accepted submission, sufficient retrieval, provider error. |
| Unsupported question | PASS | “What is the cafeteria menu on Tuesday?” returned Abstained and a message explaining that the selected documents lacked matching evidence. |
| SQLite session behavior | PASS | Original tab retained four documents and two questions across navigation. A fresh simultaneous tab started with three seeded documents and zero questions. Each Workspace creates a SQLite file and upload folder in a TemporaryDirectory. A new session or server restart can lose uploads, history, feedback and audit records. Save evidence before closing. |
| Backend tests | PASS | 96 passed, one Starlette dependency deprecation warning. Executed the repository's backend suite using the deployed backend sources. The earlier 97-test result included a local-only superscript regression. |
| Streamlit AppTest | PASS | Real SQLite and PDFs with a fixture provider. Verified navigation, rendered answer, citation chip, PDF preview, reindex, retirement, retained historical citation and audit labels. |
| Scientific text fidelity | FAIL | Reproduced against the GitHub backend revision: chunking “25 m²” produced “25 m2”. The earlier local fix has not been deployed. This review changed presentation and import packaging only. |

## Evidence and release conditions

The separately supplied evaluator evidence contains original browser captures, the two-page PDF, live provider details, filtered audit rows, concurrent-session observations, backend and AppTest logs, and the local SDK attempt. Historical React and live-provider results describe their own revisions. This run did not establish production-grade persistence, a complete new model benchmark, or security certification.

To clear the hosted demonstration, configure the deployment owner's OpenAI key in Streamlit Cloud Secrets, restart the app, upload the synthetic PDF in a fresh session, then verify the 17-day answer, its page-2 citation, provider response ID, Helpful rating, history and audit events in the same session. Separately port and rerun the existing superscript regression before certifying technical course material.
