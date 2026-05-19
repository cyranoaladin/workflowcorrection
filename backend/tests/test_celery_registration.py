from __future__ import annotations


def test_embed_exam_task_is_registered_in_worker_app() -> None:
    from app.workers.celery_app import celery

    assert "embed_exam" in celery.tasks
