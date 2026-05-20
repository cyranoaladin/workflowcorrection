from __future__ import annotations

import os
import shutil
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

# IMPORTANT: these env vars must be set before importing the app/settings.
# APP_ENV=test ensures validate_for_runtime() is skipped even on prod servers.
os.environ["APP_ENV"] = "test"
TEST_STORAGE_ROOT = Path("/tmp/math-correction-test-storage")
os.environ["LOCAL_STORAGE_PATH"] = str(TEST_STORAGE_ROOT)
# Force a small limit for tests regardless of what's in .env / container env.
os.environ["MAX_UPLOAD_SIZE_MB"] = "5"
os.environ["OCR_ENABLE_PAID_CALLS"] = "false"
os.environ["OCR_MAX_PAGES_PER_JOB"] = "3"
os.environ["OCR_DEFAULT_IMAGE_TYPE"] = "processed"
os.environ["OPENAI_API_KEY"] = "sk-test"
os.environ["ADMIN_API_TOKEN"] = "pytest-admin-token"
os.environ["PDF_MAX_PAGES"] = "20"
os.environ["RAG_PROVIDER"] = "pgvector"


def _reset_caches() -> None:
    from app.core.config import get_settings

    get_settings.cache_clear()

    import app.core.storage as storage_mod

    storage_mod._storage = None


_reset_caches()


def _prepare_storage() -> None:
    if TEST_STORAGE_ROOT.exists():
        shutil.rmtree(TEST_STORAGE_ROOT)
    TEST_STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


_prepare_storage()


def _configure_celery_eager() -> None:
    from app.workers.celery_app import celery

    celery.conf.task_always_eager = True
    celery.conf.task_store_eager_result = True
    celery.conf.task_eager_propagates = True


_configure_celery_eager()


@pytest.fixture(scope="session")
def client() -> TestClient:
    from app.main import app

    c = TestClient(app)
    c.headers.update({"Authorization": "Bearer pytest-admin-token"})
    return c


@pytest.fixture(scope="session")
def anon_client() -> TestClient:
    from app.main import app

    return TestClient(app)


@pytest.fixture
def unique_title() -> str:
    return f"pytest-{uuid.uuid4()}"


@pytest.fixture
def cleanup_ids() -> dict:
    """
    Collect created IDs to be cleaned up from the real DB.
    Uses DB-level cascade deletes (exams -> student_copies -> copy_pages).
    """
    return {"exam_ids": []}


@pytest.fixture(autouse=True)
def _cleanup_db_after_test(cleanup_ids: dict):
    yield

    from app.core.database import SessionLocal
    from app.models.exam import Exam

    db = SessionLocal()
    try:
        for exam_id in cleanup_ids["exam_ids"]:
            db.query(Exam).filter(Exam.id == exam_id).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()

    # Ensure environment monkeypatches don't leak via cached settings/storage.
    _reset_caches()
