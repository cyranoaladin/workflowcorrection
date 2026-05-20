from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.storage import get_storage
from app.models.page import CopyPage
from app.models.transcription import Transcription
from app.schemas.transcription_schema import TranscriptionRead
from app.services.azure_ocr_service import call_azure_read
from app.services.mathpix_service import call_mathpix_image
from app.services.openai_vision_service import call_openai_vision_for_transcription
from app.services.transcription_fusion_service import fuse_transcriptions

router = APIRouter(prefix="/pages", tags=["pages"])


def _resolve_page_image(page: CopyPage, image_type: str) -> str:
    rel = page.original_image_path if image_type == "original" else page.processed_image_path
    if not rel:
        raise HTTPException(status_code=404, detail="Image not available")

    storage = get_storage()
    abs_path = storage.resolve(rel)
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="Image file missing on disk")
    return str(abs_path)


@router.get("/{page_id}/image")
def get_page_image(
    page_id: UUID,
    type: str = Query(default="original", pattern="^(original|processed)$"),
    db: Session = Depends(get_db),
) -> FileResponse:
    page = db.get(CopyPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    rel = page.original_image_path if type == "original" else page.processed_image_path
    if not rel:
        raise HTTPException(status_code=404, detail="Image not available")

    storage = get_storage()
    abs_path = storage.resolve(rel)
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="Image file missing on disk")

    return FileResponse(path=str(abs_path), media_type="image/png")


@router.get("/{page_id}/transcriptions", response_model=list[TranscriptionRead])
def list_page_transcriptions(page_id: UUID, db: Session = Depends(get_db)) -> list[Transcription]:
    page = db.get(CopyPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")
    return (
        db.query(Transcription).filter(Transcription.page_id == page_id).order_by(Transcription.created_at.desc()).all()
    )


def _guard_paid_calls_enabled() -> None:
    settings = get_settings()
    if not settings.OCR_ENABLE_PAID_CALLS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "error": "paid_calls_disabled",
                "message": "Paid OCR calls are disabled. Set OCR_ENABLE_PAID_CALLS=true to enable.",
            },
        )


def _guard_paid_call_confirmed(confirm_paid_call: bool) -> None:
    if not confirm_paid_call:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "confirmation_required",
                "message": "Set confirm_paid_call=true to run a paid OCR call.",
            },
        )


@router.post("/{page_id}/ocr/mathpix", response_model=TranscriptionRead)
def ocr_mathpix(
    page_id: UUID,
    image_type: str | None = Query(default=None, pattern="^(original|processed)$"),
    confirm_paid_call: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Transcription:
    settings = get_settings()
    _guard_paid_calls_enabled()
    _guard_paid_call_confirmed(confirm_paid_call)
    if not settings.MATHPIX_APP_ID or not settings.MATHPIX_APP_KEY:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_mathpix_keys", "message": "Mathpix keys not set"},
        )

    page = db.get(CopyPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    img_type = image_type or settings.OCR_DEFAULT_IMAGE_TYPE
    image_path = _resolve_page_image(page, img_type)
    result = call_mathpix_image(image_path)

    t = Transcription(
        copy_id=page.copy_id,
        page_id=page.id,
        source="mathpix",
        input_image_type=img_type,
        raw_json=result.get("raw_json") or {},
        raw_text=result.get("raw_text"),
        raw_latex=result.get("raw_latex"),
        final_text=result.get("raw_text"),
        final_latex=result.get("raw_latex"),
        confidence=result.get("confidence"),
        needs_human_review=result.get("status") != "ok",
        error_message=result.get("error_message"),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.post("/{page_id}/ocr/azure", response_model=TranscriptionRead)
def ocr_azure(
    page_id: UUID,
    image_type: str | None = Query(default=None, pattern="^(original|processed)$"),
    confirm_paid_call: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Transcription:
    settings = get_settings()
    _guard_paid_calls_enabled()
    _guard_paid_call_confirmed(confirm_paid_call)
    if not settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT or not settings.AZURE_DOCUMENT_INTELLIGENCE_KEY:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "missing_azure_document_intelligence_keys",
                "message": "Azure Document Intelligence endpoint/key not set",
            },
        )

    page = db.get(CopyPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    img_type = image_type or settings.OCR_DEFAULT_IMAGE_TYPE
    image_path = _resolve_page_image(page, img_type)
    result = call_azure_read(image_path)

    t = Transcription(
        copy_id=page.copy_id,
        page_id=page.id,
        source="azure",
        input_image_type=img_type,
        raw_json=result.get("raw_json") or {},
        raw_text=result.get("raw_text"),
        raw_latex=result.get("raw_latex"),
        final_text=result.get("raw_text"),
        final_latex=result.get("raw_latex"),
        confidence=result.get("confidence"),
        needs_human_review=result.get("status") != "ok",
        error_message=result.get("error_message"),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.post("/{page_id}/ocr/openai-vision", response_model=TranscriptionRead)
def ocr_openai_vision(
    page_id: UUID,
    image_type: str | None = Query(default=None, pattern="^(original|processed)$"),
    question_context: str | None = Query(default=None, max_length=4000),
    confirm_paid_call: bool = Query(default=False),
    db: Session = Depends(get_db),
) -> Transcription:
    settings = get_settings()
    _guard_paid_calls_enabled()
    _guard_paid_call_confirmed(confirm_paid_call)
    if not settings.OPENAI_API_KEY:
        raise HTTPException(
            status_code=400,
            detail={"error": "missing_openai_api_key", "message": "OpenAI key not set"},
        )

    page = db.get(CopyPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    img_type = image_type or settings.OCR_DEFAULT_IMAGE_TYPE
    image_path = _resolve_page_image(page, img_type)
    result = call_openai_vision_for_transcription(image_path, question_context or "")

    t = Transcription(
        copy_id=page.copy_id,
        page_id=page.id,
        source="openai_vision",
        input_image_type=img_type,
        raw_json=result.get("raw_json") or {},
        raw_text=result.get("raw_text"),
        raw_latex=result.get("raw_latex"),
        final_text=result.get("raw_text"),
        final_latex=result.get("raw_latex"),
        confidence=result.get("confidence"),
        needs_human_review=result.get("status") != "ok",
        error_message=result.get("error_message"),
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


@router.post("/{page_id}/ocr/fuse", response_model=TranscriptionRead)
def ocr_fuse(page_id: UUID, db: Session = Depends(get_db)) -> Transcription:
    page = db.get(CopyPage, page_id)
    if not page:
        raise HTTPException(status_code=404, detail="Page not found")

    # Pull latest per source for this page
    def latest(source: str) -> Transcription | None:
        return (
            db.query(Transcription)
            .filter(Transcription.page_id == page_id, Transcription.source == source)
            .order_by(Transcription.created_at.desc())
            .first()
        )

    m = latest("mathpix")
    a = latest("azure")
    o = latest("openai_vision")
    if not (m or a or o):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_transcriptions",
                "message": "No OCR transcriptions found for this page",
            },
        )

    fusion = fuse_transcriptions(
        page_id=str(page_id),
        mathpix={
            "raw_text": m.raw_text,
            "raw_latex": m.raw_latex,
            "raw_json": m.raw_json,
            "confidence": m.confidence,
        }
        if m
        else None,
        azure={
            "raw_text": a.raw_text,
            "raw_latex": a.raw_latex,
            "raw_json": a.raw_json,
            "confidence": a.confidence,
        }
        if a
        else None,
        openai={
            "raw_text": o.raw_text,
            "raw_latex": o.raw_latex,
            "raw_json": o.raw_json,
            "confidence": o.confidence,
        }
        if o
        else None,
    )

    t = Transcription(
        copy_id=page.copy_id,
        page_id=page.id,
        source="fusion",
        input_image_type=None,
        raw_json=fusion,
        raw_text=fusion.get("final_text"),
        raw_latex=fusion.get("final_latex"),
        final_text=fusion.get("final_text"),
        final_latex=fusion.get("final_latex"),
        confidence=fusion.get("confidence"),
        needs_human_review=bool(fusion.get("needs_human_review")),
        error_message=None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t
