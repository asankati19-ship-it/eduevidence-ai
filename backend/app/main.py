from contextlib import asynccontextmanager
from time import perf_counter
from urllib.parse import urlsplit
from uuid import uuid4
import logging
import sqlite3

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from backend.app.api.routes import router
from backend.app.connectors.lms import LocalLMSConnector
from backend.app.core.config import Settings
from backend.app.core.errors import AppError
from backend.app.db.database import Database
from backend.app.services.documents import DocumentService
from backend.app.services.provider import OpenAIProvider
from backend.app.services.questions import QuestionService


LOGGER = logging.getLogger("eduevidence")
LOCAL_HOSTS = ("127.0.0.1", "localhost")
TEST_HOST = "testserver"


def error_response(request, status_code, code, message, issues=None):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message, "request_id": request_id, "issues": issues or []}},
        headers={"X-Request-ID": request_id, "X-Content-Type-Options": "nosniff"},
    )


class BodyLimitMiddleware:
    def __init__(self, app, settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] != "POST":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        cap = 128 * 1024
        if scope["path"] == "/documents/upload":
            cap += self.settings.max_pdf_mb * 1024 * 1024
        size = request.headers.get("content-length", "")
        if size.isdigit() and (len(size) > 12 or int(size) > cap):
            response = error_response(request, 413, "request_too_large", "The request body exceeds the configured limit.")
            await response(scope, receive, send)
            return

        bytes_seen = 0

        async def limited_receive():
            nonlocal bytes_seen
            message = await receive()
            bytes_seen += len(message.get("body", b""))
            if bytes_seen > cap:
                raise HTTPException(413, "The request body exceeds the configured limit.")
            return message

        await self.app(scope, limited_receive, send)


def create_app(settings=None, provider=None, *, testing=False):
    settings = settings or Settings.from_environment()
    database = Database(settings.database_path)
    provider = provider or OpenAIProvider(settings)
    lms = LocalLMSConnector(database)
    documents = DocumentService(database, settings)
    questions = QuestionService(database, settings, provider, lms)

    @asynccontextmanager
    async def lifespan(_app):
        database.initialize()
        documents.recover()
        questions.recover()
        yield

    app = FastAPI(
        title="EduEvidence AI", version="1.0.0",
        description="Local synthetic LMS document question answering with verified source ancestry.",
        lifespan=lifespan,
    )
    app.state.settings = settings
    app.state.db = database
    app.state.provider = provider
    app.state.lms = lms
    app.state.documents = documents
    app.state.questions = questions
    hosts = (*LOCAL_HOSTS, TEST_HOST) if testing else LOCAL_HOSTS
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(hosts))
    app.add_middleware(BodyLimitMiddleware, settings=settings)

    @app.middleware("http")
    async def request_context(request: Request, next_handler):
        request.state.request_id = str(uuid4())
        started = perf_counter()
        origin = request.headers.get("origin")
        if request.method in ("POST", "PUT", "DELETE", "PATCH") and origin:
            try:
                parsed_origin = urlsplit(origin)
                allowed = parsed_origin.scheme in ("http", "https") and parsed_origin.hostname in hosts
            except ValueError:
                allowed = False
            if not allowed:
                return error_response(request, 403, "origin_denied", "Write requests must originate from the local workspace.")
        response = await next_handler(request)
        response.headers["X-Request-ID"] = request.state.request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        LOGGER.info("request_id=%s method=%s status=%s elapsed_ms=%d",
                    request.state.request_id, request.method, response.status_code, (perf_counter() - started) * 1000)
        return response

    @app.exception_handler(AppError)
    async def application_error(request, exc):
        return error_response(request, exc.status_code, exc.code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        issues = [{"field": ".".join(str(part) for part in issue["loc"]), "message": issue["msg"]} for issue in exc.errors()]
        return error_response(request, 422, "invalid_input", "Check the submitted fields.", issues)

    @app.exception_handler(HTTPException)
    async def http_error(request, exc):
        code = "request_too_large" if exc.status_code == 413 else "http_error"
        return error_response(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(sqlite3.Error)
    async def database_error(request, exc):
        LOGGER.error("database_failure request_id=%s type=%s", request.state.request_id, type(exc).__name__)
        return error_response(request, 503, "database_error", "The workspace database is temporarily unavailable. Try again.")

    @app.exception_handler(Exception)
    async def unexpected_error(request, exc):
        LOGGER.error("unexpected_failure request_id=%s type=%s", request.state.request_id, type(exc).__name__)
        return error_response(request, 500, "server_error", "The local server could not complete the request.")

    app.include_router(router)
    return app

