from typing import Protocol

from backend.app.db.database import Database


class LMSConnector(Protocol):
    def courses(self) -> list[dict]: ...
    def learner(self) -> dict: ...


class LocalLMSConnector:
    """Expose only synthetic LMS identities and course metadata."""

    def __init__(self, database: Database):
        self.database = database

    def courses(self) -> list[dict]:
        return self.database.all("SELECT id,code,title FROM courses ORDER BY id")

    def learner(self) -> dict:
        return self.database.one("SELECT id,display_name FROM learners WHERE id=1")

