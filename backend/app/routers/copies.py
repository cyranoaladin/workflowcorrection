from __future__ import annotations

import uuid
from uuid import UUID

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.storage import StorageError, get_storage
from app.core.upload_validation import UploadValidationError, validate_pdf_upload
from app.models.copy import CopyStatus, StudentCopy
from app.models.exam import Exam
from app.models.page import CopyPage
from app.models.transcription import Transcription
from app.schemas.copy_schema import CopyRead
from app.schemas.page_schema import PageRead
from app.schemas.transcription_schema import TranscriptionRead
from app.services.azure_ocr_service import call_azure_read
from app.services.mathpix_service import call_mathpix_image
from app.services.openai_vision_service import call_openai_vision_for_transcription
from app.workers.celery_app import celery
from app.workers.tasks import grade_copy_task, process_copy

router = APIRouter(tags=["copies"])


@router.post("/copies", response_model=CopyRead)
def upload_copy(
    db: Session = Depends(get_db),
    exam_id: UUID = Form(...),
    student_name: str | None = Form(default=None),
    copy_code: str | None = Form(default=None),
    file: UploadFile = File(...),
) -> StudentCopy:
    exam = db.get(Exam, exam_id)
    if not exam:
        raise HTTPException(status_code=404, detail="Exam not found")

    storage = get_storage()
    settings = get_settings()

    try:
        validate_pdf_upload(file)
    except UploadValidationError as e:
        raise HTTPException(status_code=415, detail={"error": e.code, "message": e.message}) from e

    copy_id = uuid.uuid4()
    pdf_rel = f"copies/{copy_id}/original.pdf"
    try:
        stored = storage.save_upload(file, pdf_rel, max_bytes=settings.max_upload_bytes)
    except StorageError as e:
        raise HTTPException(status_code=413, detail={"error": "upload_error", "message": str(e)}) from e

    copy = StudentCopy(
        id=copy_id,
        exam_id=exam_id,
        student_name=student_name,
        copy_code=copy_code,
        original_pdf_path=stored.relative_path,
        status=CopyStatus.uploaded.value,
    )

    db.add(copy)
    db.commit()
    db.refresh(copy)
    return copy


@router.get("/copies", response_model=list[CopyRead])
def list_copies(exam_id: UUID | None = None, db: Session = Depends(get_db)) -> list[StudentCopy]:
    q = db.query(StudentCopy).order_by(StudentCopy.created_at.desc())
    if exam_id is not None:
        q = q.filter(StudentCopy.exam_id == exam_id)
    return q.all()


@router.get("/copies/{copy_id}", response_model=CopyRead)
def get_copy(copy_id: UUID, db: Session = Depends(get_db)) -> StudentCopy:
    copy = db.get(StudentCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")
    return copy


@router.post("/copies/{copy_id}/process")
def launch_process(copy_id: UUID, force: bool = Query(default=False), db: Session = Depends(get_db)) -> dict:
    copy = db.get(StudentCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")

    if copy.status == CopyStatus.processed_pages.value and not force:
        return {
            "copy_id": str(copy_id),
            "status": "already_processed",
            "message": "Copy already processed. Use force=true to reprocess.",
        }

    if copy.status in (CopyStatus.processing.value, CopyStatus.queued.value):
        raise HTTPException(status_code=409, detail=f"Copy already {copy.status}")

    copy.status = CopyStatus.queued.value
    copy.error_message = None
    db.add(copy)
    db.commit()
    db.refresh(copy)

    result = process_copy.apply_async(args=[str(copy_id)], kwargs={"force": force})
    copy.processing_task_id = result.id
    db.add(copy)
    db.commit()

    return {"copy_id": str(copy_id), "task_id": result.id, "status": "queued"}


@router.get("/copies/{copy_id}/pages", response_model=list[PageRead])
def list_pages(copy_id: UUID, db: Session = Depends(get_db)) -> list[CopyPage]:
    copy = db.get(StudentCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")
    return db.query(CopyPage).filter(CopyPage.copy_id == copy_id).order_by(CopyPage.page_number.asc()).all()


@router.get("/copies/{copy_id}/status")
def get_status(copy_id: UUID, db: Session = Depends(get_db)) -> dict:
    copy = db.get(StudentCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")

    task_state = None
    task_info = None
    if copy.processing_task_id:
        res = AsyncResult(copy.processing_task_id, app=celery)
        task_state = res.state
        try:
            task_info = res.info if isinstance(res.info, dict) else {"info": str(res.info)}
        except Exception:
            task_info = None

    return {
        "copy_id": str(copy.id),
        "status": copy.status,
        "task_id": copy.processing_task_id,
        "task_state": task_state,
        "error_message": copy.error_message,
        "task_info": task_info,
    }


@router.get("/copies/{copy_id}/correction")
def get_correction(copy_id: UUID, db: Session = Depends(get_db)) -> dict:
    copy = db.get(StudentCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")
    # MVP: no grading yet
    return {
        "copy_id": str(copy.id),
        "corrections": [],
        "needs_human_review": True,
        "confidence": None,
    }


@router.get("/copies/{copy_id}/transcriptions", response_model=list[TranscriptionRead])
def list_copy_transcriptions(copy_id: UUID, db: Session = Depends(get_db)) -> list[Transcription]:
    copy = db.get(StudentCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")
    return (
        db.query(Transcription).filter(Transcription.copy_id == copy_id).order_by(Transcription.created_at.desc()).all()
    )


@router.post("/copies/{copy_id}/grade-async")
def launch_grade_async(
    copy_id: UUID,
    force: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    """Launch async LLM grading via Celery. Returns task_id for status polling."""
    copy = db.get(StudentCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")

    if copy.status == CopyStatus.corrected.value and not force:
        return {"copy_id": str(copy_id), "status": "already_corrected"}

    result = grade_copy_task.apply_async(args=[str(copy_id)], kwargs={"force": force})
    copy.processing_task_id = result.id
    db.add(copy)
    db.commit()
    return {"copy_id": str(copy_id), "task_id": result.id, "status": "grading_queued"}


@router.post("/copies/{copy_id}/ocr")
def ocr_copy(
    copy_id: UUID,
    max_pages: int | None = Query(default=None, ge=1),
    sources: list[str] = Query(default=["azure"]),
    image_type: str | None = Query(default=None, pattern="^(original|processed)$"),
    confirm_paid_calls: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> dict:
    settings = get_settings()
    if not settings.OCR_ENABLE_PAID_CALLS:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "paid_calls_disabled",
                "message": "Paid OCR calls are disabled. Set OCR_ENABLE_PAID_CALLS=true to enable.",
            },
        )
    if not confirm_paid_calls:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "confirmation_required",
                "message": "Set confirm_paid_calls=true to run paid OCR calls on multiple pages.",
            },
        )

    copy = db.get(StudentCopy, copy_id)
    if not copy:
        raise HTTPException(status_code=404, detail="Copy not found")

    pages = db.query(CopyPage).filter(CopyPage.copy_id == copy_id).order_by(CopyPage.page_number.asc()).all()
    if not pages:
        raise HTTPException(
            status_code=409,
            detail={"error": "no_pages", "message": "Copy has no pages to OCR"},
        )

    limit = int(settings.OCR_MAX_PAGES_PER_JOB)
    requested = max_pages or limit
    if requested > limit:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "max_pages_exceeds_limit",
                "message": f"Requested max_pages={requested} exceeds OCR_MAX_PAGES_PER_JOB={limit}",
            },
        )

    allowed = {"mathpix", "azure", "openai_vision"}
    unknown = [s for s in sources if s not in allowed]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_sources",
                "message": f"Unknown OCR sources: {unknown}",
                "allowed": sorted(allowed),
            },
        )

    # Validate configuration up front for selected sources.
    if "mathpix" in sources and (not settings.MATHPIX_APP_ID or not settings.MATHPIX_APP_KEY):
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_mathpix_keys", "message": "Mathpix keys not set"},
        )
    if "azure" in sources and (
        not settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT or not settings.AZURE_DOCUMENT_INTELLIGENCE_KEY
    ):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_azure_document_intelligence_keys",
                "message": "Azure Document Intelligence endpoint/key not set",
            },
        )
    if "openai_vision" in sources and not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_openai_api_key", "message": "OpenAI key not set"},
        )

    storage = get_storage()
    img_type = image_type or settings.OCR_DEFAULT_IMAGE_TYPE
    pages_to_process = pages[: min(requested, len(pages))]

    created: list[dict] = []
    for p in pages_to_process:
        rel = p.original_image_path if img_type == "original" else p.processed_image_path
        if not rel:
            continue
        abs_path = storage.resolve(rel)
        if not abs_path.exists():
            continue

        per_page: dict[str, str] = {"page_id": str(p.id)}
        image_path = str(abs_path)

        if "mathpix" in sources:
            r = call_mathpix_image(image_path)
            t = Transcription(
                copy_id=p.copy_id,
                page_id=p.id,
                source="mathpix",
                input_image_type=img_type,
                raw_json=r.get("raw_json") or {},
                raw_text=r.get("raw_text"),
                raw_latex=r.get("raw_latex"),
                final_text=r.get("raw_text"),
                final_latex=r.get("raw_latex"),
                confidence=r.get("confidence"),
                needs_human_review=r.get("status") != "ok",
                error_message=r.get("error_message"),
            )
            db.add(t)
            db.commit()
            db.refresh(t)
            per_page["mathpix_transcription_id"] = str(t.id)

        if "azure" in sources:
            r = call_azure_read(image_path)
            t = Transcription(
                copy_id=p.copy_id,
                page_id=p.id,
                source="azure",
                input_image_type=img_type,
                raw_json=r.get("raw_json") or {},
                raw_text=r.get("raw_text"),
                raw_latex=r.get("raw_latex"),
                final_text=r.get("raw_text"),
                final_latex=r.get("raw_latex"),
                confidence=r.get("confidence"),
                needs_human_review=r.get("status") != "ok",
                error_message=r.get("error_message"),
            )
            db.add(t)
            db.commit()
            db.refresh(t)
            per_page["azure_transcription_id"] = str(t.id)

        if "openai_vision" in sources:
            r = call_openai_vision_for_transcription(image_path, "")
            t = Transcription(
                copy_id=p.copy_id,
                page_id=p.id,
                source="openai_vision",
                input_image_type=img_type,
                raw_json=r.get("raw_json") or {},
                raw_text=r.get("raw_text"),
                raw_latex=r.get("raw_latex"),
                final_text=r.get("raw_text"),
                final_latex=r.get("raw_latex"),
                confidence=r.get("confidence"),
                needs_human_review=r.get("status") != "ok",
                error_message=r.get("error_message"),
            )
            db.add(t)
            db.commit()
            db.refresh(t)
            per_page["openai_vision_transcription_id"] = str(t.id)

        created.append(per_page)

    return {
        "copy_id": str(copy_id),
        "image_type": img_type,
        "sources": sources,
        "requested_max_pages": requested,
        "processed_pages": len(created),
        "created": created,
    }
