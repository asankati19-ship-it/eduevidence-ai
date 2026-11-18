from pathlib import Path

from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator
import os


ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseModel):
    model_config = ConfigDict(hide_input_in_errors=True)

    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4.1-mini"
    openai_timeout_seconds: float = Field(25, gt=0, le=120)
    openai_max_retries: int = Field(1, ge=0, le=2)
    database_path: Path = ROOT / "runtime/eduevidence.sqlite3"
    upload_directory: Path = ROOT / "runtime/uploads"
    retrieval_top_k: int = Field(5, ge=1, le=12)
    min_retrieval_score: float = Field(0.18, gt=0, le=1)
    min_query_terms: int = Field(2, ge=1, le=12)
    min_query_overlap: int = Field(1, ge=1, le=12)
    chunk_words: int = Field(135, ge=20, le=500)
    chunk_overlap: int = Field(24, ge=0, le=499)
    max_pdf_mb: int = Field(20, ge=1, le=50)
    max_pdf_pages: int = Field(120, ge=1, le=500)

    @model_validator(mode="after")
    def validate_configuration(self):
        if self.chunk_overlap >= self.chunk_words:
            raise ValueError("CHUNK_OVERLAP must be less than CHUNK_WORDS")
        for field in ("database_path", "upload_directory"):
            path = getattr(self, field)
            if not path.is_absolute():
                setattr(self, field, ROOT / path)
        return self

    @classmethod
    def from_environment(cls):
        local = dotenv_values(ROOT / ".env")
        values = {
            field: value
            for field in cls.model_fields
            if (value := os.environ.get(field.upper(), local.get(field.upper()))) is not None
        }
        return cls.model_validate(values)

