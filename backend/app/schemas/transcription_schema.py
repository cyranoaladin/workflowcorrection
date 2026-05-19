from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class TranscriptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    copy_id: UUID
    page_id: UUID | None
    question_id: str | None

    source: str | None
    input_image_type: str | None

    raw_text: str | None
    raw_latex: str | None
    final_text: str | None
    final_latex: str | None

    raw_json: dict[str, Any] | None
    confidence: float | None
    needs_human_review: bool
    error_message: str | None
    created_at: datetime
