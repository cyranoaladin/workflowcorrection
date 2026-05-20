from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


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
