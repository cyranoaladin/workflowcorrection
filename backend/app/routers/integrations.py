from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings

router = APIRouter(tags=["integrations"])


@router.get("/integrations/status")
def integrations_status() -> dict:
    settings = get_settings()
    paid = bool(settings.OCR_ENABLE_PAID_CALLS)
    return {
        "mathpix": {
            "configured": bool(settings.MATHPIX_APP_ID and settings.MATHPIX_APP_KEY),
            "paid_calls_enabled": paid,
        },
        "azure_document_intelligence": {
            "configured": bool(
                settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT
                and settings.AZURE_DOCUMENT_INTELLIGENCE_KEY
            ),
            "paid_calls_enabled": paid,
        },
        "openai": {
            "configured": bool(settings.OPENAI_API_KEY),
            "paid_calls_enabled": paid,
        },
        "ocr": {
            "paid_calls_enabled": paid,
            "max_pages_per_job": int(settings.OCR_MAX_PAGES_PER_JOB),
            "default_image_type": settings.OCR_DEFAULT_IMAGE_TYPE,
        },
    }
