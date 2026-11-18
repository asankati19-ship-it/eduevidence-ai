from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QuestionInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    question: str = Field(min_length=3, max_length=1200)
    course_id: int | None = Field(None, gt=0)
    document_id: int | None = Field(None, gt=0)
    conversation_id: UUID | None = None

    @field_validator("question")
    @classmethod
    def has_letters_or_digits(cls, value):
        if not any(char.isalnum() for char in value):
            raise ValueError("Enter a question with letters or numbers.")
        return value


class FeedbackInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")
    rating: Literal["helpful", "not_helpful"]
    comment: str | None = Field(None, max_length=600)


class ModelCitation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    chunk_id: int
    document_id: int
    page_number: int
    evidence_quote: str


class ModelAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["answered", "abstained"]
    answer: str | None
    citations: list[ModelCitation]
    abstention_reason: str | None


class ModelVerification(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    outcome: Literal["supported", "unsupported", "conflict"]
    reason: str


class CourseOut(BaseModel):
    id: int
    code: str
    title: str


class DocumentOut(BaseModel):
    id: int
    course_id: int
    course_code: str
    course_title: str
    title: str
    original_filename: str
    sha256: str
    size_bytes: int
    page_count: int
    text_pages: int | None
    status: Literal["processing", "indexed", "error", "retired"]
    active_revision: int
    chunk_count: int
    error_code: str | None
    error_message: str | None
    created_at: str
    updated_at: str


class SourceOut(BaseModel):
    chunk_id: int
    document_id: int
    document_title: str
    original_filename: str
    page_number: int
    chunk_number: int
    revision: int
    content: str
    score: float
    rank: int


class CitationOut(SourceOut):
    evidence_quote: str
    position: int


class AnswerOut(BaseModel):
    id: int
    status: str
    body: str | None
    reason: str | None
    provider: str
    model: str | None
    prompt_version: str
    api_outcome: str
    error_code: str | None
    retryable: bool
    verification_passed: bool
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int | None
    provider_response_id: str | None
    rating: Literal["helpful", "not_helpful"] | None


class QuestionOut(BaseModel):
    id: int
    question_text: str
    course_id: int | None
    document_id: int | None
    document_title: str | None
    conversation_id: str | None
    status: str
    request_id: str
    created_at: str
    completed_at: str | None
    answer: AnswerOut | None
    sources: list[SourceOut]
    citations: list[CitationOut]


class PageOut[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class AuditOut(BaseModel):
    id: int
    event_type: str
    outcome: str
    detail: str | None
    request_id: str
    question_id: int | None
    document_id: int | None
    created_at: str

