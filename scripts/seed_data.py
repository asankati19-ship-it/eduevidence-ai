import argparse
from contextlib import closing
from hashlib import sha256
from pathlib import Path
import shutil
import sqlite3
from tempfile import TemporaryDirectory
from uuid import uuid4

from backend.app.core.config import ROOT, Settings
from backend.app.db.database import Database
from backend.app.services.documents import DocumentService
from scripts.sample_content import SAMPLES


SAMPLE_DB = ROOT / "data/sample_database/eduevidence_sample.sqlite3"
SAMPLE_DOCS = ROOT / "data/sample_documents"


def seed(settings, verbose=True):
    db = Database(settings.database_path)
    db.initialize()
    service = DocumentService(db, settings)
    for item in SAMPLES:
        path = SAMPLE_DOCS / item["filename"]
        checksum = sha256(path.read_bytes()).hexdigest()
        present = db.one("SELECT id,status FROM documents WHERE sha256=? AND retired_at IS NULL", (checksum,))
        if present is None:
            request_id = str(uuid4())
            with path.open("rb") as file:
                present = service.ingest(path.name, file, item["course_id"], request_id)
            service.index(present["id"], request_id)
        row = service.get(present["id"])
        if row["status"] != "indexed":
            raise RuntimeError(f"Could not index {path.name}: {row['error_message']}")
        if verbose:
            print(f"Document {row['id']}: {row['title']} | {row['page_count']} pages | {row['chunk_count']} chunks")


def build_sample_database():
    with TemporaryDirectory() as temporary:
        folder = Path(temporary)
        settings = Settings(database_path=folder / "seed.sqlite3", upload_directory=folder / "uploads")
        seed(settings)
        SAMPLE_DB.parent.mkdir(parents=True, exist_ok=True)
        with closing(sqlite3.connect(settings.database_path)) as source, closing(sqlite3.connect(SAMPLE_DB)) as target:
            source.backup(target)
            target.execute("PRAGMA journal_mode = DELETE")
        print(f"Created {SAMPLE_DB.name}")


def restore(settings):
    if settings.database_path.exists():
        raise SystemExit("The target database already exists. Choose a new DATABASE_PATH before restoring.")
    documents = Database(SAMPLE_DB).all("SELECT storage_name,original_filename,sha256 FROM documents")
    service = DocumentService(Database(settings.database_path), settings)
    settings.database_path.parent.mkdir(parents=True, exist_ok=True)
    settings.upload_directory.mkdir(parents=True, exist_ok=True)
    verified = []
    for document in documents:
        source = SAMPLE_DOCS / document["original_filename"]
        destination = service.path(document["storage_name"])
        if sha256(source.read_bytes()).hexdigest() != document["sha256"]:
            raise SystemExit(f"Bundled PDF hash mismatch: {source.name}")
        if destination.exists() and sha256(destination.read_bytes()).hexdigest() != document["sha256"]:
            raise SystemExit(f"Existing upload conflicts with {source.name}")
        verified.append((source, destination))
    for source, destination in verified:
        if not destination.exists():
            with source.open("rb") as incoming, destination.open("xb") as outgoing:
                shutil.copyfileobj(incoming, outgoing)
    with SAMPLE_DB.open("rb") as source, settings.database_path.open("xb") as target:
        shutil.copyfileobj(source, target)
    print(f"Restored {len(documents)} documents at {settings.database_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed the synthetic EduEvidence course library.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--build-sample-db", action="store_true")
    mode.add_argument("--restore-sample", action="store_true")
    args = parser.parse_args()
    if args.build_sample_db:
        build_sample_database()
    elif args.restore_sample:
        restore(Settings.from_environment())
    else:
        seed(Settings.from_environment())

