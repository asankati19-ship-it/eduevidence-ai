# Execution evidence

- `pytest.txt`, `playwright.txt`, and `frontend-build.txt` record the automated runs.
- `live-openai.json` records the first successful real API smoke check and a retrieval-only abstention.
- `live-acceptance.json` and `live-acceptance.txt` preserve the full live run and its original exact-phrase mismatch. The `live-acceptance-reviewed` files show the corrected content check on the same responses.
- `live-browser.json`, `live-browser.txt`, and the `*-live.png` screenshots document the real browser-to-OpenAI workflow.
- `sqlite-trace.json` and `sqlite-integrity.txt` record database inspection and referential integrity.
- The remaining screenshots show offline browser journeys. Assistant and citation screenshots display the offline fixture label.

The captured questions, responses and document passages refer to the bundled synthetic corpus. Internal Windows workspace paths in command logs have been redacted.

