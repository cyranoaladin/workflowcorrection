from __future__ import annotations

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from redis import Redis
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.database import get_db
from app.core.storage import get_storage

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

    checks: dict[str, str] = {}
    errors: dict[str, str] = {}

    # Database
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = "error"
        errors["database"] = f"{type(e).__name__}: {e}"

    # Redis
    try:
        r = Redis.from_url(settings.REDIS_URL)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = "error"
        errors["redis"] = f"{type(e).__name__}: {e}"

    # Storage
    try:
        storage.ensure_base_dirs()
        # Write check
        probe_rel = "reports/.ready_probe"
        probe_abs = storage.resolve(probe_rel)
        probe_abs.write_text("ok", encoding="utf-8")
        probe_abs.unlink(missing_ok=True)
        checks["storage"] = "ok"
    except Exception as e:
        checks["storage"] = "error"
        errors["storage"] = f"{type(e).__name__}: {e}"

    ok = all(v == "ok" for v in checks.values()) and {"database", "redis", "storage"}.issubset(checks.keys())
    payload = {"status": "ready" if ok else "not_ready", "checks": checks}
    if not ok:
        payload["errors"] = errors
        return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content=payload)
    return JSONResponse(status_code=status.HTTP_200_OK, content=payload)
