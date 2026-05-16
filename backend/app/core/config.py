from __future__ import annotations

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # App
    APP_ENV: str = "development"
    APP_NAME: str = "math-correction-platform"
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    PUBLIC_API_BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://correction_user:change_me@postgres:5432/correction_db"
    )

    # Redis / Celery
    REDIS_URL: str = "redis://redis:6379/0"
    CELERY_BROKER_URL: str = "redis://redis:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://redis:6379/1"

    # Storage
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "/app/storage"
    MAX_UPLOAD_SIZE_MB: int = 50

    MINIO_ENDPOINT: str = "minio:9000"
    MINIO_ACCESS_KEY: str = ""
    MINIO_SECRET_KEY: str = ""
    MINIO_BUCKET: str = "correction-files"
    MINIO_SECURE: bool = False

    # OCR / IA (stubs)
    MATHPIX_APP_ID: str = ""
    MATHPIX_APP_KEY: str = ""

    AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: str = ""
    AZURE_DOCUMENT_INTELLIGENCE_KEY: str = ""

    OPENAI_API_KEY: str = ""
    OPENAI_VISION_MODEL: str = "gpt-4.1"
    OPENAI_GRADING_MODEL: str = "gpt-4.1"
    OPENAI_AUDIT_MODEL: str = "gpt-4.1"

    # OCR safety
    OCR_MAX_PAGES_PER_JOB: int = 3
    OCR_ENABLE_PAID_CALLS: bool = False
    OCR_DEFAULT_IMAGE_TYPE: str = "processed"

    # Security (future)
    JWT_SECRET: str = "change_me_long_random_secret"
    ADMIN_EMAIL: str = "admin@example.com"
    ADMIN_PASSWORD: str = "change_me"

    CORS_ALLOWED_ORIGINS: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_allowed_origins(self) -> List[str]:
        return [o.strip() for o in self.CORS_ALLOWED_ORIGINS.split(",") if o.strip()]

    @property
    def max_upload_bytes(self) -> int:
        return int(self.MAX_UPLOAD_SIZE_MB) * 1024 * 1024


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
