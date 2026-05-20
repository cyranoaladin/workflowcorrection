"""
Tests for CSV import flow and rubric_json status interactions.
"""

from __future__ import annotations

import io
from uuid import UUID


def _make_csv(rows: list[dict]) -> bytes:
    if not rows:
        return b"student_name,copy_code\n"
    headers = ",".join(rows[0].keys())
    lines = [headers] + [",".join(str(v) for v in r.values()) for r in rows]
    return "\n".join(lines).encode("utf-8")


def _make_csv_latin1(rows: list[dict]) -> bytes:
    return _make_csv(rows).decode("utf-8").encode("latin-1")


RUBRIC = {
    "questions": [
        {"id": "Q1", "label": "Calculer", "points_max": 4, "criteria": ["ok"]},
    ]
}


class TestCsvImport:
    def _create_exam(self, client, cleanup_ids, title):
        r = client.post("/exams", json={"title": title})
        assert r.status_code == 200
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))
        return exam_id

    def test_import_basic_csv(self, client, cleanup_ids, unique_title):
        exam_id = self._create_exam(client, cleanup_ids, unique_title)
        rows = [
            {"student_name": "Alice Martin", "copy_code": "A01"},
            {"student_name": "Bob Dupont", "copy_code": "A02"},
        ]
        csv_data = _make_csv(rows)
        r = client.post(
            f"/exams/{exam_id}/students/csv",
            files={"file": ("students.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["created"] == 2
        assert data["skipped"] == 0
        assert data["errors"] == []

    def test_import_french_headers(self, client, cleanup_ids, unique_title):
        exam_id = self._create_exam(client, cleanup_ids, unique_title)
        csv_data = b"nom,code\nDupont Marie,B01\nMartin Paul,B02\n"
        r = client.post(
            f"/exams/{exam_id}/students/csv",
            files={"file": ("s.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["created"] == 2

    def test_import_skips_empty_rows(self, client, cleanup_ids, unique_title):
        exam_id = self._create_exam(client, cleanup_ids, unique_title)
        csv_data = b"student_name,copy_code\nAlice,A01\n,,\n  ,  \n"
        r = client.post(
            f"/exams/{exam_id}/students/csv",
            files={"file": ("s.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert r.status_code == 200
        data = r.json()
        assert data["created"] == 1
        assert data["skipped"] == 2

    def test_import_latin1_encoding(self, client, cleanup_ids, unique_title):
        exam_id = self._create_exam(client, cleanup_ids, unique_title)
        rows = [{"student_name": "Élève Prénom", "copy_code": "C01"}]
        csv_data = _make_csv_latin1(rows)
        r = client.post(
            f"/exams/{exam_id}/students/csv",
            files={"file": ("s.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert r.status_code == 200
        assert r.json()["created"] == 1

    def test_import_utf8_bom(self, client, cleanup_ids, unique_title):
        exam_id = self._create_exam(client, cleanup_ids, unique_title)
        csv_data = b"\xef\xbb\xbfstudent_name,copy_code\nTest,T01\n"
        r = client.post(
            f"/exams/{exam_id}/students/csv",
            files={"file": ("s.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert r.status_code == 200
        assert r.json()["created"] == 1

    def test_import_rejects_missing_column(self, client, cleanup_ids, unique_title):
        exam_id = self._create_exam(client, cleanup_ids, unique_title)
        csv_data = b"code_seul\nA01\n"
        r = client.post(
            f"/exams/{exam_id}/students/csv",
            files={"file": ("s.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert r.status_code == 422
        assert r.json()["detail"]["error"] == "missing_column"

    def test_import_404_unknown_exam(self, client):
        csv_data = b"student_name\nAlice\n"
        r = client.post(
            "/exams/00000000-0000-0000-0000-000000000000/students/csv",
            files={"file": ("s.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert r.status_code == 404

    def test_imported_copies_visible_in_list(self, client, cleanup_ids, unique_title):
        exam_id = self._create_exam(client, cleanup_ids, unique_title)
        rows = [{"student_name": f"Eleve{i}", "copy_code": f"X{i:02d}"} for i in range(3)]
        csv_data = _make_csv(rows)
        client.post(
            f"/exams/{exam_id}/students/csv",
            files={"file": ("s.csv", io.BytesIO(csv_data), "text/csv")},
        )
        r = client.get(f"/copies?exam_id={exam_id}")
        assert r.status_code == 200
        copies = r.json()
        assert len(copies) == 3
        names = {c["student_name"] for c in copies}
        assert "Eleve0" in names

    def test_imported_copies_have_pending_pdf(self, client, cleanup_ids, unique_title):
        exam_id = self._create_exam(client, cleanup_ids, unique_title)
        csv_data = b"student_name\nAlice\n"
        client.post(
            f"/exams/{exam_id}/students/csv",
            files={"file": ("s.csv", io.BytesIO(csv_data), "text/csv")},
        )
        copies = client.get(f"/copies?exam_id={exam_id}").json()
        assert copies[0]["original_pdf_path"] == "pending"
        assert copies[0]["status"] == "uploaded"

    def test_copy_code_optional(self, client, cleanup_ids, unique_title):
        exam_id = self._create_exam(client, cleanup_ids, unique_title)
        csv_data = b"student_name\nAlice\nBob\n"
        r = client.post(
            f"/exams/{exam_id}/students/csv",
            files={"file": ("s.csv", io.BytesIO(csv_data), "text/csv")},
        )
        assert r.status_code == 200
        assert r.json()["created"] == 2


class TestCopyStatusFlow:
    """Verify that copy status transitions are correct and grade requires right status."""

    def _make_pdf_bytes(self):
        try:
            import pymupdf as fitz
        except Exception:
            import fitz
        doc = fitz.open()
        p = doc.new_page()
        p.insert_text((72, 72), "f'(x) = 2x")
        data = doc.tobytes()
        doc.close()
        return data

    def test_upload_status_is_uploaded(self, client, cleanup_ids, unique_title):
        r = client.post("/exams", json={"title": unique_title})
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))
        pdf = self._make_pdf_bytes()
        r2 = client.post(
            "/copies",
            data={"exam_id": exam_id},
            files={"file": ("c.pdf", pdf, "application/pdf")},
        )
        assert r2.status_code == 200
        assert r2.json()["status"] == "uploaded"

    def test_process_transitions_to_processed_pages(self, client, cleanup_ids, unique_title):
        r = client.post("/exams", json={"title": unique_title})
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))
        pdf = self._make_pdf_bytes()
        copy_id = client.post(
            "/copies",
            data={"exam_id": exam_id},
            files={"file": ("c.pdf", pdf, "application/pdf")},
        ).json()["id"]

        r2 = client.post(f"/copies/{copy_id}/process")
        assert r2.status_code == 200

        status = client.get(f"/copies/{copy_id}").json()["status"]
        assert status == "processed_pages"

    def test_grade_without_rubric_returns_422(self, client, cleanup_ids, unique_title):
        r = client.post("/exams", json={"title": unique_title})
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))
        pdf = self._make_pdf_bytes()
        copy_id = client.post(
            "/copies",
            data={"exam_id": exam_id},
            files={"file": ("c.pdf", pdf, "application/pdf")},
        ).json()["id"]
        client.post(f"/copies/{copy_id}/process")

        r2 = client.post(f"/copies/{copy_id}/grade")
        assert r2.status_code == 422
        assert r2.json()["detail"]["error"] == "no_rubric"

    def test_grade_async_returns_task_id(self, client, cleanup_ids, unique_title):
        r = client.post("/exams", json={"title": unique_title})
        exam_id = r.json()["id"]
        cleanup_ids["exam_ids"].append(UUID(exam_id))
        pdf = self._make_pdf_bytes()
        copy_id = client.post(
            "/copies",
            data={"exam_id": exam_id},
            files={"file": ("c.pdf", pdf, "application/pdf")},
        ).json()["id"]

        from unittest.mock import MagicMock, patch

        with patch("app.workers.tasks.grade_copy_task.apply_async") as mock_task:
            fake_result = MagicMock()
            fake_result.id = "fake-task-id-123"
            mock_task.return_value = fake_result
            r2 = client.post(f"/copies/{copy_id}/grade-async")

        assert r2.status_code == 200
        assert r2.json()["status"] == "grading_queued"
        assert "task_id" in r2.json()
