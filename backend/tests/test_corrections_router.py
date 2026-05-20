"""
Integration tests for corrections router: grade, report, validate, bilan.
LLM calls are mocked. Uses real DB (via conftest.py).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch
from uuid import UUID

# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_pdf_bytes(pages: int = 1) -> bytes:
    try:
        import pymupdf as fitz
    except Exception:
        import fitz
    doc = fitz.open()
    for i in range(pages):
        p = doc.new_page()
        p.insert_text((72, 72), f"Q1: f(x) = x^2, donc f'(x) = 2x. Résultat : 2x. Page {i+1}")
    data = doc.tobytes()
    doc.close()
    return data


RUBRIC = {
    "questions": [
        {
            "id": "Q1",
            "label": "Calculer f'(x)",
            "points_max": 4,
            "criteria": ["Méthode correcte", "Résultat exact"],
            "expected_answer": "f'(x) = 2x",
        },
        {
            "id": "Q2",
            "label": "Calculer l'intégrale",
            "points_max": 6,
            "criteria": ["Primitive correcte", "Bornes", "Résultat final"],
        },
    ]
}

MOCK_GRADE_Q1 = {
    "question_id": "Q1",
    "points_max": 4.0,
    "points_awarded": 3.5,
    "confidence": 0.88,
    "needs_human_review": False,
    "justification": "Méthode correcte, résultat bon",
    "criteria_details": [{"criterion": "Méthode correcte", "awarded": 2, "comment": "ok"}],
    "status": "ok",
    "error_message": None,
}

MOCK_GRADE_Q2 = {
    "question_id": "Q2",
    "points_max": 6.0,
    "points_awarded": 4.0,
    "confidence": 0.75,
    "needs_human_review": False,
    "justification": "Primitive ok, résultat correct",
    "criteria_details": [],
    "status": "ok",
    "error_message": None,
}


def _setup_exam_with_rubric(client, cleanup_ids, unique_title):
    """Create exam + set rubric_json. Returns exam_id."""
    r = client.post("/exams", json={"title": unique_title, "level": "TS", "session": "2026"})
    assert r.status_code == 200
    exam_id = r.json()["id"]
    cleanup_ids["exam_ids"].append(UUID(exam_id))

    r2 = client.post(f"/exams/{exam_id}/rubric-json", json=RUBRIC)
    assert r2.status_code == 200
    assert r2.json()["rubric_json"]["questions"][0]["id"] == "Q1"
    return exam_id


def _setup_processed_copy(client, cleanup_ids, unique_title):
    """Create exam + copy + process. Returns (exam_id, copy_id)."""
    exam_id = _setup_exam_with_rubric(client, cleanup_ids, unique_title)
    pdf = _make_pdf_bytes(pages=1)
    r = client.post(
        "/copies",
        data={"exam_id": exam_id, "student_name": "Alice Dupont", "copy_code": "A01"},
        files={"file": ("copy.pdf", pdf, "application/pdf")},
    )
    assert r.status_code == 200
    copy_id = r.json()["id"]

    r2 = client.post(f"/copies/{copy_id}/process")
    assert r2.status_code == 200
    assert client.get(f"/copies/{copy_id}").json()["status"] == "processed_pages"

    return exam_id, copy_id


def _inject_transcription(copy_id: str, text: str):
    """Directly insert a transcription row for tests."""
    from uuid import uuid4

    from app.core.database import SessionLocal
    from app.models.transcription import Transcription

    db = SessionLocal()
    try:
        t = Transcription(
            id=uuid4(),
            copy_id=UUID(copy_id),
            source="test",
            raw_text=text,
            final_text=text,
        )
        db.add(t)
        db.commit()
    finally:
        db.close()


# ─── rubric-json endpoint ─────────────────────────────────────────────────────


class TestRubricJson:
    def test_set_rubric_json_success(self, client, cleanup_ids, unique_title):
        r = client.post("/exams", json={"title": unique_title})
        assert r.status_code == 200
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))

        r2 = client.post(f"/exams/{exam_id}/rubric-json", json=RUBRIC)
        assert r2.status_code == 200
        data = r2.json()
        assert data["rubric_json"]["questions"][0]["id"] == "Q1"
        assert len(data["rubric_json"]["questions"]) == 2
        assert data["embedding_status"] == "idle"

    @patch("app.workers.embed_tasks.embed_exam_task.delay")
    def test_auto_embed_triggers_when_correction_and_rubric_present(
        self,
        mock_delay,
        client,
        cleanup_ids,
        unique_title,
    ):
        r = client.post("/exams", json={"title": unique_title})
        assert r.status_code == 200
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))

        pdf = _make_pdf_bytes()
        files = {"correction_pdf": ("correction.pdf", pdf, "application/pdf")}
        uploaded = client.post(f"/exams/{exam_id}/files", files=files)
        assert uploaded.status_code == 200
        assert uploaded.json()["embedding_status"] == "idle"
        mock_delay.assert_not_called()

        r2 = client.post(f"/exams/{exam_id}/rubric-json", json=RUBRIC)
        assert r2.status_code == 200
        assert r2.json()["embedding_status"] == "queued"
        mock_delay.assert_called_once_with(exam_id, force=False)

    @patch("app.workers.embed_tasks.embed_exam_task.delay")
    def test_auto_embed_triggers_when_rubric_exists_and_correction_uploaded(
        self,
        mock_delay,
        client,
        cleanup_ids,
        unique_title,
    ):
        r = client.post("/exams", json={"title": unique_title})
        assert r.status_code == 200
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))

        r2 = client.post(f"/exams/{exam_id}/rubric-json", json=RUBRIC)
        assert r2.status_code == 200
        assert r2.json()["embedding_status"] == "idle"
        mock_delay.assert_not_called()

        pdf = _make_pdf_bytes()
        files = {"correction_pdf": ("correction.pdf", pdf, "application/pdf")}
        uploaded = client.post(f"/exams/{exam_id}/files", files=files)
        assert uploaded.status_code == 200
        assert uploaded.json()["embedding_status"] == "queued"
        mock_delay.assert_called_once_with(exam_id, force=False)

    def test_rejects_empty_questions(self, client, cleanup_ids, unique_title):
        r = client.post("/exams", json={"title": unique_title})
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))

        r2 = client.post(f"/exams/{exam_id}/rubric-json", json={"questions": []})
        assert r2.status_code == 422
        assert r2.json()["detail"]["error"] == "invalid_rubric"

    def test_rejects_missing_id(self, client, cleanup_ids, unique_title):
        r = client.post("/exams", json={"title": unique_title})
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))

        r2 = client.post(
            f"/exams/{exam_id}/rubric-json",
            json={"questions": [{"label": "Q", "points_max": 2}]},
        )
        assert r2.status_code == 422
        assert "missing_question_id" in r2.json()["detail"]["error"]

    def test_rejects_missing_points_max(self, client, cleanup_ids, unique_title):
        r = client.post("/exams", json={"title": unique_title})
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))

        r2 = client.post(
            f"/exams/{exam_id}/rubric-json",
            json={"questions": [{"id": "Q1", "label": "X"}]},
        )
        assert r2.status_code == 422
        assert "missing_points_max" in r2.json()["detail"]["error"]

    def test_404_on_unknown_exam(self, client):
        r = client.post("/exams/00000000-0000-0000-0000-000000000000/rubric-json", json=RUBRIC)
        assert r.status_code == 404


# ─── exam update endpoint ─────────────────────────────────────────────────────


class TestExamUpdate:
    def test_patch_exam_title(self, client, cleanup_ids, unique_title):
        r = client.post("/exams", json={"title": unique_title})
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))

        r2 = client.patch(f"/exams/{exam_id}", json={"title": "Nouveau titre", "total_points": 30})
        assert r2.status_code == 200
        data = r2.json()
        assert data["title"] == "Nouveau titre"
        assert float(data["total_points"]) == 30.0

    def test_patch_exam_404(self, client):
        r = client.patch("/exams/00000000-0000-0000-0000-000000000000", json={"title": "x"})
        assert r.status_code == 404


# ─── grading endpoint ────────────────────────────────────────────────────────


class TestGradeEndpoint:
    def test_grade_requires_processed_status(self, client, cleanup_ids, unique_title):
        exam_id = _setup_exam_with_rubric(client, cleanup_ids, unique_title)
        pdf = _make_pdf_bytes()
        r = client.post(
            "/copies",
            data={"exam_id": exam_id},
            files={"file": ("c.pdf", pdf, "application/pdf")},
        )
        copy_id = r.json()["id"]
        # Status = uploaded, not processed_pages

        r2 = client.post(f"/copies/{copy_id}/grade")
        assert r2.status_code == 409
        assert r2.json()["detail"]["error"] == "invalid_status"

    def test_grade_requires_rubric(self, client, cleanup_ids, unique_title):
        r = client.post("/exams", json={"title": unique_title})
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))
        pdf = _make_pdf_bytes()
        r2 = client.post(
            "/copies",
            data={"exam_id": exam_id},
            files={"file": ("c.pdf", pdf, "application/pdf")},
        )
        copy_id = r2.json()["id"]
        client.post(f"/copies/{copy_id}/process")
        # No rubric_json set

        r3 = client.post(f"/copies/{copy_id}/grade")
        assert r3.status_code == 422
        assert r3.json()["detail"]["error"] == "no_rubric"

    def test_grade_requires_transcription(self, client, cleanup_ids, unique_title):
        _, copy_id = _setup_processed_copy(client, cleanup_ids, unique_title)
        # No transcription added

        r = client.post(f"/copies/{copy_id}/grade")
        assert r.status_code == 409
        assert r.json()["detail"]["error"] == "no_transcription"

    def test_grade_full_flow_mocked(self, client, cleanup_ids, unique_title):
        exam_id, copy_id = _setup_processed_copy(client, cleanup_ids, unique_title)
        _inject_transcription(copy_id, "f'(x) = 2x car la dérivée de x^2 est 2x. Intégrale = x^3/3.")

        with patch("app.services.grading_service.OpenAI") as MockG, patch("app.services.audit_service.OpenAI") as MockA:

            def side_effect(*args, **kwargs):
                prompt = kwargs["messages"][1]["content"]
                if "f'(x)" in prompt or "Q1" in prompt:
                    resp = MagicMock()
                    resp.choices = [MagicMock()]
                    resp.choices[0].message.content = (
                        '{"points_awarded": 3.5, "confidence": 0.88, "needs_human_review": false,'
                        ' "justification": "Bonne réponse", "criteria_details": []}'
                    )
                    return resp
                else:
                    resp = MagicMock()
                    resp.choices = [MagicMock()]
                    resp.choices[0].message.content = (
                        '{"points_awarded": 4.0, "confidence": 0.75, "needs_human_review": false,'
                        ' "justification": "Correcte", "criteria_details": []}'
                    )
                    return resp

            MockG.return_value.chat.completions.create.side_effect = side_effect

            audit_resp = MagicMock()
            audit_resp.choices = [MagicMock()]
            audit_resp.choices[
                0
            ].message.content = (
                '{"audit_passed": true, "additional_flags": [], "summary": "OK", "recommendation": "validate"}'
            )
            MockA.return_value.chat.completions.create.return_value = audit_resp

            r = client.post(f"/copies/{copy_id}/grade")

        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "corrected"
        assert data["questions_graded"] == 2
        assert data["total_awarded"] > 0
        assert data["audit"]["audit_passed"] is True

        # Copy status updated
        copy = client.get(f"/copies/{copy_id}").json()
        assert copy["status"] == "corrected"
        assert copy["total_score"] is not None

    def test_grade_already_corrected_no_force(self, client, cleanup_ids, unique_title):
        exam_id, copy_id = _setup_processed_copy(client, cleanup_ids, unique_title)
        _inject_transcription(copy_id, "réponse test")

        with patch("app.services.grading_service.OpenAI") as MockG, patch("app.services.audit_service.OpenAI"):
            resp = MagicMock()
            resp.choices = [MagicMock()]
            resp.choices[0].message.content = (
                '{"points_awarded": 2, "confidence": 0.9, "needs_human_review": false,'
                ' "justification": "ok", "criteria_details": []}'
            )
            MockG.return_value.chat.completions.create.return_value = resp
            client.post(f"/copies/{copy_id}/grade")
            r2 = client.post(f"/copies/{copy_id}/grade")

        assert r2.status_code == 200
        assert r2.json()["status"] == "already_corrected"

    def test_grade_force_regraded(self, client, cleanup_ids, unique_title):
        exam_id, copy_id = _setup_processed_copy(client, cleanup_ids, unique_title)
        _inject_transcription(copy_id, "réponse test")

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = (
            '{"points_awarded": 2, "confidence": 0.8, "needs_human_review": false,'
            ' "justification": "ok", "criteria_details": []}'
        )

        with patch("app.services.grading_service.OpenAI") as MockG, patch("app.services.audit_service.OpenAI"):
            MockG.return_value.chat.completions.create.return_value = mock_resp
            client.post(f"/copies/{copy_id}/grade")
            r2 = client.post(f"/copies/{copy_id}/grade?force=true")

        assert r2.status_code == 200
        assert r2.json()["status"] == "corrected"


# ─── report endpoint ──────────────────────────────────────────────────────────


class TestReportEndpoint:
    def test_report_404_unknown_copy(self, client):
        r = client.get("/copies/00000000-0000-0000-0000-000000000000/report")
        assert r.status_code == 404

    def test_report_409_not_corrected(self, client, cleanup_ids, unique_title):
        exam_id = _setup_exam_with_rubric(client, cleanup_ids, unique_title)
        pdf = _make_pdf_bytes()
        r = client.post(
            "/copies",
            data={"exam_id": exam_id},
            files={"file": ("c.pdf", pdf, "application/pdf")},
        )
        copy_id = r.json()["id"]

        r2 = client.get(f"/copies/{copy_id}/report")
        assert r2.status_code == 409
        assert r2.json()["detail"]["error"] == "not_corrected"

    def test_report_full_after_grade(self, client, cleanup_ids, unique_title):
        exam_id, copy_id = _setup_processed_copy(client, cleanup_ids, unique_title)
        _inject_transcription(copy_id, "f'(x) = 2x. Intégrale = x^3/3 + C")

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = (
            '{"points_awarded": 3, "confidence": 0.9, "needs_human_review": false,'
            ' "justification": "Correct", "criteria_details": []}'
        )

        with patch("app.services.grading_service.OpenAI") as MockG, patch("app.services.audit_service.OpenAI"):
            MockG.return_value.chat.completions.create.return_value = mock_resp
            client.post(f"/copies/{copy_id}/grade")

        r = client.get(f"/copies/{copy_id}/report")
        assert r.status_code == 200
        data = r.json()
        assert data["copy_id"] == copy_id
        assert data["student"]["name"] == "Alice Dupont"
        assert data["student"]["code"] == "A01"
        assert "score" in data
        assert "questions" in data
        assert "audit" in data
        assert data["score"]["total_max"] > 0


# ─── validate endpoint ────────────────────────────────────────────────────────


class TestValidateEndpoint:
    def _get_correction_id(self, copy_id: str) -> str:
        from uuid import UUID

        from app.core.database import SessionLocal
        from app.models.correction import Correction

        db = SessionLocal()
        try:
            c = db.query(Correction).filter(Correction.copy_id == UUID(copy_id)).first()
            return str(c.id) if c else None
        finally:
            db.close()

    def test_validate_marks_human_review_done(self, client, cleanup_ids, unique_title):
        exam_id, copy_id = _setup_processed_copy(client, cleanup_ids, unique_title)
        _inject_transcription(copy_id, "réponse test")

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = (
            '{"points_awarded": 1, "confidence": 0.3, "needs_human_review": true,'
            ' "justification": "Illisible", "criteria_details": []}'
        )

        with patch("app.services.grading_service.OpenAI") as MockG, patch("app.services.audit_service.OpenAI"):
            MockG.return_value.chat.completions.create.return_value = mock_resp
            client.post(f"/copies/{copy_id}/grade")

        correction_id = self._get_correction_id(copy_id)
        assert correction_id is not None

        r = client.patch(f"/corrections/{correction_id}/validate?points_awarded=2")
        assert r.status_code == 200
        data = r.json()
        assert data["validated_by_human"] is True
        assert data["needs_human_review"] is False
        assert float(data["points_awarded"]) == 2.0

    def test_validate_404_unknown(self, client):
        r = client.patch("/corrections/00000000-0000-0000-0000-000000000000/validate")
        assert r.status_code == 404

    def test_validate_rejects_over_max(self, client, cleanup_ids, unique_title):
        exam_id, copy_id = _setup_processed_copy(client, cleanup_ids, unique_title)
        _inject_transcription(copy_id, "réponse")

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = (
            '{"points_awarded": 2, "confidence": 0.5, "needs_human_review": true,'
            ' "justification": "ok", "criteria_details": []}'
        )

        with patch("app.services.grading_service.OpenAI") as MockG, patch("app.services.audit_service.OpenAI"):
            MockG.return_value.chat.completions.create.return_value = mock_resp
            client.post(f"/copies/{copy_id}/grade")

        correction_id = self._get_correction_id(copy_id)
        r = client.patch(f"/corrections/{correction_id}/validate?points_awarded=999")
        assert r.status_code == 400


# ─── bilan endpoint ───────────────────────────────────────────────────────────


class TestBilanEndpoint:
    def test_bilan_no_corrected_copies(self, client, cleanup_ids, unique_title):
        exam_id = _setup_exam_with_rubric(client, cleanup_ids, unique_title)
        r = client.get(f"/exams/{exam_id}/bilan")
        assert r.status_code == 200
        data = r.json()
        assert data["corrected_copies"] == 0
        assert "message" in data

    def test_bilan_404_unknown_exam(self, client):
        r = client.get("/exams/00000000-0000-0000-0000-000000000000/bilan")
        assert r.status_code == 404

    def test_bilan_stats_after_grading(self, client, cleanup_ids, unique_title):
        exam_id, copy_id = _setup_processed_copy(client, cleanup_ids, unique_title)
        _inject_transcription(copy_id, "réponse correcte")

        mock_resp = MagicMock()
        mock_resp.choices = [MagicMock()]
        mock_resp.choices[0].message.content = (
            '{"points_awarded": 4, "confidence": 0.9, "needs_human_review": false,'
            ' "justification": "ok", "criteria_details": []}'
        )

        with patch("app.services.grading_service.OpenAI") as MockG, patch("app.services.audit_service.OpenAI"):
            MockG.return_value.chat.completions.create.return_value = mock_resp
            client.post(f"/copies/{copy_id}/grade")

        r = client.get(f"/exams/{exam_id}/bilan")
        assert r.status_code == 200
        data = r.json()
        assert data["corrected_copies"] == 1
        assert "stats" in data
        assert data["stats"]["average"] > 0
        assert len(data["students"]) == 1
        assert "distribution_over_20" in data
