"""Reconcile a captured browser run with the same SQLite database written by FastAPI."""

import argparse
from contextlib import closing
from pathlib import Path
import sqlite3

from scripts.run_functional_evaluation import check_trace, inspect_sqlite, read_json, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, required=True)
    parser.add_argument("--capture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    assert args.database.is_file()
    observed = read_json(args.capture)
    path = args.database.resolve()
    rows = []
    for trace in observed["cases"]:
        stored = inspect_sqlite(path, trace["id"])
        check_trace(trace, stored, None)
        rows.append({"browser_trace": trace, "sqlite_trace": stored, "passed": True})
        print(f"{observed['mode']}: question {trace['id']}, {trace['status']}, SQLite relationship checks passed")
    with closing(sqlite3.connect(path.as_uri() + "?mode=ro", uri=True)) as con:
        integrity = con.execute("PRAGMA integrity_check").fetchone()[0]
        fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
    assert integrity == "ok" and not fk_errors
    write_json(args.output, {"mode": observed["mode"], "integrity": integrity, "foreign_key_errors": fk_errors, "cases": rows})


if __name__ == "__main__":
    main()

