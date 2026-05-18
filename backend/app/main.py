from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.security import require_admin
from app.core.storage import get_storage
from app.routers import copies, corrections, exams, health, integrations, knowledge, pages

configure_logging()
settings = get_settings()
settings.validate_for_runtime()


@asynccontextmanager
async def lifespan(_: FastAPI):
    # Startup
    get_storage().ensure_base_dirs()
    yield
    # Shutdown: nothing yet


app = FastAPI(title=settings.APP_NAME, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
protected = [Depends(require_admin)]
app.include_router(integrations.router, dependencies=protected)
app.include_router(exams.router, dependencies=protected)
app.include_router(copies.router, dependencies=protected)
app.include_router(pages.router, dependencies=protected)
app.include_router(corrections.router, dependencies=protected)
app.include_router(knowledge.router, dependencies=protected)
