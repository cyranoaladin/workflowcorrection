from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.copy import CopyStatus, StudentCopy
from app.models.correction import Correction
from app.models.exam import Exam
from app.models.transcription import Transcription
from app.schemas.correction_schema import CorrectionRead
from app.services.audit_service import audit_correction
from app.services.grading_service import grade_question
from app.services.report_service import build_report

router = APIRouter(tags=["corrections"])


def _to_float(value: object, fallback: float | None = None) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _rubric_total_points(rubric_questions: list[dict]) -> float:
    return sum(_to_float(q.get("points_max"), 0.0) or 0.0 for q in rubric_questions)


def _exam_total_points(exam: Exam | None, rubric_questions: list[dict]) -> float:
    exam_total = _to_float(exam.total_points if exam else None)
    return exam_total if exam_total and exam_total > 0 else _rubric_total_points(rubric_questions)


# ── POST /copies/{copy_id}/grade ─────────────────────────────────────────────
@router.post("/copies/{copy_id}/grade")
def grade_copy(
    copy_id: UUID,
    force: bool = Query(default=False, description="Re-grade even if already corrected"),
    db: Session = Depends(get_db),
) -> dict:
    """
    Grade all questions of a copy using LLM + rubric_json.

    Requires:
    - Copy status = processed_pages (OCR must have run first)
    - Exam must have rubric_json defined
    - OPENAI_API_KEY must be set in .env
    """
    copy = db.get(StudentCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")

    if copy.status == CopyStatus.corrected.value and not force:
        return {
            "copy_id": str(copy_id),
            "status": "already_corrected",
            "message": "Copy already graded. Use force=true to re-grade.",
        }

    if copy.status not in (
        CopyStatus.processed_pages.value,
        CopyStatus.corrected.value,
        CopyStatus.ocr_pending.value,
    ):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "invalid_status",
                "message": f"Copy status is '{copy.status}'. Must be processed_pages or ocr_pending to grade.",
            },
        )

    exam: Exam = db.get(Exam, copy.exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    rubric_questions: list[dict] = []
    if exam.rubric_json:
        rubric_questions = exam.rubric_json.get("questions", [])

    if not rubric_questions:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "no_rubric",
                "message": "Exam has no rubric_json with questions. Upload a rubric first.",
            },
        )

    # Gather all transcriptions for this copy (concatenated per page)
    transcriptions = (
        db.query(Transcription).filter(Transcription.copy_id == copy_id).order_by(Transcription.created_at.desc()).all()
    )

    full_transcription = "\n\n".join(
        t.final_text or t.raw_text or "" for t in transcriptions if (t.final_text or t.raw_text)
    )

    if not full_transcription.strip():
        raise HTTPException(
            status_code=409,
            detail={
                "error": "no_transcription",
                "message": "No OCR transcription found for this copy. Run OCR first.",
            },
        )

    # Delete previous corrections if force
    if force:
        db.query(Correction).filter(Correction.copy_id == copy_id).delete(synchronize_session=False)
        db.flush()

    grading_results: list[dict] = []
    persisted_total = Decimal("0")
    exam_total_points = _exam_total_points(exam, rubric_questions)

    for q in rubric_questions:
        qid = str(q.get("id", "unknown"))
        q_points_max = _to_float(q.get("points_max"), 0.0) or 0.0
        result = grade_question(qid, q, full_transcription, exam_id=str(exam.id)) or {}
        if not isinstance(result, dict):
            result = {}

        points_max = _to_float(result.get("points_max"), q_points_max) or q_points_max
        points_awarded = _to_float(result.get("points_awarded"))
        confidence = _to_float(result.get("confidence"), 0.0) or 0.0

        normalized = {
            "question_id": qid,
            "points_max": points_max,
            "points_awarded": points_awarded,
            "confidence": confidence,
            "needs_human_review": result.get("needs_human_review", True),
            "justification": result.get("justification", ""),
            "criteria_details": result.get("criteria_details", []),
            "error_message": result.get("error_message"),
            "status": result.get("status") or ("ok" if points_awarded is not None else "error"),
        }
        grading_results.append(normalized)

        if points_awarded is not None:
            awarded = Decimal(str(points_awarded))
            corr = Correction(
                copy_id=copy_id,
                question_id=qid,
                points_max=Decimal(str(points_max)),
                points_awarded=awarded,
                correction_json={
                    "justification": normalized["justification"],
                    "criteria_details": normalized["criteria_details"],
                    "error_message": normalized["error_message"],
                    "status": normalized["status"],
                },
                confidence=Decimal(str(confidence)),
                needs_human_review=normalized["needs_human_review"],
            )
            db.add(corr)
            persisted_total += awarded

    db.flush()

    # Audit
    audit = audit_correction(
        corrections=grading_results,
        total_points=exam_total_points,
        rubric_questions=rubric_questions,
    )

    copy.total_score = persisted_total
    copy.confidence = Decimal(str(audit.get("overall_confidence", 0)))
    copy.status = CopyStatus.corrected.value
    db.add(copy)
    db.commit()

    return {
        "copy_id": str(copy_id),
        "status": "corrected",
        "total_awarded": float(persisted_total),
        "total_max": exam_total_points,
        "questions_graded": len(grading_results),
        "audit": audit,
        "corrections": grading_results,
    }


# ── GET /copies/{copy_id}/report ──────────────────────────────────────────────
@router.get("/copies/{copy_id}/report")
def get_report(copy_id: UUID, db: Session = Depends(get_db)) -> dict:
    """Full correction report for a copy."""
    copy = db.get(StudentCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")

    if copy.status != CopyStatus.corrected.value:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "not_corrected",
                "message": f"Copy not yet corrected (status: {copy.status}). Run POST /copies/{copy_id}/grade first.",
            },
        )

    exam: Exam = db.get(Exam, copy.exam_id)
    corrections_db = db.query(Correction).filter(Correction.copy_id == copy_id).order_by(Correction.question_id).all()

    corrections_list = [
        {
            "id": str(c.id),
            "question_id": c.question_id,
            "points_max": float(c.points_max),
            "points_awarded": float(c.points_awarded) if c.points_awarded is not None else None,
            "confidence": float(c.confidence) if c.confidence is not None else None,
            "needs_human_review": c.needs_human_review,
            "validated_by_human": c.validated_by_human,
            "justification": c.correction_json.get("justification", ""),
            "criteria_details": c.correction_json.get("criteria_details", []),
            "status": "ok" if c.points_awarded is not None else "error",
        }
        for c in corrections_db
    ]

    rubric_questions = (exam.rubric_json or {}).get("questions", []) if exam else []
    exam_total_points = _exam_total_points(exam, rubric_questions)
    audit = audit_correction(
        corrections=corrections_list,
        total_points=exam_total_points,
        rubric_questions=rubric_questions,
    )

    return build_report(
        copy_id=str(copy_id),
        student_name=copy.student_name,
        copy_code=copy.copy_code,
        exam_title=exam.title if exam else "Examen inconnu",
        exam_total_points=exam_total_points,
        corrections=corrections_list,
        audit=audit,
    )


# ── PATCH /corrections/{correction_id}/validate ───────────────────────────────
@router.patch("/corrections/{correction_id}/validate", response_model=CorrectionRead)
def validate_correction(
    correction_id: UUID,
    points_awarded: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Correction:
    """Human validation of a graded question (optionally override score)."""
    corr = db.get(Correction, correction_id)
    if not corr:
        raise HTTPException(status_code=404, detail="Correction not found")

    if points_awarded is not None:
        try:
            parsed_points = float(points_awarded)
        except (ValueError, TypeError) as exc:
            raise HTTPException(status_code=400, detail="points_awarded must be a number") from exc

        if parsed_points < 0:
            raise HTTPException(
                status_code=400,
                detail=f"points_awarded ({parsed_points}) must be >= 0",
            )
        if parsed_points > float(corr.points_max):
            raise HTTPException(
                status_code=400,
                detail=f"points_awarded ({parsed_points}) exceeds points_max ({corr.points_max})",
            )
        corr.points_awarded = Decimal(str(parsed_points))

    corr.validated_by_human = True
    corr.needs_human_review = False
    db.add(corr)

    # Recompute copy total score
    all_corr = db.query(Correction).filter(Correction.copy_id == corr.copy_id).all()
    new_total = sum(float(c.points_awarded) for c in all_corr if c.points_awarded is not None)
    copy = db.get(StudentCopy, corr.copy_id)
    if copy:
        copy.total_score = Decimal(str(new_total))
        db.add(copy)

    db.commit()
    db.refresh(corr)
    return corr


# ── GET /exams/{exam_id}/bilan ────────────────────────────────────────────────
@router.get("/exams/{exam_id}/bilan")
def get_exam_bilan(exam_id: UUID, db: Session = Depends(get_db)) -> dict:
    """Class summary: stats across all corrected copies of an exam."""
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    copies = db.query(StudentCopy).filter(StudentCopy.exam_id == exam_id).all()
    corrected = [c for c in copies if c.status == CopyStatus.corrected.value and c.total_score is not None]

    if not corrected:
        return {
            "exam_id": str(exam_id),
            "exam_title": exam.title,
            "total_copies": len(copies),
            "corrected_copies": 0,
            "message": "Aucune copie corrigée pour cet examen.",
        }

    scores = [float(c.total_score) for c in corrected]
    rubric_questions = (exam.rubric_json or {}).get("questions", [])
    total_max = _exam_total_points(exam, rubric_questions)

    scores_20 = [round(s / total_max * 20, 2) for s in scores]

    avg = round(sum(scores) / len(scores), 2)
    avg_20 = round(sum(scores_20) / len(scores_20), 2)
    minimum = round(min(scores), 2)
    maximum = round(max(scores), 2)
    median = round(sorted(scores)[len(scores) // 2], 2)

    distribution = {"<5": 0, "5-9": 0, "10-12": 0, "13-15": 0, "16-18": 0, "19-20": 0}
    for s20 in scores_20:
        if s20 < 5:
            distribution["<5"] += 1
        elif s20 < 10:
            distribution["5-9"] += 1
        elif s20 < 13:
            distribution["10-12"] += 1
        elif s20 < 16:
            distribution["13-15"] += 1
        elif s20 < 19:
            distribution["16-18"] += 1
        else:
            distribution["19-20"] += 1

    students = sorted(
        [
            {
                "copy_id": str(c.id),
                "student_name": c.student_name,
                "copy_code": c.copy_code,
                "score": float(c.total_score),
                "score_over_20": round(float(c.total_score) / total_max * 20, 2),
                "needs_human_review": any(
                    corr.needs_human_review for corr in db.query(Correction).filter(Correction.copy_id == c.id).all()
                ),
            }
            for c in corrected
        ],
        key=lambda x: x["score"],
        reverse=True,
    )

    return {
        "exam_id": str(exam_id),
        "exam_title": exam.title,
        "total_points": total_max,
        "total_copies": len(copies),
        "corrected_copies": len(corrected),
        "pending_copies": len(copies) - len(corrected),
        "stats": {
            "average": avg,
            "average_over_20": avg_20,
            "min": minimum,
            "max": maximum,
            "median": median,
        },
        "distribution_over_20": distribution,
        "students": students,
    }
