from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import PurePosixPath
import re
import unicodedata

import pymupdf

from backend.app.core.errors import AppError
from backend.app.services.retrieval import normalize


# MuPDF operations share one dedicated thread in this process.
PDF_WORKER = ThreadPoolExecutor(max_workers=1, thread_name_prefix="pdf")


@dataclass(frozen=True)
class PDFInfo:
    page_count: int
    title: str


def safe_label(filename: str | None) -> str:
    name = PurePosixPath((filename or "").replace("\\", "/")).name
    clean = "".join(char for char in name if not unicodedata.category(char).startswith("C"))
    clean = re.sub(r'[<>:"/\\|?*]', "_", clean).strip(" .")
    if not clean.lower().endswith(".pdf"):
        raise AppError(422, "invalid_extension", "Choose a file with a .pdf extension.")
    return clean[:176] + ".pdf" if len(clean) > 180 else clean


def safe_title(value: str) -> str:
    cleaned = "".join(char for char in value if not unicodedata.category(char).startswith("C"))
    return normalize(cleaned)[:180]


def inspect_pdf(data: bytes, max_pages: int) -> PDFInfo:
    if not re.match(rb"%PDF-[12]\.\d", data[:12]):
        raise AppError(422, "invalid_pdf", "The file does not have a valid PDF signature.")
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass or doc.is_encrypted:
                raise AppError(422, "encrypted_pdf", "Password-protected PDFs are not supported.")
            if doc.is_repaired or not doc.page_count:
                raise AppError(422, "corrupt_pdf", "The PDF is damaged or has no usable pages.")
            if doc.page_count > max_pages:
                raise AppError(422, "page_limit", f"PDFs may have up to {max_pages} pages.")
            return PDFInfo(doc.page_count, safe_title((doc.metadata or {}).get("title") or ""))
    except (pymupdf.FileDataError, ValueError, RuntimeError) as exc:
        raise AppError(422, "corrupt_pdf", "The PDF could not be read. Export a fresh copy and upload it again.") from exc


def extract_pages(data: bytes):
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        # Preserve layout paragraph breaks until chunking so citation validation can see sentence boundaries.
        return [(page.number + 1, page.get_text(sort=True)) for page in doc]


def render_page(data: bytes, page_number: int):
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        page = doc.load_page(page_number - 1)
        scale = min(1.7, 1450 / max(page.rect.width, page.rect.height, 1))
        return page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), alpha=False).tobytes("png")

