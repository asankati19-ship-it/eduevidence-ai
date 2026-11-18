from hashlib import sha256
import sqlite3
from contextlib import closing

import pytest

from backend.app.core.errors import AppError
from backend.app.services.retrieval import normalize, page_chunks
from backend.tests.conftest import pdf_bytes, upload
from backend.tests.fixtures import PYTHON_QUESTION
from scripts.seed_data import SAMPLE_DB, restore


def test_upload_extracts_page_aware_chunks(client):
    data = pdf_bytes(["First module introduces variables and strings.", "Second module teaches exception handling and file reading."])
    response = upload(client, data, title="Approved module notes")
    assert response.status_code == 202
    assert response.json()["status"] == "processing"
    assert response.json()["sha256"] == sha256(data).hexdigest()
    row = client.get("/documents/1").json()
    assert (row["title"], row["page_count"], row["text_pages"], row["chunk_count"], row["status"]) == (
        "Approved module notes", 2, 2, 2, "indexed",
    )
    chunks = client.app.state.db.all("SELECT page_number,content FROM document_chunks ORDER BY id")
    assert chunks[0]["page_number"] == 1 and "variables" in chunks[0]["content"]
    assert chunks[1]["page_number"] == 2 and "exception handling" in chunks[1]["content"]


def test_actual_pdf_page_preview_and_invalid_page(seeded):
    response = seeded.get("/documents/1/pages/4")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG")
    assert seeded.get("/documents/1/pages/5").json()["error"]["code"] == "page_not_found"


@pytest.mark.parametrize(("name", "data", "code"), [
    ("wrong.txt", b"some text", "invalid_extension"),
    ("fake.pdf", b"some text", "invalid_pdf"),
    ("broken.pdf", b"%PDF-1.7\nactually corrupted", "corrupt_pdf"),
])
def test_invalid_upload_is_rejected_and_audited(client, name, data, code):
    response = upload(client, data, name=name)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == code
    assert client.get("/documents").json()["total"] == 0
    audit = client.get("/audit/events", params={"request_id": response.headers["x-request-id"]}).json()["items"]
    assert [(event["outcome"], event["detail"]) for event in audit] == [("rejected", code)]


def test_image_only_pdf_records_visible_error(client):
    doc_id = upload(client, pdf_bytes([""], image_only=True)).json()["id"]
    document = client.get(f"/documents/{doc_id}").json()
    assert document["status"] == "error"
    assert document["error_code"] == "no_text"
    assert "OCR" in document["error_message"]
    assert document["chunk_count"] == 0


def test_encrypted_pdf_rejected(client):
    result = upload(client, pdf_bytes(["Protected grading policy example"], encrypted=True))
    assert result.status_code == 422
    assert result.json()["error"]["code"] == "encrypted_pdf"


def test_upload_size_limit(client):
    client.app.state.settings.max_pdf_mb = 1
    response = upload(client, b"%PDF-1.7" + (b"A" * 1048576))
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "file_too_large"


def test_http_body_limit(client):
    client.app.state.settings.max_pdf_mb = 1
    response = client.post("/documents/upload", content=b"x" * 1300000)
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_streamed_body_limit_without_content_length(client):
    response = client.post("/questions", content=iter([b"x" * 65536] * 3),
                           headers={"Content-Type": "application/json"})
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"


def test_page_count_limit(client):
    client.app.state.settings.max_pdf_pages = 1
    assert upload(client, pdf_bytes(["First page", "Second page"])).json()["error"]["code"] == "page_limit"


def test_duplicate_hash_under_different_name(client):
    document = pdf_bytes(["A searchable attendance notice for learners."])
    assert upload(client, document, name="first.pdf").status_code == 202
    response = upload(client, document, name="second.pdf", course=2)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "duplicate_pdf"


def test_filename_sanitization_and_storage_path(client):
    response = upload(client, pdf_bytes(["The synthetic course handbook has three chapters."]), name="../../unsafe.pdf")
    assert response.status_code == 202
    assert response.json()["original_filename"] == "unsafe.pdf"
    database = client.app.state.db
    stored = database.one("SELECT storage_name FROM documents")["storage_name"]
    assert stored != "unsafe.pdf" and stored.endswith(".pdf")
    service = client.app.state.documents
    assert service.path(stored).exists()
    with pytest.raises(AppError, match="path is invalid"):
        service.path("../unsafe.pdf")


def test_chunk_window_overlap_and_unicode_normalization():
    words = ["term" + str(number) for number in range(45)]
    actual = list(page_chunks(" ".join(words), size=20, overlap=5))
    assert [len(chunk.split()) for chunk in actual] == [20, 20, 15]
    assert actual[0].split()[-5:] == actual[1].split()[:5]
    assert normalize("ﬁles repre-\n sented\u00a0here.") == "files represented here."


def test_course_search_filter_and_pagination(seeded):
    course = seeded.get("/documents", params={"course_id": 2, "status": "indexed"}).json()
    assert course["total"] == 1 and course["items"][0]["course_code"] == "AI-201"
    assert seeded.get("/documents", params={"search": "attenDANCE"}).json()["total"] == 1
    limited = seeded.get("/documents", params={"limit": 1, "offset": 1}).json()
    assert limited["total"] == 3 and len(limited["items"]) == 1


def test_identical_reindex_does_not_duplicate_chunks_or_invalidate_citations(seeded):
    first = seeded.post("/questions", json={"question": PYTHON_QUESTION, "document_id": 1}).json()
    original_chunk = first["citations"][0]["chunk_id"]
    before = seeded.get("/documents/1").json()
    assert seeded.post("/documents/1/reindex").status_code == 202
    after = seeded.get("/documents/1").json()
    assert after["active_revision"] == before["active_revision"]
    assert before["chunk_count"] == after["chunk_count"] == 4
    second = seeded.post("/questions", json={"question": PYTHON_QUESTION, "document_id": 1}).json()
    assert second["citations"][0]["chunk_id"] == original_chunk
    assert seeded.app.state.db.one("SELECT count(*) AS count FROM document_chunks WHERE document_id=1")["count"] == 4
    assert seeded.get(f"/questions/{first['id']}").json()["citations"][0]["chunk_id"] == original_chunk


def test_changed_chunking_publishes_new_revision_but_keeps_original_trace(seeded):
    old = seeded.post("/questions", json={"question": PYTHON_QUESTION, "document_id": 1}).json()
    settings = seeded.app.state.settings
    settings.chunk_words = 45
    settings.chunk_overlap = 10
    assert seeded.post("/documents/1/reindex").status_code == 202
    updated = seeded.get("/documents/1").json()
    assert updated["active_revision"] == 2 and updated["chunk_count"] > 4
    assert seeded.get(f"/questions/{old['id']}").json()["citations"] == old["citations"]


def test_preview_and_reindex_detect_modified_file(seeded):
    row = seeded.app.state.documents.get(1)
    seeded.app.state.documents.path(row["storage_name"]).write_bytes(b"modified")
    assert seeded.get("/documents/1/pages/4").json()["error"]["code"] == "content_changed"
    assert seeded.post("/documents/1/reindex").status_code == 202
    assert seeded.get("/documents/1").json()["error_code"] == "content_changed"


def test_remove_excludes_retrieval_preserves_historic_page(seeded):
    old = seeded.post("/questions", json={"question": PYTHON_QUESTION, "document_id": 1}).json()
    assert old["status"] == "answered"
    assert seeded.delete("/documents/1").status_code == 204
    assert seeded.get("/documents").json()["total"] == 2
    assert seeded.post("/questions", json={"question": PYTHON_QUESTION, "document_id": 1}).status_code == 404
    assert seeded.get("/documents/1/pages/4").status_code == 200
    assert seeded.get(f"/questions/{old['id']}").json()["citations"] == old["citations"]


def test_sample_db_can_restore_pdf_previews(settings):
    assert SAMPLE_DB.exists()
    with closing(sqlite3.connect(SAMPLE_DB)) as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert con.execute("PRAGMA foreign_key_check").fetchall() == []
    restore(settings)
    assert settings.database_path.exists()
    assert len(list(settings.upload_directory.glob("*.pdf"))) == 3
    with pytest.raises(SystemExit, match="already exists"):
        restore(settings)

