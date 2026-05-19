from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.routers.knowledge import _build_embed_response


def test_embed_response_includes_chunks_count_when_task_ready() -> None:
    task = MagicMock()
    task.id = str(uuid.uuid4())
    task.ready.return_value = True
    task.result = {"status": "completed", "chunks_count": 3}

    response = _build_embed_response(task)

    assert response.status == "completed"
    assert response.chunks_count == 3
    assert response.task_id == task.id


def test_embed_response_is_queued_when_task_not_ready() -> None:
    task = MagicMock()
    task.id = str(uuid.uuid4())
    task.ready.return_value = False

    response = _build_embed_response(task)

    assert response.status == "queued"
    assert response.chunks_count is None
    assert response.task_id == task.id
