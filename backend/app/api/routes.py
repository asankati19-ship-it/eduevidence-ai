from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, File, Form, Path, Query, Request, Response, UploadFile

from backend.app.core.errors import AppError
from backend.app.models.schemas import AuditOut, CourseOut, DocumentOut, FeedbackInput, PageOut, QuestionInput, QuestionOut
from backend.app.services.analytics import audit_page, overview
from backend.app.services.pdf import PDF_WORKER, render_page


router = APIRouter()
PositiveID = Annotated[int, Path(gt=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]
Search = Annotated[str | None, Query(max_length=150)]
QuestionStatus = Literal["processing", "answered", "abstained", "provider_error", "validation_error", "processing_error"]


@router.get("/health", tags=["system"])
def health(request: Request):
    request.app.state.db.one("SELECT id FROM learners LIMIT 1")
    return {"status": "ok", "database": "reachable"}


@router.get("/system/status", tags=["system"])
def system_status(request: Request):
    state = request.app.state
    settings = state.settings
    result = state.db.one("PRAGMA user_version")
    return {
        "database": {"status": "reachable", "schema_version": result["user_version"]},
        "provider": {
            "name": state.provider.name, "model": state.provider.model,
            "configured": state.provider.configured, "timeout_seconds": settings.openai_timeout_seconds,
            "max_retries": settings.openai_max_retries,
        },
        "retrieval": {
            "engine": "TF-IDF + cosine similarity", "top_k": settings.retrieval_top_k,
            "min_score": settings.min_retrieval_score, "min_query_terms": settings.min_query_terms,
            "min_query_overlap": settings.min_query_overlap,
            "chunk_words": settings.chunk_words, "chunk_overlap": settings.chunk_overlap,
        },
        "upload": {"max_mb": settings.max_pdf_mb, "max_pages": settings.max_pdf_pages},
        "learner": state.lms.learner(), "mode": "local_synthetic",
    }


@router.get("/courses", response_model=list[CourseOut], tags=["documents"])
def courses(request: Request):
    return request.app.state.lms.courses()


@router.get("/documents", response_model=PageOut[DocumentOut], tags=["documents"])
def documents(
    request: Request, course_id: Annotated[int | None, Query(gt=0)] = None,
    status: Literal["processing", "indexed", "error"] | None = None, search: Search = None,
    limit: Limit = 20, offset: Offset = 0,
):
    return request.app.state.documents.list(course_id, status, search, limit, offset)


@router.post("/documents/upload", response_model=DocumentOut, status_code=202, tags=["documents"])
def upload(
    request: Request, tasks: BackgroundTasks,
    file: Annotated[UploadFile, File()],
    course_id: Annotated[int, Form(gt=0)],
    title: Annotated[str | None, Form(max_length=180)] = None,
):
    service = request.app.state.documents
    result = service.ingest(file.filename, file.file, course_id, request.state.request_id, title)
    tasks.add_task(service.index, result["id"], request.state.request_id)
    return result


@router.get("/documents/{document_id}", response_model=DocumentOut, tags=["documents"])
def document(request: Request, document_id: PositiveID):
    return request.app.state.documents.get(document_id)


@router.get("/documents/{document_id}/pages/{page_number}", tags=["documents"],
            responses={200: {"content": {"image/png": {}}}}, response_class=Response)
def page(request: Request, document_id: PositiveID, page_number: PositiveID):
    service = request.app.state.documents
    doc = service.get(document_id)
    if page_number > doc["page_count"]:
        raise AppError(404, "page_not_found", "Page not found in this PDF.")
    storage = service.path(doc["storage_name"])
    if not storage.is_file():
        raise AppError(404, "file_unavailable", "The PDF is unavailable on disk.")
    try:
        source = storage.read_bytes()
        if sha256(source).hexdigest() != doc["sha256"]:
            raise AppError(409, "content_changed", "The stored PDF no longer matches the original upload.")
        data = PDF_WORKER.submit(render_page, source, page_number).result()
    except (RuntimeError, ValueError, OSError):
        raise AppError(422, "page_unavailable", "This page could not be rendered.") from None
    return Response(data, media_type="image/png", headers={"Cache-Control": "no-store"})


@router.post("/documents/{document_id}/reindex", response_model=DocumentOut, status_code=202, tags=["documents"])
def reindex(request: Request, document_id: PositiveID, tasks: BackgroundTasks):
    service = request.app.state.documents
    document_row = service.reindex(document_id, request.state.request_id)
    tasks.add_task(service.index, document_id, request.state.request_id)
    return document_row


@router.delete("/documents/{document_id}", status_code=204, tags=["documents"])
def retire(request: Request, document_id: PositiveID):
    request.app.state.documents.retire(document_id, request.state.request_id)
    return Response(status_code=204)


@router.post("/questions", response_model=QuestionOut, status_code=201, tags=["questions"])
def ask(request: Request, body: QuestionInput):
    return request.app.state.questions.ask(body, request.state.request_id)


@router.get("/questions/history", response_model=PageOut[QuestionOut], tags=["questions"])
def history(
    request: Request, limit: Limit = 20, offset: Offset = 0, status: QuestionStatus | None = None,
    conversation_id: UUID | None = None, search: Search = None,
):
    return request.app.state.questions.history(limit, offset, status, str(conversation_id) if conversation_id else None, search)


@router.get("/questions/{question_id}", response_model=QuestionOut, tags=["questions"])
def question(request: Request, question_id: PositiveID):
    return request.app.state.questions.get(question_id)


@router.post("/answers/{answer_id}/feedback", tags=["questions"])
def feedback(request: Request, answer_id: PositiveID, body: FeedbackInput):
    return request.app.state.questions.feedback(answer_id, body, request.state.request_id)


@router.get("/analytics/overview", tags=["analytics"])
def analytics(request: Request):
    return overview(request.app.state.db)


@router.get("/audit/events", response_model=PageOut[AuditOut], tags=["audit"])
def audit_events(
    request: Request, event_type: Annotated[str | None, Query(max_length=60)] = None,
    request_id: UUID | None = None, limit: Limit = 20, offset: Offset = 0,
):
    return audit_page(request.app.state.db, event_type, str(request_id) if request_id else None, limit, offset)

