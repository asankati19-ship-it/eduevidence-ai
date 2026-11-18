from hashlib import sha256
from pathlib import Path
from uuid import uuid4
import logging

from backend.app.core.errors import AppError
from backend.app.db.database import audit, utc_now
from backend.app.services.pdf import PDF_WORKER, extract_pages, inspect_pdf, safe_label, safe_title
from backend.app.services.retrieval import build_index, content_terms, page_chunks


LOGGER = logging.getLogger(__name__)
DOCUMENT_QUERY = """
SELECT d.*, c.code AS course_code, c.title AS course_title,
       (SELECT COUNT(*) FROM document_chunks ch
        WHERE ch.document_id=d.id AND ch.revision=d.active_revision) AS chunk_count
FROM documents d JOIN courses c ON c.id=d.course_id
"""


class DocumentService:
    def __init__(self, db, settings):
        self.db = db
        self.settings = settings

    def get(self, document_id):
        row = self.db.one(DOCUMENT_QUERY + " WHERE d.id=?", (document_id,))
        if row is None:
            raise AppError(404, "document_not_found", "Document not found.")
        return row

    def list(self, course_id, status, search, limit, offset):
        filters = ["d.retired_at IS NULL"]
        params = []
        if course_id is not None:
            filters.append("d.course_id=?")
            params.append(course_id)
        if status:
            filters.append("d.status=?")
            params.append(status)
        if search:
            filters.append("(instr(lower(d.title),lower(?))>0 OR instr(lower(d.original_filename),lower(?))>0)")
            params.extend([search, search])
        where = " WHERE " + " AND ".join(filters)
        with self.db.connection() as con:
            con.execute("BEGIN")
            total = con.execute("SELECT count(*) FROM documents d" + where, params).fetchone()[0]
            items = [dict(row) for row in con.execute(
                DOCUMENT_QUERY + where + " ORDER BY d.id DESC LIMIT ? OFFSET ?", (*params, limit, offset),
            )]
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def path(self, storage_name):
        directory = self.settings.upload_directory.resolve()
        resolved = (directory / storage_name).resolve()
        if resolved.parent != directory or Path(storage_name).name != storage_name:
            raise AppError(500, "invalid_storage_path", "The stored file path is invalid.")
        return resolved

    def ingest(self, filename, stream, course_id, request_id, title=None):
        try:
            return self._reserve_upload(filename, stream, course_id, request_id, title)
        except AppError as exc:
            with self.db.connection(write=True) as con:
                audit(con, request_id, "document.upload", "rejected", detail=exc.code)
            raise

    def _reserve_upload(self, filename, stream, course_id, request_id, title):
        if self.db.one("SELECT id FROM courses WHERE id=?", (course_id,)) is None:
            raise AppError(422, "invalid_course", "Select an existing course.")
        original = safe_label(filename)
        limit = self.settings.max_pdf_mb * 1024 * 1024
        data = stream.read(limit + 1)
        if len(data) > limit:
            raise AppError(413, "file_too_large", f"Maximum PDF size is {self.settings.max_pdf_mb} MB.")
        checksum = sha256(data).hexdigest()
        info = PDF_WORKER.submit(inspect_pdf, data, self.settings.max_pdf_pages).result()
        name = f"{uuid4().hex}.pdf"
        storage = self.path(name)
        now = utc_now()
        display_title = safe_title(title or "") or info.title or Path(original).stem
        with self.db.connection(write=True) as con:
            duplicate = con.execute(
                "SELECT id FROM documents WHERE sha256=? AND retired_at IS NULL", (checksum,),
            ).fetchone()
            if duplicate:
                raise AppError(409, "duplicate_pdf", f"This PDF is already in the library (document {duplicate['id']}).")
            document_id = con.execute(
                """INSERT INTO documents
                (course_id,title,original_filename,storage_name,sha256,size_bytes,page_count,status,job_id,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,'processing',?,?,?)""",
                (course_id, display_title, original, name, checksum, len(data), info.page_count, request_id, now, now),
            ).lastrowid
            audit(con, request_id, "document.upload", "accepted", document_id=document_id)
        try:
            storage.parent.mkdir(parents=True, exist_ok=True)
            with storage.open("xb") as file:
                file.write(data)
        except OSError:
            self.fail(document_id, request_id, "storage_error", "The upload could not be written to local storage.")
            raise AppError(500, "storage_error", "The upload could not be written to local storage.") from None
        return self.get(document_id)

    def index(self, document_id, request_id):
        row = self.get(document_id)
        if row["job_id"] != request_id or row["status"] != "processing":
            return
        try:
            storage = self.path(row["storage_name"])
            data = storage.read_bytes()
            if sha256(data).hexdigest() != row["sha256"]:
                self.fail(document_id, request_id, "content_changed", "The stored PDF differs from the original upload.")
                return
            pages = PDF_WORKER.submit(extract_pages, data).result()
            text_pages = sum(bool(content_terms(text)) for _, text in pages)
            candidates = [
                (page, chunk, sha256(chunk.encode()).hexdigest())
                for page, text in pages
                for chunk in page_chunks(text, self.settings.chunk_words, self.settings.chunk_overlap)
                if content_terms(chunk)
            ]
            if not candidates:
                self.fail(document_id, request_id, "no_text", "No extractable text was found. Use a searchable PDF or run OCR first.", 0)
                return
            # Check indexability before publishing the corpus. Query-time fits reflect each active scope.
            build_index([chunk for _, chunk, _ in candidates])
            candidate_hashes = [(page, checksum) for page, _, checksum in candidates]
            now = utc_now()
            with self.db.connection(write=True) as con:
                current = con.execute(
                    "SELECT active_revision FROM documents WHERE id=? AND status='processing' AND job_id=?",
                    (document_id, request_id),
                ).fetchone()
                if current is None:
                    return
                revision = current["active_revision"]
                active = [tuple(chunk) for chunk in con.execute(
                    """SELECT page_number,content_hash FROM document_chunks
                       WHERE document_id=? AND revision=? ORDER BY chunk_number""", (document_id, revision),
                )]
                unchanged = active == candidate_hashes
                if not unchanged:
                    revision += 1
                    con.executemany(
                        """INSERT INTO document_chunks
                        (document_id,revision,page_number,chunk_number,content,content_hash,created_at)
                        VALUES (?,?,?,?,?,?,?)""",
                        [
                            (document_id, revision, page, number, chunk, checksum, now)
                            for number, (page, chunk, checksum) in enumerate(candidates, 1)
                        ],
                    )
                con.execute(
                    """UPDATE documents SET status='indexed',active_revision=?,text_pages=?,
                       job_id=NULL,error_code=NULL,error_message=NULL,updated_at=? WHERE id=?""",
                    (revision, text_pages, now, document_id),
                )
                detail = f"{len(candidates)} chunks"
                if unchanged:
                    detail += " (unchanged)"
                audit(con, request_id, "document.index", "indexed", detail=detail, document_id=document_id)
        except Exception as exc:
            LOGGER.error("index_failure request_id=%s type=%s", request_id, type(exc).__name__)
            self.fail(document_id, request_id, "extraction_error", "Text extraction or indexing failed. Check the PDF and try reindexing.")

    def fail(self, document_id, request_id, code, message, text_pages=None):
        with self.db.connection(write=True) as con:
            changed = con.execute(
                """UPDATE documents SET status='error',job_id=NULL,error_code=?,error_message=?,text_pages=?,updated_at=?
                   WHERE id=? AND job_id=? AND status='processing'""",
                (code, message, text_pages, utc_now(), document_id, request_id),
            ).rowcount
            if changed:
                audit(con, request_id, "document.index", "error", detail=code, document_id=document_id)

    def reindex(self, document_id, request_id):
        with self.db.connection(write=True) as con:
            row = con.execute("SELECT status FROM documents WHERE id=?", (document_id,)).fetchone()
            if row is None or row["status"] == "retired":
                raise AppError(404, "document_not_found", "Active document not found.")
            if row["status"] == "processing":
                raise AppError(409, "document_busy", "This document is already processing.")
            con.execute(
                "UPDATE documents SET status='processing',job_id=?,error_code=NULL,error_message=NULL,updated_at=? WHERE id=?",
                (request_id, utc_now(), document_id),
            )
            audit(con, request_id, "document.reindex", "accepted", document_id=document_id)
        return self.get(document_id)

    def retire(self, document_id, request_id):
        with self.db.connection(write=True) as con:
            row = con.execute("SELECT status FROM documents WHERE id=?", (document_id,)).fetchone()
            if row is None or row["status"] == "retired":
                raise AppError(404, "document_not_found", "Active document not found.")
            if row["status"] == "processing":
                raise AppError(409, "document_busy", "Wait until processing finishes before removing this document.")
            now = utc_now()
            con.execute("UPDATE documents SET status='retired',retired_at=?,updated_at=? WHERE id=?", (now, now, document_id))
            audit(con, request_id, "document.retire", "retired", document_id=document_id)

    def recover(self):
        for row in self.db.all("SELECT id,job_id FROM documents WHERE status='processing'"):
            self.fail(row["id"], row["job_id"], "interrupted", "Indexing was interrupted. Reindex to try again.")

