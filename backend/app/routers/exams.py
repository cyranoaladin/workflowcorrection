from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.storage import StorageError, get_storage
from app.core.upload_validation import UploadValidationError, validate_pdf_upload
from app.models.exam import Exam
from app.schemas.exam_schema import ExamCreate, ExamRead

from app.core.database import get_db

router = APIRouter(prefix="/exams", tags=["exams"])


@router.post("", response_model=ExamRead)
def create_exam(payload: ExamCreate, db: Session = Depends(get_db)) -> Exam:
    exam = Exam(title=payload.title, level=payload.level, session=payload.session)
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.get("", response_model=list[ExamRead])
def list_exams(db: Session = Depends(get_db)) -> list[Exam]:
    return db.query(Exam).order_by(Exam.created_at.desc()).all()


@router.get("/{exam_id}", response_model=ExamRead)
def get_exam(exam_id: UUID, db: Session = Depends(get_db)) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    return exam


@router.post("/{exam_id}/files", response_model=ExamRead)
def upload_exam_files(
    exam_id: UUID,
    db: Session = Depends(get_db),
    subject_pdf: UploadFile | None = File(default=None),
    correction_pdf: UploadFile | None = File(default=None),
    rubric_pdf: UploadFile | None = File(default=None),
    rubric_tex: str | None = Form(default=None),
) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    storage = get_storage()
    settings = get_settings()

    if subject_pdf is not None:
        try:
            validate_pdf_upload(subject_pdf)
        except UploadValidationError as e:
            raise HTTPException(status_code=415, detail={"error": e.code, "message": e.message})
        try:
            stored = storage.save_upload(subject_pdf, f"exams/{exam_id}/subject.pdf", max_bytes=settings.max_upload_bytes)
        except StorageError as e:
            raise HTTPException(status_code=413, detail={"error": "upload_error", "message": str(e)})
        exam.subject_pdf_path = stored.relative_path

    if correction_pdf is not None:
        try:
            validate_pdf_upload(correction_pdf)
        except UploadValidationError as e:
            raise HTTPException(status_code=415, detail={"error": e.code, "message": e.message})
        try:
            stored = storage.save_upload(
                correction_pdf, f"exams/{exam_id}/correction.pdf", max_bytes=settings.max_upload_bytes
            )
        except StorageError as e:
            raise HTTPException(status_code=413, detail={"error": "upload_error", "message": str(e)})
        exam.correction_pdf_path = stored.relative_path

    if rubric_pdf is not None:
        try:
            validate_pdf_upload(rubric_pdf)
        except UploadValidationError as e:
            raise HTTPException(status_code=415, detail={"error": e.code, "message": e.message})
        try:
            stored = storage.save_upload(rubric_pdf, f"exams/{exam_id}/rubric.pdf", max_bytes=settings.max_upload_bytes)
        except StorageError as e:
            raise HTTPException(status_code=413, detail={"error": "upload_error", "message": str(e)})
        exam.rubric_pdf_path = stored.relative_path

    if rubric_tex is not None and rubric_tex.strip():
        tex_rel = f"exams/{exam_id}/rubric.tex"
        storage.save_bytes(rubric_tex.encode("utf-8"), tex_rel)
        exam.rubric_json = {**(exam.rubric_json or {}), "rubric_tex_path": tex_rel}

    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam
