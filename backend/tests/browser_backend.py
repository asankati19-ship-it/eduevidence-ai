"""Start an isolated workspace for browser verification."""

import argparse
from contextlib import ExitStack
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

import uvicorn

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.tests.fixtures import FixtureProvider
from scripts.seed_data import seed


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8018)
    parser.add_argument("--mode", choices=("fixture", "live", "unconfigured", "empty", "database-error"), default="fixture")
    args = parser.parse_args()
    with ExitStack() as resources:
        evidence_path = os.getenv("EDUEVIDENCE_TRACE_DB_DIR")
        if evidence_path:
            path = Path(evidence_path).resolve()
            path.mkdir(parents=True, exist_ok=True)
            if (path / "browser.sqlite3").exists():
                raise SystemExit("Use a fresh directory to capture a browser trace database.")
        else:
            path = Path(resources.enter_context(TemporaryDirectory()))
        if args.mode == "live":
            settings = Settings.from_environment().model_copy(update={
                "database_path": path / "browser.sqlite3", "upload_directory": path / "uploads",
            })
            if not settings.openai_api_key.get_secret_value().strip():
                raise SystemExit("The live browser check requires an OpenAI API key.")
        else:
            settings = Settings(database_path=path / "browser.sqlite3", upload_directory=path / "uploads")
        if args.mode != "empty":
            seed(settings, verbose=False)
        provider = None if args.mode in ("live", "unconfigured") else FixtureProvider()
        app = create_app(settings, provider)
        if args.mode == "database-error":
            lookup = app.state.db.one
            fail_next_status = True

            def read_with_one_failure(sql, params=()):
                global fail_next_status
                if fail_next_status and sql == "PRAGMA user_version":
                    fail_next_status = False
                    raise sqlite3.OperationalError("Simulated database outage in isolated browser test")
                return lookup(sql, params)

            app.state.db.one = read_with_one_failure
        uvicorn.run(app, host="127.0.0.1", port=args.port, access_log=False)

