from __future__ import annotations

import os
from pathlib import Path
from uuid import UUID


def _make_pdf_bytes(pages: int = 2) -> bytes:
    try:
        import pymupdf as fitz  # type: ignore
    except Exception:  # pragma: no cover
        import fitz  # type: ignore

    doc = fitz.open()
    for i in range(pages):
        p = doc.new_page()
        p.insert_text((72, 72), f"pytest page {i+1}")
    data = doc.tobytes()
    doc.close()
    return data


def test_processing_idempotence_force(client, unique_title, cleanup_ids):
    # Create exam
    r_exam = client.post("/exams", json={"title": unique_title})
    assert r_exam.status_code == 200
    exam_id = r_exam.json()["id"]
    cleanup_ids["exam_ids"].append(UUID(exam_id))

    # Upload copy
    pdf = _make_pdf_bytes(pages=2)
    r_copy = client.post(
        "/copies",
        data={"exam_id": exam_id},
        files={"file": ("copy.pdf", pdf, "application/pdf")},
    )
    assert r_copy.status_code == 200
    copy_id = r_copy.json()["id"]

    # First process
    r_p1 = client.post(f"/copies/{copy_id}/process")
    assert r_p1.status_code == 200

    r_copy2 = client.get(f"/copies/{copy_id}")
    assert r_copy2.status_code == 200
    assert r_copy2.json()["status"] == "processed_pages"

    r_pages1 = client.get(f"/copies/{copy_id}/pages")
    assert r_pages1.status_code == 200
    pages1 = r_pages1.json()
    assert len(pages1) == 2
    old_page_ids = [p["id"] for p in pages1]

    # Second process without force should not error
    r_p2 = client.post(f"/copies/{copy_id}/process")
    assert r_p2.status_code == 200
    assert r_p2.json()["status"] == "already_processed"

    # Force reprocess should recreate pages and delete old derived images
    storage_root = Path(os.environ["LOCAL_STORAGE_PATH"])
    old_dirs = [storage_root / "pages" / pid for pid in old_page_ids]
    assert all(d.exists() for d in old_dirs)

    r_p3 = client.post(f"/copies/{copy_id}/process?force=true")
    assert r_p3.status_code == 200

    r_copy3 = client.get(f"/copies/{copy_id}")
    assert r_copy3.status_code == 200
    assert r_copy3.json()["status"] == "processed_pages"

    r_pages2 = client.get(f"/copies/{copy_id}/pages")
    assert r_pages2.status_code == 200
    pages2 = r_pages2.json()
    assert len(pages2) == 2
    new_page_ids = [p["id"] for p in pages2]
    assert set(new_page_ids) != set(old_page_ids)

    # Old derived page dirs removed
    assert all(not d.exists() for d in old_dirs)


def test_processing_rejects_pdf_over_page_limit():
    from app.workers.tasks import enforce_pdf_page_limit

    try:
        enforce_pdf_page_limit(page_count=2, max_pages=1)
    except ValueError as exc:
        assert "too_many_pages" in str(exc)
    else:
        raise AssertionError("Expected page limit rejection")
