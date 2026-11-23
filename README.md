# EduEvidence AI

EduEvidence AI helps learners and instructors ask questions about course PDFs and check the supporting passage on its original page.

**First visit.** Open Overview and click **Try a free PDF example** to read the Python handbook's completion requirements directly from page 4. The preview uses the bundled PDF and works without an API key. For a generated answer, open Knowledge Assistant, select the document, and submit a question.

**What the Overview looks like.** The left sidebar links to all seven workspace pages. On smaller screens, open the sidebar with the menu control. Overview shows the product name, three short instructions, the indexed course PDFs, and activity counts for this browser session.

**Streamlit quick start (Python 3.12).** In a fresh virtual environment, run `python -m pip install -r requirements.txt` and `python -m streamlit run streamlit_app.py`. For live answers, copy `.streamlit/secrets.toml.example` to the ignored `.streamlit/secrets.toml` and set `OPENAI_API_KEY`. The React and FastAPI setup is below.

**Community Cloud.** Deploy `main` with entry point `streamlit_app.py`. Set visibility under **App settings → Sharing → Who can view this app → This app is public and searchable**. Add the provider key in **App settings → Secrets**. The single-process service can sleep between visits, has limited RAM (plan around 1 GB), and offers no availability guarantee. Each new session starts a new temporary SQLite workspace. The Streamlit limit is five live submissions per session, with up to two provider requests per submission and automatic retries disabled. New sessions receive a new allowance. Page previews, downloads and navigation do not use the paid provider.

## Windows quick start

Install 64-bit Python 3.12 and Node.js 22.12 or newer. Open this folder in VS Code and use PowerShell from the project root.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
Copy-Item .env.example .env
.\.venv\Scripts\python.exe -m scripts.seed_data
npm.cmd --prefix frontend ci
```

If the Python launcher does not list 3.12, use the full path to your Python 3.12 executable for the first command. The commands call the environment's Python directly and work without PowerShell script activation.

Add your OpenAI key to the ignored root `.env` file as `OPENAI_API_KEY`, or set it in the backend terminal's process environment. Process variables have precedence. The default model is `gpt-4.1-mini`. The library, retrieval, pre-provider abstentions, and audit functions also operate with the key blank. A supported question in that state records a missing-credentials outcome.

Start FastAPI in a dedicated terminal.

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
```

Start Vite in a second terminal.

```powershell
npm.cmd --prefix frontend run dev
```

Open [the workspace](http://127.0.0.1:5173), [the health endpoint](http://127.0.0.1:8000/health), or [the API reference](http://127.0.0.1:8000/docs). Keep both servers bound to loopback. Use one FastAPI worker. See the [API configuration guide](docs/api_configuration.md) for settings and the [demo walkthrough](docs/demo_script.md) for the evaluation sequence.

## First question

In **Knowledge Assistant**, select **Python Programming** and **Python Programming Course Handbook**. Ask:

> What are the Python Programming course completion requirements?

The expected answer includes all four graded labs, at least 70% overall, and a Pass on the capstone project. Open the citation to see the supporting text and page 4. Mark the answer Helpful and open its question trace to review the retrieval ranking and request ID.

## Streamlit Community Cloud

The Streamlit workspace uses the same backend and the bundled synthetic PDFs. See the [Streamlit run and deployment instructions](docs/streamlit_deployment.md).

## Data and verification

`scripts.seed_data` loads all three PDFs into the runtime database and can be rerun. To use the packaged SQLite file instead, run `.\.venv\Scripts\python.exe -m scripts.seed_data --restore-sample` against a **fresh** database path. This command restores the database and its matching PDF files. The supplied database has three indexed PDFs and no learner questions. In an existing workspace, use **Reindex** in the Document Library to apply paragraph-aware indexing to previously uploaded PDFs.

```powershell
.\.venv\Scripts\python.exe -m pytest -q
npm.cmd --prefix frontend run build
npm.cmd --prefix frontend exec -- playwright install chromium
npm.cmd --prefix frontend run test:e2e
.\.venv\Scripts\python.exe -m scripts.run_e2e_demo --isolated --full
```

The demo runner uses the supplied synthetic passages. Each candidate answer that passes local validation receives a separate OpenAI verification call before it can be shown as verified. The default Playwright run uses a labeled fixture provider, a real FastAPI server, a fresh SQLite database, and Vite. Set `$env:EDUEVIDENCE_BROWSER_CHANNEL='msedge'` in PowerShell to use installed Edge. See the [final readiness report](docs/final_readiness_report.md) for the latest installation and test results and the [demo walkthrough](docs/demo_script.md) for the live answer, abstention, and simulated recovery scenarios.

## Project files

| Path | Contents |
|---|---|
| `backend/app/` | FastAPI, SQLite repositories, LMS connector, ingestion, retrieval, provider and validation |
| `frontend/` | React, TypeScript, Tailwind, TanStack Query and Playwright |
| `database/schema.sql` | Versioned schema and synthetic learner and course records |
| `prompts/` | Generation and verification prompts and strict response schemas |
| `data/` | Three synthetic PDFs, sample SQLite database and expected answers |
| `scripts/` | PDF generation, seeding, functional evaluation, live acceptance, and trace inspection |
| `docs/` | Architecture, ER diagram, reports, demo, limitations and acceptance matrix |
| `verification/` | Captured test output and synthetic execution evidence |

The application is a single-operator sandbox. See [known limitations](docs/known_limitations.md) before adapting it.

