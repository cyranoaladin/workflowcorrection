from __future__ import annotations

import csv
import io
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Body, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.storage import StorageError, get_storage
from app.core.upload_validation import UploadValidationError, validate_pdf_upload
from app.models.copy import CopyStatus, StudentCopy
from app.models.exam import Exam
from app.schemas.exam_schema import ExamCreate, ExamRead, ExamUpdate

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
            raise HTTPException(status_code=415, detail={"error": e.code, "message": e.message}) from e
        try:
            stored = storage.save_upload(
                subject_pdf,
                f"exams/{exam_id}/subject.pdf",
                max_bytes=settings.max_upload_bytes,
            )
        except StorageError as e:
            raise HTTPException(status_code=413, detail={"error": "upload_error", "message": str(e)}) from e
        exam.subject_pdf_path = stored.relative_path

    if correction_pdf is not None:
        try:
            validate_pdf_upload(correction_pdf)
        except UploadValidationError as e:
            raise HTTPException(status_code=415, detail={"error": e.code, "message": e.message}) from e
        try:
            stored = storage.save_upload(
                correction_pdf,
                f"exams/{exam_id}/correction.pdf",
                max_bytes=settings.max_upload_bytes,
            )
        except StorageError as e:
            raise HTTPException(status_code=413, detail={"error": "upload_error", "message": str(e)}) from e
        exam.correction_pdf_path = stored.relative_path

    if rubric_pdf is not None:
        try:
            validate_pdf_upload(rubric_pdf)
        except UploadValidationError as e:
            raise HTTPException(status_code=415, detail={"error": e.code, "message": e.message}) from e
        try:
            stored = storage.save_upload(
                rubric_pdf,
                f"exams/{exam_id}/rubric.pdf",
                max_bytes=settings.max_upload_bytes,
            )
        except StorageError as e:
            raise HTTPException(status_code=413, detail={"error": "upload_error", "message": str(e)}) from e
        exam.rubric_pdf_path = stored.relative_path

    if rubric_tex is not None and rubric_tex.strip():
        tex_rel = f"exams/{exam_id}/rubric.tex"
        storage.save_bytes(rubric_tex.encode("utf-8"), tex_rel)
        exam.rubric_json = {**(exam.rubric_json or {}), "rubric_tex_path": tex_rel}

    rag_relevant_upload = correction_pdf is not None or rubric_pdf is not None
    should_queue_embedding = rag_relevant_upload and _mark_embedding_queued_if_ready(exam)
    db.add(exam)
    db.commit()
    if should_queue_embedding:
        try:
            _queue_embedding(exam.id)
        except Exception:
            # Broker failure — rollback the queued status so we don't leave a
            # permanently stale "queued" state.
            metadata = dict(exam.metadata_json or {})
            metadata.pop("embedding_status", None)
            metadata.pop("embedded_queued_at", None)
            exam.metadata_json = metadata
            db.add(exam)
            db.commit()
    db.refresh(exam)
    return exam


@router.patch("/{exam_id}", response_model=ExamRead)
def update_exam(
    exam_id: UUID,
    payload: ExamUpdate,
    db: Session = Depends(get_db),
) -> Exam:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")
    if payload.title is not None:
        exam.title = payload.title
    if payload.level is not None:
        exam.level = payload.level
    if payload.session is not None:
        exam.session = payload.session
    if payload.total_points is not None:
        exam.total_points = payload.total_points
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.post("/{exam_id}/rubric-json", response_model=ExamRead)
def set_rubric_json(
    exam_id: UUID,
    rubric: dict = Body(
        ...,
        example={
            "questions": [
                {
                    "id": "Q1",
                    "label": "Calculer la dérivée",
                    "points_max": 4,
                    "criteria": ["Méthode correcte", "Résultat exact"],
                }
            ]
        },
    ),
    db: Session = Depends(get_db),
) -> Exam:
    """
    Set or replace the structured rubric JSON for an exam.
    Expected format: {"questions": [{"id": str, "label": str, "points_max": float, "criteria": list[str], "expected_answer": str (optional)}]}
    This is required before running LLM grading.
    """
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    questions = rubric.get("questions", [])
    if not isinstance(questions, list) or not questions:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "invalid_rubric",
                "message": "rubric must contain a non-empty 'questions' list",
            },
        )
    for i, q in enumerate(questions):
        if not isinstance(q, dict):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "invalid_question",
                    "message": f"Question {i} must be an object",
                },
            )
        if not q.get("id"):
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "missing_question_id",
                    "message": f"Question {i} missing 'id'",
                },
            )
        if q.get("points_max") is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "missing_points_max",
                    "message": f"Question {q.get('id')} missing 'points_max'",
                },
            )

    exam.rubric_json = rubric
    should_queue_embedding = _mark_embedding_queued_if_ready(exam)
    db.add(exam)
    db.commit()
    if should_queue_embedding:
        try:
            _queue_embedding(exam.id)
        except Exception:
            metadata = dict(exam.metadata_json or {})
            metadata.pop("embedding_status", None)
            metadata.pop("embedded_queued_at", None)
            exam.metadata_json = metadata
            db.add(exam)
            db.commit()
    db.refresh(exam)
    return exam


def _mark_embedding_queued_if_ready(exam: Exam) -> bool:
    if not (exam.correction_pdf_path and exam.rubric_json):
        return False

    metadata = dict(exam.metadata_json or {})
    metadata["embedding_status"] = "queued"
    metadata["embedded_queued_at"] = datetime.now(UTC).isoformat()
    exam.metadata_json = metadata
    return True


def _queue_embedding(exam_id: UUID) -> None:
    from app.workers.embed_tasks import embed_exam_task

    embed_exam_task.delay(str(exam_id), force=False)


@router.post("/{exam_id}/students/csv")
def import_students_csv(
    exam_id: UUID,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """
    Import a student list from a CSV file for an exam.

    Expected CSV columns (order does not matter, header required):
      student_name  — full name of the student
      copy_code     — unique identifier / seat number (optional column)

    Creates a StudentCopy per row with status=registered and no PDF yet.
    The PDF can be uploaded later via POST /copies.
    Skips rows where both student_name and copy_code are empty.
    Returns {"created": N, "skipped": N, "errors": [...]}
    """
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    if file.content_type not in (
        "text/csv",
        "text/plain",
        "application/csv",
        "application/octet-stream",
    ):
        content_type = file.content_type or ""
        if not content_type.startswith("text/"):
            raise HTTPException(
                status_code=415,
                detail={"error": "invalid_file_type", "message": "File must be a CSV"},
            )

    raw = file.file.read()
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = raw.decode("latin-1")
        except UnicodeDecodeError as exc:
            raise HTTPException(
                status_code=422,
                detail={
                    "error": "encoding_error",
                    "message": "Cannot decode CSV file. Use UTF-8 or Latin-1 encoding.",
                },
            ) from exc

    reader = csv.DictReader(io.StringIO(text))

    normalized_headers = [h.strip().lower() for h in (reader.fieldnames or [])]
    if "student_name" not in normalized_headers and "nom" not in normalized_headers:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "missing_column",
                "message": "CSV must have a 'student_name' column (or 'nom' in French). Optional: 'copy_code'.",
            },
        )

    created = 0
    skipped = 0
    errors: list[dict] = []

    for _i, row in enumerate(reader, start=2):
        clean = {
            (k or "").strip().lower(): str(v).strip() if v is not None and not isinstance(v, list) else ""
            for k, v in row.items()
        }

        student_name = clean.get("student_name") or clean.get("nom") or ""
        copy_code = clean.get("copy_code") or clean.get("code") or ""

        if not student_name and not copy_code:
            skipped += 1
            continue

        copy = StudentCopy(
            exam_id=exam_id,
            student_name=student_name or None,
            copy_code=copy_code or None,
            original_pdf_path="pending",
            status=CopyStatus.uploaded.value,
        )
        db.add(copy)
        created += 1

    db.commit()
    return {"created": created, "skipped": skipped, "errors": errors}
