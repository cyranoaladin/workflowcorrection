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

    if copy.status not in (CopyStatus.processed_pages.value, CopyStatus.corrected.value, CopyStatus.ocr_pending.value):
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
        db.query(Transcription)
        .filter(Transcription.copy_id == copy_id)
        .order_by(Transcription.created_at.desc())
        .all()
    )

    full_transcription = "\n\n".join(
        t.final_text or t.raw_text or ""
        for t in transcriptions
        if (t.final_text or t.raw_text)
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
        db.commit()

    grading_results: list[dict] = []
    for q in rubric_questions:
        qid = str(q.get("id", "unknown"))
        result = grade_question(qid, q, full_transcription)
        grading_results.append(result)

        if result.get("status") == "ok" and result.get("points_awarded") is not None:
            corr = Correction(
                copy_id=copy_id,
                question_id=qid,
                points_max=Decimal(str(result["points_max"])),
                points_awarded=Decimal(str(result["points_awarded"])),
                correction_json={
                    "justification": result.get("justification", ""),
                    "criteria_details": result.get("criteria_details", []),
                    "error_message": result.get("error_message"),
                },
                confidence=Decimal(str(result.get("confidence", 0))),
                needs_human_review=result.get("needs_human_review", True),
            )
            db.add(corr)

    db.flush()

    # Audit
    audit = audit_correction(
        corrections=grading_results,
        total_points=float(exam.total_points),
        rubric_questions=rubric_questions,
    )

    # Compute total score
    total_awarded = sum(
        float(r["points_awarded"])
        for r in grading_results
        if r.get("status") == "ok" and r.get("points_awarded") is not None
    )
    copy.total_score = Decimal(str(total_awarded))
    copy.confidence = Decimal(str(audit.get("overall_confidence", 0)))
    copy.status = CopyStatus.corrected.value
    db.add(copy)
    db.commit()

    return {
        "copy_id": str(copy_id),
        "status": "corrected",
        "total_awarded": total_awarded,
        "total_max": float(exam.total_points),
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
    corrections_db = (
        db.query(Correction)
        .filter(Correction.copy_id == copy_id)
        .order_by(Correction.question_id)
        .all()
    )

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
    audit = audit_correction(
        corrections=corrections_list,
        total_points=float(exam.total_points) if exam else 20.0,
        rubric_questions=rubric_questions,
    )

    return build_report(
        copy_id=str(copy_id),
        student_name=copy.student_name,
        copy_code=copy.copy_code,
        exam_title=exam.title if exam else "Examen inconnu",
        exam_total_points=float(exam.total_points) if exam else 20.0,
        corrections=corrections_list,
        audit=audit,
    )


# ── PATCH /corrections/{correction_id}/validate ───────────────────────────────
@router.patch("/corrections/{correction_id}/validate", response_model=CorrectionRead)
def validate_correction(
    correction_id: UUID,
    points_awarded: float | None = Query(default=None),
    db: Session = Depends(get_db),
) -> Correction:
    """Human validation of a graded question (optionally override score)."""
    corr = db.get(Correction, correction_id)
    if not corr:
        raise HTTPException(status_code=404, detail="Correction not found")

    if points_awarded is not None:
        if points_awarded < 0:
            raise HTTPException(
                status_code=400,
                detail=f"points_awarded ({points_awarded}) must be >= 0",
            )
        if points_awarded > float(corr.points_max):
            raise HTTPException(
                status_code=400,
                detail=f"points_awarded ({points_awarded}) exceeds points_max ({corr.points_max})",
            )
        corr.points_awarded = Decimal(str(points_awarded))

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
    total_max = float(exam.total_points)

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
                    corr.needs_human_review
                    for corr in db.query(Correction).filter(Correction.copy_id == c.id).all()
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

