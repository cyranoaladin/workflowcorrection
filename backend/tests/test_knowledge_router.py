from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from app.routers.knowledge import _build_embed_response, _embed_task_belongs_to_exam, _new_embed_task_id


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


def test_embed_response_handles_failed_task_exception_result() -> None:
    task = MagicMock()
    task.id = str(uuid.uuid4())
    task.status = "FAILURE"
    task.ready.return_value = True
    task.result = RuntimeError("boom")

    response = _build_embed_response(task)

    assert response.status == "failure"
    assert response.chunks_count == 0
    assert response.task_id == task.id


def test_embed_task_id_is_scoped_to_exam_id() -> None:
    exam_id = uuid.uuid4()
    other_exam_id = uuid.uuid4()

    task_id = _new_embed_task_id(exam_id)

    assert _embed_task_belongs_to_exam(task_id, exam_id) is True
    assert _embed_task_belongs_to_exam(task_id, other_exam_id) is False
