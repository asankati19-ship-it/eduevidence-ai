# Clean Windows installation and startup evidence

The review extracted the previous accuracy archive into a fresh directory. It installed the same pinned Python and Node dependencies used by the final source. The final changes affect documentation, one existing dependency declaration, a small CSS rule, and its regression assertion. The final-source build and Edge runs are separate. [Final build](frontend-build.txt) · [Final browser fixture](browser/playwright-fixture-final.txt)

| Step | Command or condition | Observed result |
|---|---|---|
| Python launcher | `py -3.12 --version` | This host's launcher had no 3.12 registration. The installed Python 3.12 executable created the fresh `.venv` using the README fallback. [Launcher output](python-launcher.txt) |
| Python dependencies | `.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt` with a fresh pip cache | All locked packages installed. `pip check` returned no broken requirements. [Install](clean-pip-install.txt) · [Dependency check](clean-pip-check.txt) |
| Frontend dependencies | `npm.cmd --prefix frontend ci` with a fresh npm cache | 178 packages installed. npm warned that an esbuild postinstall script was blocked and the production build still succeeded. [Install](clean-npm-ci.txt) · [Build](clean-frontend-build.txt) |
| Playwright | `npm.cmd --prefix frontend exec -- playwright install chromium` with a fresh browser directory | Chromium and its support dependencies downloaded. Chromium 159.0.8154.6 launched in the clean startup check. [Install](clean-playwright-install.txt) · [Browser launch](clean-startup-final.txt) |
| Configuration and corpus | Copied `.env.example` to a fresh `.env`. Ran `.\.venv\Scripts\python.exe -m scripts.seed_data` and `.\.venv\Scripts\python.exe -m scripts.seed_data --restore-sample` in separate clean paths | Three indexed PDFs, ten chunks and three restored PDFs. The rendered page 4 was a PNG. [Seed](clean-seed.txt) · [Restore](clean-restore.txt) |
| Clean runtime | `.\.venv\Scripts\python.exe -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8072 --no-access-log` and `npm.cmd --prefix frontend run dev -- --port 5262` with `EDUEVIDENCE_API_ORIGIN=http://127.0.0.1:8072` | Health and OpenAPI returned successfully. Vite proxied real API data. The known question ranked the correct page and recorded missing credentials. The unsupported question abstained. SQLite returned integrity `ok` and zero foreign-key violations. [Startup result](clean-startup-final.txt) |
| Dashboard synchronization | Load Overview in the freshly installed Chromium and compare exact card labels to the proxied API | Documents 3, Indexed chunks 10, Questions asked 2, Verified answers 0. All values matched and no page errors were captured. [Browser output](clean-startup-final.txt) · [Screenshot](clean-overview.png) |

The initial clean-run browser assertion selected two metric cards because it matched the word “Documents” anywhere in the card. The rerun used the exact metric label and a fresh SQLite database. The backend and proxy checks succeeded in both attempts. [First run](clean-startup.txt) · [Captured diagnostic](clean-startup-recheck.txt) · [Passing rerun](clean-startup-final.txt)

The clean installation intentionally used an empty provider key. Live OpenAI behavior was tested separately on the final working source. [Live demo](live-demo.json)

