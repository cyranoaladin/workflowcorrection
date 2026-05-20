from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.storage import get_storage
from app.services.rag.factory import get_rag_provider

router = APIRouter(tags=["health"])


@router.get("/health")
def health() -> dict:
    return {"status": "ok"}


@router.get("/health/live")
def live() -> dict:
    return {"status": "live"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)) -> JSONResponse:
    settings = get_settings()
    storage = get_storage()

    checks: dict[str, dict] = {}

    checks["database"] = _check_db(db)
    checks["redis"] = _check_redis(settings)
    checks["storage"] = _check_storage(storage)
    checks["rag"] = _check_rag(settings)

    ok = all(check["ok"] for check in checks.values())
    payload = {"status": "ready" if ok else "degraded", "checks": checks}
    if not ok:
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)


def _check_db(db: Session) -> dict:
    try:
        db.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def _check_redis(settings) -> dict:
    try:
        Redis.from_url(settings.REDIS_URL).ping()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def _check_storage(storage) -> dict:
    try:
        storage.ensure_base_dirs()
        probe_rel = "reports/.ready_probe"
        probe_abs = storage.resolve(probe_rel)
        probe_abs.write_text("ok", encoding="utf-8")
        probe_abs.unlink(missing_ok=True)
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": type(exc).__name__}


def _check_rag(settings) -> dict:
    if settings.RAG_PROVIDER == "pgvector":
        return {"ok": True, "provider": "pgvector"}
    try:
        ok = get_rag_provider().health()
        return {
            "ok": ok,
            "provider": "http",
            "base_url": settings.RAG_HTTP_BASE_URL,
        }
    except Exception as exc:
        return {"ok": False, "provider": "http", "error": type(exc).__name__}
