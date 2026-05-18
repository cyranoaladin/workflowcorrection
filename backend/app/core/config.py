from __future__ import annotations

from functools import lru_cache
from typing import List, Literal

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
    POSTGRES_PASSWORD: str = ""
    DATABASE_URL: str = Field(
        default="postgresql+psycopg2://correction_user:change_me@postgres:5432/correction_db"
    )

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str = "redis://localhost:6379/0"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/1"

    # Storage
    STORAGE_BACKEND: str = "local"
    LOCAL_STORAGE_PATH: str = "/app/storage"
    MAX_UPLOAD_SIZE_MB: int = 50
    PDF_MAX_PAGES: int = 50

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

    # Embeddings / RAG
    EMBEDDING_PROVIDER: Literal["openai", "tei"] = "openai"
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    EMBEDDING_DIMENSION: int = 1536
    TEI_ENDPOINT: str = ""
    RAG_TOP_K: int = 5
    RAG_MIN_SCORE: float = 0.35

    # Security (future)
    ADMIN_API_TOKEN: str = ""
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

    def validate_for_runtime(self) -> None:
        if self.APP_ENV.lower() not in {"production", "prod"}:
            return

        problems: list[str] = []

        def unsafe_secret(name: str, value: str, *, min_len: int = 24) -> None:
            normalized = (value or "").strip()
            lowered = normalized.lower()
            if (
                not normalized
                or len(normalized) < min_len
                or "change_me" in lowered
                or "replace_with" in lowered
                or "example" in lowered
            ):
                problems.append(name)

        unsafe_secret("ADMIN_API_TOKEN", self.ADMIN_API_TOKEN, min_len=32)
        unsafe_secret("JWT_SECRET", self.JWT_SECRET, min_len=32)
        unsafe_secret("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD, min_len=16)
        if "change_me" in self.DATABASE_URL.lower() or "replace_with" in self.DATABASE_URL.lower():
            problems.append("DATABASE_URL")
        if any(origin.startswith("http://") or "localhost" in origin or "127.0.0.1" in origin for origin in self.cors_allowed_origins):
            problems.append("CORS_ALLOWED_ORIGINS")
        if self.PUBLIC_API_BASE_URL.startswith("http://") or "localhost" in self.PUBLIC_API_BASE_URL:
            problems.append("PUBLIC_API_BASE_URL")

        if problems:
            unique = ", ".join(sorted(set(problems)))
            raise ValueError(f"Unsafe production settings: {unique}")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
