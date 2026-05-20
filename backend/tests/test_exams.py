from __future__ import annotations

from uuid import UUID


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
