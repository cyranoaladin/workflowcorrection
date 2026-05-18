from __future__ import annotations

from uuid import UUID
from unittest.mock import patch


def test_create_and_list_exams(client, unique_title, cleanup_ids):
    r = client.post("/exams", json={"title": unique_title, "level": "test", "session": "2026"})
    assert r.status_code == 200
    exam = r.json()
    exam_id = UUID(exam["id"])
    cleanup_ids["exam_ids"].append(exam_id)

    r2 = client.get("/exams")
    assert r2.status_code == 200
    exams = r2.json()
    assert any(e["id"] == str(exam_id) for e in exams)


def test_get_exam_not_found(client):
    r = client.get("/exams/00000000-0000-0000-0000-000000000000")
    assert r.status_code == 404


def test_embed_exam_indexes_rubric_json_idempotently(client, cleanup_ids, unique_title):
    r = client.post("/exams", json={"title": unique_title, "level": "test", "session": "2026"})
    assert r.status_code == 200
    exam_id = r.json()["id"]
    cleanup_ids["exam_ids"].append(UUID(exam_id))

    rubric = {
        "questions": [
            {"id": "Q1", "label": "Dériver x^2", "points_max": 4, "criteria": ["Résultat exact"]},
            {"id": "Q2", "label": "Intégrer x^2", "points_max": 6, "criteria": ["Primitive"]},
        ]
    }
    assert client.post(f"/exams/{exam_id}/rubric-json", json=rubric).status_code == 200

    embedding = [0.0] * 1536
    with patch("app.workers.tasks.embed_texts", return_value=[embedding, embedding]):
        first = client.post(f"/exams/{exam_id}/embed")
        second = client.post(f"/exams/{exam_id}/embed")

    assert first.status_code == 200
    assert first.json()["status"] == "embedded"
    assert first.json()["chunks_count"] == 2
    assert second.status_code == 200
    assert second.json()["status"] == "skipped"

    listed = client.get(f"/exams/{exam_id}/knowledge")
    assert listed.status_code == 200
    data = listed.json()
    assert len(data["documents"]) == 1
    assert data["documents"][0]["kind"] == "rubric"
    assert data["documents"][0]["chunks_count"] == 2
