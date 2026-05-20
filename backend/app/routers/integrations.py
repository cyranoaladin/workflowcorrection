from __future__ import annotations

from fastapi import APIRouter

from app.core.config import get_settings
from app.services.rag.factory import get_rag_provider

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
                settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and settings.AZURE_DOCUMENT_INTELLIGENCE_KEY
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
        "rag": _rag_status(settings),
    }


def _rag_status(settings) -> dict:
    if settings.RAG_PROVIDER == "pgvector":
        return {"ok": True, "provider": "pgvector", "configured": True}
    configured = bool(settings.RAG_HTTP_BASE_URL and settings.RAG_HTTP_API_TOKEN)
    try:
        return {
            "ok": get_rag_provider().health() if configured else False,
            "provider": "http",
            "configured": configured,
            "base_url": settings.RAG_HTTP_BASE_URL,
            "collection": settings.RAG_HTTP_COLLECTION,
        }
    except Exception as exc:
        return {
            "ok": False,
            "provider": "http",
            "configured": configured,
            "error": type(exc).__name__,
        }
