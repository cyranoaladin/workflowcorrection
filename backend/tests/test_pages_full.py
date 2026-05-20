"""Tests for GET /copies/{copy_id}/pages-full batch endpoint."""
from __future__ import annotations

import io
import uuid

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def exam_with_copy(client: TestClient, cleanup_ids: dict) -> tuple[str, str]:
    """Create an exam and upload a 1-page PDF copy."""
    exam_id = str(uuid.uuid4())
    r = client.post(
        "/exams",
        data={"title": "BatchTest", "level": "Test", "session": "2026"},
    )
    assert r.status_code == 200
    exam_id = r.json()["id"]
    cleanup_ids["exam_ids"].append(exam_id)

    # Minimal valid PDF (1 page)
    pdf_bytes = (
        b"%PDF-1.0\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>endobj\n"
        b"xref\n0 4\ntrailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF"
    )
    r = client.post(
        "/copies",
        data={"exam_id": exam_id},
        files={"file": ("test.pdf", io.BytesIO(pdf_bytes), "application/pdf")},
    )
    assert r.status_code == 200
    copy_id = r.json()["id"]
    return exam_id, copy_id


def test_pages_full_returns_empty_for_no_pages(client: TestClient, exam_with_copy: tuple[str, str]) -> None:
    _, copy_id = exam_with_copy
    r = client.get(f"/copies/{copy_id}/pages-full")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, list)
    # No pages yet (process not run), but endpoint works
    for page in data:
        assert "has_processed" in page
        assert "transcriptions" in page
        assert isinstance(page["transcriptions"], list)


def test_pages_full_404_for_missing_copy(client: TestClient) -> None:
    r = client.get(f"/copies/{uuid.uuid4()}/pages-full")
    assert r.status_code == 404
