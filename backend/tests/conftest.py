from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
import pymupdf
import pytest

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.tests.fixtures import FixtureProvider
from scripts.seed_data import seed


@pytest.fixture
def settings(tmp_path):
    return Settings(database_path=tmp_path / "test.sqlite3", upload_directory=tmp_path / "uploads")


@pytest.fixture
def provider():
    return FixtureProvider()


@pytest.fixture
def client(settings, provider):
    with TestClient(create_app(settings, provider, testing=True)) as test:
        yield test


@pytest.fixture
def seeded(settings, provider):
    seed(settings, verbose=False)
    with TestClient(create_app(settings, provider, testing=True)) as test:
        yield test


def pdf_bytes(pages, *, encrypted=False, image_only=False, title="Test Course Manual"):
    with pymupdf.open() as pdf:
        pdf.set_metadata({"title": title})
        for text in pages:
            page = pdf.new_page()
            if image_only:
                image = BytesIO()
                Image.new("RGB", (72, 72), "navy").save(image, format="PNG")
                page.insert_image(pymupdf.Rect(72, 72, 144, 144), stream=image.getvalue())
            else:
                page.insert_textbox(pymupdf.Rect(65, 70, 550, 750), text, fontsize=12)
        params = {"encryption": pymupdf.PDF_ENCRYPT_AES_256, "owner_pw": "test-owner", "user_pw": "test-reader"} if encrypted else {}
        return pdf.tobytes(**params)


def upload(client, data, course=1, name="test.pdf", **fields):
    return client.post("/documents/upload", data={"course_id": course, **fields}, files={"file": (name, data, "application/pdf")})

