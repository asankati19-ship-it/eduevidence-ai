# Evaluator demo

Run from the project root in PowerShell after the [Windows setup](../README.md). Use the bundled synthetic PDFs. The live and simulated scenarios each use a fresh workspace. Their evidence is labeled in the [final readiness report](final_readiness_report.md).

## A. Live answer, real PDF citation, and stored evidence

1. In the backend terminal, set a fresh demo path and seed it. The backend reads your configured OpenAI API key.

   ```powershell
   $env:DATABASE_PATH = 'runtime/evaluator-live/workspace.sqlite3'
   $env:UPLOAD_DIRECTORY = 'runtime/evaluator-live/uploads'
   .\.venv\Scripts\python.exe -m scripts.seed_data
   .\.venv\Scripts\python.exe -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-access-log
   ```

2. In another terminal, start `npm.cmd --prefix frontend run dev`. Open [Overview](http://127.0.0.1:5173). A fresh seeded workspace shows three indexed PDFs and ten chunks.
3. Prepare an upload variant of the bundled handbook. The trailing PDF comment changes its checksum while leaving page content intact. Run this once from the project root in a third terminal.

   ```powershell
   .\.venv\Scripts\python.exe -c "from pathlib import Path; source=Path('data/sample_documents/Python Programming Course Handbook.pdf'); target=Path('runtime/evaluator-live/full-journey-course-handbook.pdf'); target.write_bytes(source.read_bytes() + b'\n% Original sample used for the full UI journey\n')"
   ```

4. Open **Document Library** and select **Upload PDF**. Choose **Python Programming**, set **Display title** to `Full Journey Python Handbook`, attach the variant from `runtime/evaluator-live/`, and select **Upload and index**. Wait for **Indexed**, confirm the page preview appears, and close the dialog.
5. Open **Knowledge Assistant**. Set **Course** to **Python Programming** and **Document** to **Full Journey Python Handbook**. Send “For this uploaded Python Programming handbook, what are the course completion requirements?” The answer must include all four graded labs, at least 70% overall, and a Pass on the capstone.
6. Open the **Full Journey Python Handbook Page 4** citation. Check the title, filename, page number, chunk, exact supporting quote, and rendered original page. Expand **Read full retrieved passage**, then press Escape to return to the citation control.
7. Select **Helpful** and open **Question History**. Open the question trace and confirm the saved rating, provider metadata, retrieval ranks, and request ID. Select **View correlated audit events** to open the filtered record. Return to **Overview** and refresh. The indexed document, verified answer, and Helpful totals each increased by one.
8. Read the question ID from the `question` parameter in the History trace URL or the **Question** link in the audit record. Inspect its SQLite record. Replace `1` if your question uses a different ID.

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.inspect_trace 1 --db runtime/evaluator-live/workspace.sqlite3
   ```

   The trace must show `answered`, a real OpenAI response ID, retrieved chunk IDs, a supported verification event, and a citation for the uploaded handbook on page 4.

## B. Insufficient evidence

1. Keep the same course and handbook selected. Send “What is the cafeteria menu on Tuesday?”
2. Confirm **Abstained** appears with the insufficient-evidence explanation and no citation controls.
3. Open **Question History**, filter by **Abstained**, and open this turn. Confirm the saved outcome, empty answer and citations, and absence of a provider response ID. The retrieval threshold stops this question before generation.

## C. Simulated API timeout and recovery

1. Open fresh terminals for this isolated fixture. Start the test backend and a separate frontend on the following ports.

   ```powershell
   $env:EDUEVIDENCE_TRACE_DB_DIR = 'runtime/evaluator-timeout'
   .\.venv\Scripts\python.exe -m backend.tests.browser_backend --mode fixture --port 8018
   ```

   ```powershell
   $env:EDUEVIDENCE_API_ORIGIN = 'http://127.0.0.1:8018'
   npm.cmd --prefix frontend run dev -- --port 5183
   ```

2. On the [fixture frontend](http://127.0.0.1:5183), open **Knowledge Assistant** and select **Python Programming** and **Python Programming Course Handbook**. Send the exact fixture question “What are the Python Programming course completion requirements for learners in the handbook?”
3. The first request displays **API timeout** with **Retry question**. It stores a `provider_error` outcome with code `timeout`, no provider response ID, no answer body, and no citations.
4. Select **Retry question**. The fixture resolves the new attempt and displays the page 4 citation. In **Question History** verify the separate failed and answered entries. To inspect either attempt directly, run `.\.venv\Scripts\python.exe -m scripts.inspect_trace 1 --db runtime/evaluator-timeout/browser.sqlite3`, then repeat with question ID `2` in a fresh fixture workspace.

This scenario uses the labeled `offline_fixture` provider. For the repeatable live command-line checks, run `.\.venv\Scripts\python.exe -m scripts.run_e2e_demo --isolated --full --output runtime/live-demo.json`.
