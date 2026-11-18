import argparse
import json
from pathlib import Path

from backend.app.core.config import Settings
from backend.app.db.database import Database
from backend.app.services.questions import QuestionService


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read a stored question trace and its audit events.")
    parser.add_argument("question_id", type=int)
    parser.add_argument("--db", type=Path)
    args = parser.parse_args()
    db = Database(args.db or Settings.from_environment().database_path)
    if not db.path.is_file():
        raise SystemExit("Database does not exist. Start the API or run the seed command first.")
    questions = QuestionService(db, None, None, None)
    trace = questions.get(args.question_id)
    events = db.all("SELECT * FROM audit_events WHERE request_id=? OR question_id=? ORDER BY id",
                    (trace["request_id"], args.question_id))
    print(json.dumps({"trace": trace, "audit": events}, indent=2, ensure_ascii=False))

