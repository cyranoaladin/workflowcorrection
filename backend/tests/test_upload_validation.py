from __future__ import annotations

from uuid import UUID


def _make_pdf_bytes() -> bytes:
    try:
        import pymupdf as fitz  # type: ignore
    except Exception:  # pragma: no cover
        import fitz  # type: ignore

    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "pytest pdf")
    pdf = doc.tobytes()
    doc.close()
    return pdf


def _create_exam(client, cleanup_ids, title: str) -> str:
    r = client.post("/exams", json={"title": title})
    assert r.status_code == 200
    exam_id = r.json()["id"]
    cleanup_ids["exam_ids"].append(UUID(exam_id))
    return exam_id


def test_reject_non_pdf_extension(client, unique_title, cleanup_ids):
    exam_id = _create_exam(client, cleanup_ids, unique_title)
    r = client.post(
        "/copies",
        data={"exam_id": exam_id},
        files={"file": ("not_a_pdf.txt", b"hello", "application/pdf")},
    )
    assert r.status_code == 415


def test_reject_non_pdf_content(client, unique_title, cleanup_ids):
    exam_id = _create_exam(client, cleanup_ids, unique_title)
    r = client.post(
        "/copies",
        data={"exam_id": exam_id},
        files={"file": ("bad.pdf", b"hello", "application/pdf")},
    )
    assert r.status_code == 415


def test_accept_minimal_pdf(client, unique_title, cleanup_ids):
    exam_id = _create_exam(client, cleanup_ids, unique_title)
    pdf = _make_pdf_bytes()
    r = client.post(
        "/copies",
        data={"exam_id": exam_id, "student_name": "Student"},
        files={"file": ("ok.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200
    copy_id = r.json()["id"]
    assert copy_id


def test_reject_too_large_upload(client, unique_title, cleanup_ids):
    # MAX_UPLOAD_SIZE_MB is set to 5 in tests (see conftest.py)
    exam_id = _create_exam(client, cleanup_ids, unique_title)

    big = b"%PDF-1.4\n" + (b"0" * (6 * 1024 * 1024))
    r = client.post(
        "/copies",
        data={"exam_id": exam_id},
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert r.status_code == 413
