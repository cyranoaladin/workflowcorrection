from __future__ import annotations

import json
from uuid import UUID


def _make_pdf_bytes(pages: int = 1) -> bytes:
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


def _create_processed_copy(client, cleanup_ids, title: str) -> tuple[str, str]:
    r_exam = client.post("/exams", json={"title": title})
    assert r_exam.status_code == 200
    exam_id = r_exam.json()["id"]
    cleanup_ids["exam_ids"].append(UUID(exam_id))

    pdf = _make_pdf_bytes(pages=1)
    r_copy = client.post(
        "/copies",
        data={"exam_id": exam_id},
        files={"file": ("copy.pdf", pdf, "application/pdf")},
    )
    assert r_copy.status_code == 200
    copy_id = r_copy.json()["id"]

    r_proc = client.post(f"/copies/{copy_id}/process")
    assert r_proc.status_code == 200

    r_pages = client.get(f"/copies/{copy_id}/pages")
    assert r_pages.status_code == 200
    pages = r_pages.json()
    assert len(pages) == 1
    page_id = pages[0]["id"]
    return copy_id, page_id


def test_integrations_status_does_not_leak_keys(client, monkeypatch):
    monkeypatch.setenv("MATHPIX_APP_ID", "id123")
    monkeypatch.setenv("MATHPIX_APP_KEY", "supersecret_mathpix_key")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "https://example.com")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "supersecret_azure_key")
    monkeypatch.setenv("OPENAI_API_KEY", "supersecret_openai_key")

    from app.core.config import get_settings

    get_settings.cache_clear()

    r = client.get("/integrations/status")
    assert r.status_code == 200
    data = r.json()
    dumped = json.dumps(data)
    assert "supersecret_mathpix_key" not in dumped
    assert "supersecret_azure_key" not in dumped
    assert "supersecret_openai_key" not in dumped
    assert data["mathpix"]["configured"] is True
    assert data["azure_document_intelligence"]["configured"] is True
    assert data["openai"]["configured"] is True
    assert data["mathpix"]["paid_calls_enabled"] is False
    assert data["azure_document_intelligence"]["paid_calls_enabled"] is False
    assert data["openai"]["paid_calls_enabled"] is False
    assert data["ocr"]["paid_calls_enabled"] is False
    assert data["ocr"]["max_pages_per_job"] == 3
    assert data["ocr"]["default_image_type"] == "processed"
    assert data["rag"]["provider"] == "pgvector"
    assert data["rag"]["ok"] is True


def test_page_transcriptions_endpoint_empty(client, unique_title, cleanup_ids):
    _, page_id = _create_processed_copy(client, cleanup_ids, unique_title)
    r = client.get(f"/pages/{page_id}/transcriptions")
    assert r.status_code == 200
    assert r.json() == []


def test_fusion_without_inputs_returns_error(client, unique_title, cleanup_ids):
    _, page_id = _create_processed_copy(client, cleanup_ids, unique_title)
    r = client.post(f"/pages/{page_id}/ocr/fuse")
    assert r.status_code == 400
    assert "no_transcriptions" in str(r.json())


def test_ocr_endpoints_blocked_when_paid_calls_disabled(client, unique_title, cleanup_ids):
    _, page_id = _create_processed_copy(client, cleanup_ids, unique_title)

    r1 = client.post(f"/pages/{page_id}/ocr/mathpix")
    assert r1.status_code == 403

    r2 = client.post(f"/pages/{page_id}/ocr/azure")
    assert r2.status_code == 403

    r3 = client.post(f"/pages/{page_id}/ocr/openai-vision")
    assert r3.status_code == 403


def test_missing_keys_errors_when_paid_calls_enabled(client, unique_title, cleanup_ids, monkeypatch):
    _, page_id = _create_processed_copy(client, cleanup_ids, unique_title)

    monkeypatch.setenv("OCR_ENABLE_PAID_CALLS", "true")
    # Keep keys empty to ensure we never hit paid APIs.
    monkeypatch.setenv("MATHPIX_APP_ID", "")
    monkeypatch.setenv("MATHPIX_APP_KEY", "")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
    monkeypatch.setenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
    monkeypatch.setenv("OPENAI_API_KEY", "")

    from app.core.config import get_settings

    get_settings.cache_clear()

    r1 = client.post(f"/pages/{page_id}/ocr/mathpix?confirm_paid_call=true")
    assert r1.status_code == 400
    assert "missing_mathpix_keys" in str(r1.json())

    r2 = client.post(f"/pages/{page_id}/ocr/azure?confirm_paid_call=true")
    assert r2.status_code == 400
    assert "missing_azure_document_intelligence_keys" in str(r2.json())

    r3 = client.post(f"/pages/{page_id}/ocr/openai-vision?confirm_paid_call=true")
    assert r3.status_code == 400
    assert "missing_openai_api_key" in str(r3.json())


def test_page_ocr_requires_confirmation_when_paid_calls_enabled(client, unique_title, cleanup_ids, monkeypatch):
    monkeypatch.setenv("OCR_ENABLE_PAID_CALLS", "true")
    monkeypatch.setenv("MATHPIX_APP_ID", "id")
    monkeypatch.setenv("MATHPIX_APP_KEY", "key")

    from app.core.config import get_settings

    get_settings.cache_clear()

    r = client.post("/pages/00000000-0000-0000-0000-000000000000/ocr/mathpix")
    assert r.status_code == 400
    assert "confirmation_required" in str(r.json())


def test_copy_ocr_max_pages_limit_enforced(client, unique_title, cleanup_ids, monkeypatch):
    copy_id, _ = _create_processed_copy(client, cleanup_ids, unique_title)

    monkeypatch.setenv("OCR_ENABLE_PAID_CALLS", "true")
    monkeypatch.setenv("OCR_MAX_PAGES_PER_JOB", "3")

    from app.core.config import get_settings

    get_settings.cache_clear()

    r = client.post(f"/copies/{copy_id}/ocr?max_pages=999&confirm_paid_calls=true")
    assert r.status_code == 400
    assert "max_pages_exceeds_limit" in str(r.json())


def test_copy_ocr_requires_confirmation_when_paid_calls_enabled(client, unique_title, cleanup_ids, monkeypatch):
    copy_id, _ = _create_processed_copy(client, cleanup_ids, unique_title)

    monkeypatch.setenv("OCR_ENABLE_PAID_CALLS", "true")
    from app.core.config import get_settings

    get_settings.cache_clear()

    r = client.post(f"/copies/{copy_id}/ocr")
    assert r.status_code == 400
    assert "confirmation_required" in str(r.json())
