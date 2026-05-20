"""
Phase 2 unit tests: grading_service, audit_service, report_service.
All LLM calls are mocked — no actual API calls are made.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

# ─────────────────────────────────────────────────────────────────────────────
# grading_service
# ─────────────────────────────────────────────────────────────────────────────


class TestGradingService:
    def test_returns_error_when_no_api_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        from app.core.config import get_settings

        get_settings.cache_clear()

        from app.services.grading_service import grade_question

        result = grade_question("Q1", {"id": "Q1", "label": "Test", "points_max": 4}, "some transcription")

        assert result["status"] == "error"
        assert result["error_message"] == "missing_openai_api_key"
        assert result["points_awarded"] is None
        assert result["needs_human_review"] is True

    def test_clamps_points_to_max(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from app.core.config import get_settings

        get_settings.cache_clear()

        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = (
            '{"points_awarded": 99, "confidence": 0.9, "needs_human_review": false,'
            ' "justification": "ok", "criteria_details": []}'
        )

        with patch("app.services.grading_service.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = fake_response
            from app.services.grading_service import grade_question

            result = grade_question("Q1", {"id": "Q1", "label": "Test", "points_max": 4}, "text")

        assert result["status"] == "ok"
        assert result["points_awarded"] == 4.0  # clamped to points_max

    def test_handles_valid_llm_response(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from app.core.config import get_settings

        get_settings.cache_clear()

        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = (
            '{"points_awarded": 3.5, "confidence": 0.85, "needs_human_review": false,'
            ' "justification": "Bonne réponse", "criteria_details": [{"criterion": "C1", "awarded": 2, "comment": "ok"}]}'
        )

        with patch("app.services.grading_service.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = fake_response
            from app.services.grading_service import grade_question

            result = grade_question("Q1", {"id": "Q1", "label": "Dériver", "points_max": 4}, "f'(x) = 2x")

        assert result["status"] == "ok"
        assert result["points_awarded"] == 3.5
        assert result["confidence"] == 0.85
        assert result["needs_human_review"] is False
        assert result["justification"] == "Bonne réponse"
        assert len(result["criteria_details"]) == 1

    def test_returns_error_on_invalid_json_from_llm(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from app.core.config import get_settings

        get_settings.cache_clear()

        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = "not json at all"

        with patch("app.services.grading_service.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = fake_response
            from app.services.grading_service import grade_question

            result = grade_question("Q1", {"id": "Q1", "label": "T", "points_max": 2}, "text")

        assert result["status"] == "error"
        assert "invalid_llm_json" in result["error_message"]
        assert result["needs_human_review"] is True

    def test_returns_error_on_llm_exception(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from app.core.config import get_settings

        get_settings.cache_clear()

        with patch("app.services.grading_service.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = RuntimeError("network error")
            from app.services.grading_service import grade_question

            result = grade_question("Q1", {"id": "Q1", "label": "T", "points_max": 5}, "text")

        assert result["status"] == "error"
        assert "RuntimeError" in result["error_message"]

    def test_points_max_zero_does_not_crash(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from app.core.config import get_settings

        get_settings.cache_clear()

        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = (
            '{"points_awarded": 0, "confidence": 1.0, "needs_human_review": false,'
            ' "justification": "ok", "criteria_details": []}'
        )

        with patch("app.services.grading_service.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = fake_response
            from app.services.grading_service import grade_question

            result = grade_question("Q0", {"id": "Q0", "label": "Bonus", "points_max": 0}, "text")

        assert result["status"] == "ok"
        assert result["points_awarded"] == 0.0

    def test_transcription_truncated_at_3000_chars(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from app.core.config import get_settings

        get_settings.cache_clear()

        captured = {}
        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = (
            '{"points_awarded": 1, "confidence": 0.7, "needs_human_review": true,'
            ' "justification": "ok", "criteria_details": []}'
        )

        def capture_call(*args, **kwargs):
            captured["prompt"] = kwargs["messages"][1]["content"]
            return fake_response

        with patch("app.services.grading_service.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = capture_call
            from app.services.grading_service import grade_question

            grade_question("Q1", {"id": "Q1", "label": "T", "points_max": 2}, "X" * 5000)

        assert len(captured.get("prompt", "")) < 4500  # truncated

    def test_uses_criteria_list_when_provided(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from app.core.config import get_settings

        get_settings.cache_clear()

        captured = {}
        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[0].message.content = (
            '{"points_awarded": 2, "confidence": 0.8, "needs_human_review": false,'
            ' "justification": "ok", "criteria_details": []}'
        )

        def capture_call(*args, **kwargs):
            captured["prompt"] = kwargs["messages"][1]["content"]
            return fake_response

        with patch("app.services.grading_service.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.side_effect = capture_call
            from app.services.grading_service import grade_question

            grade_question(
                "Q1",
                {
                    "id": "Q1",
                    "label": "T",
                    "points_max": 3,
                    "criteria": ["Crit A", "Crit B"],
                },
                "some answer",
            )

        assert "Crit A" in captured.get("prompt", "")
        assert "Crit B" in captured.get("prompt", "")


# ─────────────────────────────────────────────────────────────────────────────
# audit_service
# ─────────────────────────────────────────────────────────────────────────────


class TestAuditService:
    def _ok_correction(self, qid="Q1", points_max=4.0, points_awarded=3.0, confidence=0.9):
        return {
            "question_id": qid,
            "points_max": points_max,
            "points_awarded": points_awarded,
            "confidence": confidence,
            "needs_human_review": False,
            "status": "ok",
            "error_message": None,
        }

    def test_no_flags_on_clean_result(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        from app.core.config import get_settings

        get_settings.cache_clear()

        from app.services.audit_service import audit_correction

        result = audit_correction(
            corrections=[self._ok_correction()],
            total_points=20.0,
            rubric_questions=[{"id": "Q1"}],
        )
        assert result["flags"] == []
        assert result["audit_passed"] is True

    def test_flags_total_exceeds_max(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        from app.core.config import get_settings

        get_settings.cache_clear()

        from app.services.audit_service import audit_correction

        result = audit_correction(
            corrections=[self._ok_correction(points_awarded=25.0, points_max=4.0)],
            total_points=20.0,
            rubric_questions=[{"id": "Q1"}],
        )
        assert any("total_exceeds_max" in f for f in result["flags"])

    def test_flags_low_confidence(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        from app.core.config import get_settings

        get_settings.cache_clear()

        from app.services.audit_service import audit_correction

        c = self._ok_correction(confidence=0.3)
        result = audit_correction(
            corrections=[c],
            total_points=20.0,
            rubric_questions=[{"id": "Q1"}],
        )
        assert any("low_confidence" in f for f in result["flags"])

    def test_flags_grading_error(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        from app.core.config import get_settings

        get_settings.cache_clear()

        from app.services.audit_service import audit_correction

        bad = {
            "question_id": "Q1",
            "status": "error",
            "error_message": "missing_key",
            "points_max": 4,
            "points_awarded": None,
            "confidence": 0,
            "needs_human_review": True,
        }
        result = audit_correction(
            corrections=[bad],
            total_points=20.0,
            rubric_questions=[{"id": "Q1"}],
        )
        assert any("grading_error" in f for f in result["flags"])

    def test_flags_missing_question(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        from app.core.config import get_settings

        get_settings.cache_clear()

        from app.services.audit_service import audit_correction

        result = audit_correction(
            corrections=[self._ok_correction(qid="Q1")],
            total_points=20.0,
            rubric_questions=[{"id": "Q1"}, {"id": "Q2"}],
        )
        assert any("missing_grade" in f and "Q2" in f for f in result["flags"])

    def test_empty_corrections_returns_ok(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "")
        from app.core.config import get_settings

        get_settings.cache_clear()

        from app.services.audit_service import audit_correction

        result = audit_correction(corrections=[], total_points=20.0, rubric_questions=[])
        assert result["overall_confidence"] == 0.0
        assert result["status"] == "ok"

    def test_llm_audit_called_when_api_key_set(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        from app.core.config import get_settings

        get_settings.cache_clear()

        fake_response = MagicMock()
        fake_response.choices = [MagicMock()]
        fake_response.choices[
            0
        ].message.content = (
            '{"audit_passed": true, "additional_flags": [], "summary": "OK", "recommendation": "validate"}'
        )

        with patch("app.services.audit_service.OpenAI") as MockClient:
            MockClient.return_value.chat.completions.create.return_value = fake_response
            from app.services.audit_service import audit_correction

            result = audit_correction(
                corrections=[self._ok_correction()],
                total_points=20.0,
                rubric_questions=[{"id": "Q1"}],
            )

        assert result["audit_passed"] is True
        assert result["summary"] == "OK"
        assert result["recommendation"] == "validate"


# ─────────────────────────────────────────────────────────────────────────────
# report_service
# ─────────────────────────────────────────────────────────────────────────────


class TestReportService:
    def _make_correction(self, qid, points_max, points_awarded, confidence=0.9):
        return {
            "id": f"uuid-{qid}",
            "question_id": qid,
            "points_max": points_max,
            "points_awarded": points_awarded,
            "confidence": confidence,
            "needs_human_review": False,
            "validated_by_human": False,
            "justification": "test",
            "criteria_details": [],
            "status": "ok",
            "error_message": None,
        }

    def _audit(self):
        return {
            "audit_passed": True,
            "overall_confidence": 0.9,
            "needs_human_review": False,
            "flags": [],
            "summary": "OK",
        }

    def test_correct_score_calculation(self):
        from app.services.report_service import build_report

        corrections = [
            self._make_correction("Q1", 4, 3),
            self._make_correction("Q2", 6, 5),
        ]
        report = build_report(
            copy_id="c1",
            student_name="Alice",
            copy_code="A01",
            exam_title="Exam",
            exam_total_points=20.0,
            corrections=corrections,
            audit=self._audit(),
        )
        assert report["score"]["total_awarded"] == 8.0
        assert report["score"]["total_max"] == 10.0
        assert report["score"]["percentage"] == 80.0
        assert report["score"]["grade_over_20"] == 16.0

    def test_mention_tres_bien(self):
        from app.services.report_service import build_report

        corrections = [self._make_correction("Q1", 10, 9.5)]
        report = build_report(
            copy_id="c1",
            student_name=None,
            copy_code=None,
            exam_title="E",
            exam_total_points=10.0,
            corrections=corrections,
            audit=self._audit(),
        )
        assert report["score"]["mention"] == "Très bien"

    def test_mention_insuffisant(self):
        from app.services.report_service import build_report

        corrections = [self._make_correction("Q1", 10, 2)]
        report = build_report(
            copy_id="c1",
            student_name=None,
            copy_code=None,
            exam_title="E",
            exam_total_points=10.0,
            corrections=corrections,
            audit=self._audit(),
        )
        assert report["score"]["mention"] == "Insuffisant"

    def test_empty_corrections_doesnt_divide_by_zero(self):
        from app.services.report_service import build_report

        report = build_report(
            copy_id="c1",
            student_name=None,
            copy_code=None,
            exam_title="E",
            exam_total_points=20.0,
            corrections=[],
            audit=self._audit(),
        )
        assert report["score"]["total_awarded"] == 0.0
        assert report["score"]["percentage"] == 0.0
        assert report["score"]["grade_over_20"] == 0.0
        assert report["graded_count"] == 0

    def test_error_corrections_counted(self):
        from app.services.report_service import build_report

        bad = {
            "id": "x",
            "question_id": "Q1",
            "points_max": 4,
            "points_awarded": None,
            "confidence": 0,
            "needs_human_review": True,
            "validated_by_human": False,
            "justification": "",
            "criteria_details": [],
            "status": "error",
            "error_message": "fail",
        }
        report = build_report(
            copy_id="c1",
            student_name=None,
            copy_code=None,
            exam_title="E",
            exam_total_points=20.0,
            corrections=[bad],
            audit=self._audit(),
        )
        assert report["error_count"] == 1
        assert report["graded_count"] == 0

    def test_report_includes_student_info(self):
        from app.services.report_service import build_report

        corrections = [self._make_correction("Q1", 4, 3)]
        report = build_report(
            copy_id="test-id",
            student_name="Bob Martin",
            copy_code="B02",
            exam_title="Algèbre",
            exam_total_points=20.0,
            corrections=corrections,
            audit=self._audit(),
        )
        assert report["student"]["name"] == "Bob Martin"
        assert report["student"]["code"] == "B02"
        assert report["exam"]["title"] == "Algèbre"
        assert report["copy_id"] == "test-id"

    def test_question_percentage_computed(self):
        from app.services.report_service import build_report

        corrections = [self._make_correction("Q1", 8, 6)]
        report = build_report(
            copy_id="c1",
            student_name=None,
            copy_code=None,
            exam_title="E",
            exam_total_points=8.0,
            corrections=corrections,
            audit=self._audit(),
        )
        q = report["questions"][0]
        assert q["percentage"] == 75.0

    def test_id_and_validated_by_human_passthrough(self):
        from app.services.report_service import build_report

        c = self._make_correction("Q1", 4, 4)
        c["id"] = "correction-uuid-123"
        c["validated_by_human"] = True
        report = build_report(
            copy_id="c1",
            student_name=None,
            copy_code=None,
            exam_title="E",
            exam_total_points=4.0,
            corrections=[c],
            audit=self._audit(),
        )
        q = report["questions"][0]
        assert q["id"] == "correction-uuid-123"
        assert q["validated_by_human"] is True
