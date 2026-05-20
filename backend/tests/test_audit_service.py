"""Tests for audit_service — adversarial edge cases.

All rule-based tests patch OPENAI_API_KEY to empty so that the LLM-as-judge
path is skipped (conftest sets it to "sk-test" which is truthy but invalid).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from app.services.audit_service import audit_correction


@pytest.fixture(autouse=True)
def _disable_llm_audit():
    """Disable LLM audit calls — test only rule-based checks."""
    with patch("app.services.audit_service.get_settings") as mock_settings:
        mock_settings.return_value.OPENAI_API_KEY = ""
        mock_settings.return_value.OPENAI_AUDIT_MODEL = "gpt-4.1-mini"
        mock_settings.return_value.OPENAI_BASE_URL = None
        yield


def _make_correction(
    question_id: str = "Q1",
    points_max: float = 4.0,
    points_awarded: float = 3.0,
    confidence: float = 0.9,
    status: str = "ok",
    needs_human_review: bool = False,
) -> dict:
    return {
        "question_id": question_id,
        "points_max": points_max,
        "points_awarded": points_awarded,
        "confidence": confidence,
        "status": status,
        "justification": "Test justification",
        "needs_human_review": needs_human_review,
    }


RUBRIC_Q1_Q2_Q3 = [
    {"id": "Q1", "label": "Q1", "points_max": 4},
    {"id": "Q2", "label": "Q2", "points_max": 6},
    {"id": "Q3", "label": "Q3", "points_max": 10},
]


class TestAuditFlagsLowConfidence:
    """Corrections with confidence < 0.5 should be flagged."""

    def test_flags_low_confidence(self):
        corrections = [
            _make_correction("Q1", confidence=0.3),
            _make_correction("Q2", points_max=6, points_awarded=5, confidence=0.8),
        ]
        rubric = [{"id": "Q1", "points_max": 4}, {"id": "Q2", "points_max": 6}]

        result = audit_correction(corrections, total_points=10, rubric_questions=rubric)

        assert result["status"] == "ok"
        assert any("low_confidence" in f and "Q1" in f for f in result["flags"])
        assert result["needs_human_review"] is True

    def test_all_low_confidence(self):
        corrections = [
            _make_correction("Q1", confidence=0.2),
            _make_correction("Q2", points_max=6, points_awarded=4, confidence=0.1),
        ]
        rubric = [{"id": "Q1", "points_max": 4}, {"id": "Q2", "points_max": 6}]

        result = audit_correction(corrections, total_points=10, rubric_questions=rubric)

        low_flags = [f for f in result["flags"] if "low_confidence" in f]
        assert len(low_flags) == 2
        assert result["needs_human_review"] is True


class TestAuditFlagsTotalExceedsMax:
    """Total awarded points exceeding max should be flagged."""

    def test_total_exceeds_max(self):
        corrections = [
            _make_correction("Q1", points_max=4, points_awarded=6),
            _make_correction("Q2", points_max=4, points_awarded=6),
        ]
        rubric = [{"id": "Q1", "points_max": 4}, {"id": "Q2", "points_max": 4}]

        result = audit_correction(corrections, total_points=8, rubric_questions=rubric)

        assert any("total_exceeds_max" in f for f in result["flags"])
        assert "12" in str(result["flags"])  # 6+6 = 12 > 8
        assert result["audit_passed"] is False

    def test_exact_max_no_flag(self):
        corrections = [
            _make_correction("Q1", points_max=4, points_awarded=4),
            _make_correction("Q2", points_max=4, points_awarded=4),
        ]
        rubric = [{"id": "Q1", "points_max": 4}, {"id": "Q2", "points_max": 4}]

        result = audit_correction(corrections, total_points=8, rubric_questions=rubric)

        assert not any("total_exceeds_max" in f for f in result["flags"])


class TestAuditFlagsMissingGrade:
    """Missing question grades should be detected."""

    def test_missing_grade(self):
        corrections = [_make_correction("Q1")]
        result = audit_correction(corrections, total_points=20, rubric_questions=RUBRIC_Q1_Q2_Q3)

        missing_flags = [f for f in result["flags"] if "missing_grade" in f]
        assert len(missing_flags) == 2  # Q2 and Q3 missing
        assert any("Q2" in f for f in missing_flags)
        assert any("Q3" in f for f in missing_flags)
        assert result["needs_human_review"] is True

    def test_all_graded_no_flag(self):
        corrections = [
            _make_correction("Q1"),
            _make_correction("Q2", points_max=6, points_awarded=5),
            _make_correction("Q3", points_max=10, points_awarded=8),
        ]
        result = audit_correction(corrections, total_points=20, rubric_questions=RUBRIC_Q1_Q2_Q3)

        assert not any("missing_grade" in f for f in result["flags"])


class TestAuditFlagsGradingError:
    """Error status corrections should be flagged."""

    def test_grading_error_flag(self):
        corrections = [
            _make_correction("Q1", status="error"),
        ]
        rubric = [{"id": "Q1", "points_max": 4}]

        result = audit_correction(corrections, total_points=4, rubric_questions=rubric)

        assert any("grading_error" in f for f in result["flags"])
        assert result["needs_human_review"] is True


class TestAuditCleanPass:
    """Clean corrections should pass without flags."""

    def test_clean_corrections_pass(self):
        corrections = [
            _make_correction("Q1", confidence=0.95),
            _make_correction("Q2", points_max=6, points_awarded=5, confidence=0.88),
        ]
        rubric = [{"id": "Q1", "points_max": 4}, {"id": "Q2", "points_max": 6}]

        result = audit_correction(corrections, total_points=10, rubric_questions=rubric)

        assert result["flags"] == []
        assert result["audit_passed"] is True
        assert result["needs_human_review"] is False


class TestAuditLLMFallback:
    """When LLM fails, rule-based results should still be returned."""

    @patch("app.services.audit_service.OpenAI")
    @patch("app.services.audit_service.get_settings")
    def test_llm_failure_returns_rule_based(self, mock_settings, mock_openai_cls):
        # Enable LLM path so we can test failure handling
        mock_settings.return_value.OPENAI_API_KEY = "sk-test-key"
        mock_settings.return_value.OPENAI_AUDIT_MODEL = "gpt-4.1-mini"
        mock_settings.return_value.OPENAI_BASE_URL = None
        mock_openai_cls.return_value.chat.completions.create.side_effect = Exception("API timeout")
        corrections = [
            _make_correction("Q1", confidence=0.3),
        ]
        rubric = [{"id": "Q1", "points_max": 4}]

        result = audit_correction(corrections, total_points=4, rubric_questions=rubric)

        assert result["status"] == "error"
        assert any("low_confidence" in f for f in result["flags"])
        assert result["needs_human_review"] is True
