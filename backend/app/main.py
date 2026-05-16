from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging_config import configure_logging
from app.core.storage import get_storage
from app.routers import copies, corrections, exams, health, integrations, pages

configure_logging()
settings = get_settings()


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
app.include_router(integrations.router)
app.include_router(exams.router)
app.include_router(copies.router)
app.include_router(pages.router)
app.include_router(corrections.router)
