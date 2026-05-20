from __future__ import annotations

import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest

FIXTURE_DIR = Path(__file__).parent / "fixtures"
RUBRIC = {
    "questions": [
        {
            "id": "Q1",
            "label": "Calculer f'(x)",
            "points_max": 4,
            "criteria": ["Dérivée correcte"],
            "expected_answer": "2x",
        },
        {
            "id": "Q2",
            "label": "Intégrer x^2",
            "points_max": 6,
            "criteria": ["Primitive correcte"],
            "expected_answer": "x^3/3",
        },
    ]
}


def _embedding(texts: list[str]) -> list[list[float]]:
    return [[1.0] + [0.0] * 1535 for _ in texts]


def _llm_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps(payload)
    return response


@pytest.mark.e2e
def test_full_correction_pipeline_with_rag_context(client, cleanup_ids, monkeypatch):
    if os.getenv("RAG_E2E_ENABLED", "false").lower() != "true":
        monkeypatch.setenv("RAG_PROVIDER", "pgvector")

    from app.core.config import get_settings
    from app.services.rag.factory import get_rag_provider

    get_settings.cache_clear()
    get_rag_provider.cache_clear()

    exam = client.post("/exams", json={"title": "DS Math E2E", "level": "Terminale", "session": "2026"})
    assert exam.status_code == 200
    exam_id = exam.json()["id"]
    cleanup_ids["exam_ids"].append(UUID(exam_id))

    with (FIXTURE_DIR / "correction.pdf").open("rb") as correction_file:
        uploaded = client.post(
            f"/exams/{exam_id}/files",
            files={"correction_pdf": ("correction.pdf", correction_file, "application/pdf")},
        )
    assert uploaded.status_code == 200
    assert uploaded.json()["embedding_status"] == "idle"

    with (
        patch("app.workers.embed_tasks.embed_texts", side_effect=_embedding),
        patch(
            "app.services.rag.pgvector_provider.embed_texts",
            side_effect=_embedding,
        ),
    ):
        rubric_response = client.post(f"/exams/{exam_id}/rubric-json", json=RUBRIC)
        assert rubric_response.status_code == 200

        exam_state = rubric_response.json()
        for _ in range(30):
            if exam_state["embedding_status"] == "embedded":
                break
            time.sleep(1)
            exam_state = client.get(f"/exams/{exam_id}").json()

        assert exam_state["embedding_status"] == "embedded"
        assert exam_state["embedded_chunks_count"] > 0

        knowledge = client.get(f"/exams/{exam_id}/knowledge")
        assert knowledge.status_code == 200
        knowledge_payload = knowledge.json()
        assert len(knowledge_payload["documents"]) >= 2
        assert knowledge_payload["total_chunks"] > 0

        with (FIXTURE_DIR / "student_copy.pdf").open("rb") as copy_file:
            copy_response = client.post(
                "/copies",
                data={"exam_id": exam_id, "student_name": "Élève E2E"},
                files={"file": ("student_copy.pdf", copy_file, "application/pdf")},
            )
        assert copy_response.status_code == 200
        copy_id = copy_response.json()["id"]

        process_response = client.post(f"/copies/{copy_id}/process")
        assert process_response.status_code == 200

        status_payload = {}
        for _ in range(30):
            status_payload = client.get(f"/copies/{copy_id}/status").json()
            if status_payload["status"] == "processed_pages":
                break
            time.sleep(1)
        assert status_payload["status"] == "processed_pages"

        pages_response = client.get(f"/copies/{copy_id}/pages")
        assert pages_response.status_code == 200
        page_id = pages_response.json()[0]["id"]

        monkeypatch.setenv("OCR_ENABLE_PAID_CALLS", "true")
        get_settings.cache_clear()
        with patch(
            "app.routers.pages.call_openai_vision_for_transcription",
            return_value={
                "status": "ok",
                "raw_text": "Q1: f'(x)=2x. Q2: primitive x^3/3.",
                "raw_latex": "f'(x)=2x",
                "confidence": 0.95,
                "raw_json": {"source": "mock"},
            },
        ):
            ocr_response = client.post(f"/pages/{page_id}/ocr/openai-vision?confirm_paid_call=true")
        assert ocr_response.status_code == 200

        grading_response = _llm_response(
            {
                "points_awarded": 4,
                "confidence": 0.9,
                "needs_human_review": False,
                "justification": "Réponse correcte",
                "criteria_details": [],
            }
        )
        with (
            patch("app.services.grading_service.OpenAI") as mock_grading,
            patch("app.routers.corrections.audit_correction") as mock_audit,
        ):
            mock_grading.return_value.chat.completions.create.return_value = grading_response
            mock_audit.return_value = {
                "audit_passed": True,
                "overall_confidence": 0.9,
                "needs_human_review": False,
                "flags": [],
                "summary": "OK",
                "recommendation": "validate",
                "status": "ok",
            }
            grade_response = client.post(f"/copies/{copy_id}/grade")
        assert grade_response.status_code == 200
        assert grade_response.json()["status"] == "corrected"

    report = client.get(f"/copies/{copy_id}/report")
    assert report.status_code == 200
    report_payload = report.json()
    assert report_payload["copy_id"] == copy_id
    assert report_payload["score"]["total_awarded"] > 0
    assert len(report_payload["questions"]) >= 1

    correction_id = report_payload["questions"][0]["id"]
    validation = client.patch(f"/corrections/{correction_id}/validate?validated=true")
    assert validation.status_code == 200
    assert validation.json()["validated_by_human"] is True

    bilan = client.get(f"/exams/{exam_id}/bilan")
    assert bilan.status_code == 200
    assert bilan.json()["exam_id"] == exam_id
