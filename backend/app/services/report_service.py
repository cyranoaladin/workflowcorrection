from __future__ import annotations

import logging
from datetime import UTC, datetime

logger = logging.getLogger(__name__)


def build_report(
    copy_id: str,
    student_name: str | None,
    copy_code: str | None,
    exam_title: str,
    exam_total_points: float,
    corrections: list[dict],
    audit: dict,
) -> dict:
    """
    Build a full correction report for a student copy.

    Returns a structured dict suitable for API response and PDF generation.
    """
    graded = [c for c in corrections if c.get("status") == "ok" and c.get("points_awarded") is not None]
    errors = [c for c in corrections if c.get("status") == "error"]

    total_awarded = sum(float(c["points_awarded"]) for c in graded)
    total_max = sum(float(c["points_max"]) for c in corrections)

    percentage = round((total_awarded / total_max * 100), 1) if total_max > 0 else 0.0
    grade_over_20 = round(total_awarded / total_max * 20, 2) if total_max > 0 else 0.0

    mention = _compute_mention(percentage)

    per_question = []
    for c in corrections:
        per_question.append(
            {
                "id": c.get("id"),
                "question_id": c.get("question_id"),
                "points_max": c.get("points_max"),
                "points_awarded": c.get("points_awarded"),
                "percentage": (
                    round(float(c["points_awarded"]) / float(c["points_max"]) * 100, 1)
                    if c.get("points_awarded") is not None and c.get("points_max")
                    else None
                ),
                "confidence": c.get("confidence"),
                "needs_human_review": c.get("needs_human_review", True),
                "validated_by_human": c.get("validated_by_human", False),
                "justification": c.get("justification", ""),
                "criteria_details": c.get("criteria_details", []),
                "status": c.get("status"),
                "error_message": c.get("error_message"),
            }
        )

    return {
        "copy_id": copy_id,
        "generated_at": datetime.now(tz=UTC).isoformat(),
        "student": {
            "name": student_name,
            "code": copy_code,
        },
        "exam": {
            "title": exam_title,
            "total_points": exam_total_points,
        },
        "score": {
            "total_awarded": round(total_awarded, 2),
            "total_max": round(total_max, 2),
            "percentage": percentage,
            "grade_over_20": grade_over_20,
            "mention": mention,
        },
        "questions": per_question,
        "graded_count": len(graded),
        "error_count": len(errors),
        "audit": audit,
        "needs_human_review": audit.get("needs_human_review", True),
        "status": "ok",
    }


def _compute_mention(percentage: float) -> str:
    if percentage >= 90:
        return "Très bien"
    if percentage >= 75:
        return "Bien"
    if percentage >= 60:
        return "Assez bien"
    if percentage >= 50:
        return "Passable"
    return "Insuffisant"
