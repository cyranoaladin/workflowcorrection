from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.transcription_schema import TranscriptionRead


class PageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    copy_id: UUID
    page_number: int
    original_image_path: str
    processed_image_path: str | None
    width: int | None
    height: int | None
    created_at: datetime


class PageFullRead(PageRead):
    """Page with its transcriptions pre-loaded (batch endpoint)."""

    has_processed: bool = False
    transcriptions: list[TranscriptionRead] = Field(default_factory=list)
