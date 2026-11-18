import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from backend.app.core.config import ROOT


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class Database:
    def __init__(self, path: Path):
        self.path = path

    @contextmanager
    def connection(self, *, write=False):
        connection = sqlite3.connect(self.path, timeout=10)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            if write:
                connection.execute("BEGIN IMMEDIATE")
            yield connection
            if write:
                connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as con:
            con.execute("PRAGMA journal_mode = WAL")
            version = con.execute("PRAGMA user_version").fetchone()[0]
            if version == 0:
                con.executescript((ROOT / "database/schema.sql").read_text(encoding="utf-8"))
            elif version != 1:
                raise RuntimeError(f"Unsupported schema version {version}")

    def all(self, sql, params=()):
        with self.connection() as con:
            return [dict(row) for row in con.execute(sql, params)]

    def one(self, sql, params=()):
        with self.connection() as con:
            row = con.execute(sql, params).fetchone()
            return dict(row) if row is not None else None


def audit(con, request_id, event, outcome, *, detail=None, question_id=None, document_id=None, learner_id=1):
    con.execute(
        """INSERT INTO audit_events
           (request_id,event_type,outcome,detail,question_id,document_id,learner_id,created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (request_id, event, outcome, detail, question_id, document_id, learner_id, utc_now()),
    )

