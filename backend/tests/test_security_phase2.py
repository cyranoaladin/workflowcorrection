"""
Security tests for phase 2 endpoints: corrections, rubric-json, bilan, validate.
All new routes must be protected by admin token.
"""

from __future__ import annotations

NEW_PROTECTED_ROUTES = [
    ("POST", "/exams/00000000-0000-0000-0000-000000000000/rubric-json"),
    ("PATCH", "/exams/00000000-0000-0000-0000-000000000000"),
    ("POST", "/copies/00000000-0000-0000-0000-000000000000/grade"),
    ("POST", "/copies/00000000-0000-0000-0000-000000000000/grade-async"),
    ("GET", "/copies/00000000-0000-0000-0000-000000000000/report"),
    ("PATCH", "/corrections/00000000-0000-0000-0000-000000000000/validate"),
    ("GET", "/exams/00000000-0000-0000-0000-000000000000/bilan"),
]


class TestPhase2AuthProtection:
    def test_phase2_routes_reject_missing_token(self, anon_client):
        for method, path in NEW_PROTECTED_ROUTES:
            if method == "GET":
                r = anon_client.get(path)
            elif method == "POST":
                r = anon_client.post(path, json={})
            elif method == "PATCH":
                r = anon_client.patch(path, json={})
            else:
                continue
            assert r.status_code == 401, f"{method} {path} should return 401 but got {r.status_code}"
            detail = r.json().get("detail", {})
            assert (
                detail.get("error") == "missing_admin_token"
            ), f"{method} {path}: expected missing_admin_token, got {detail}"

    def test_phase2_routes_reject_wrong_token(self, anon_client):
        for method, path in NEW_PROTECTED_ROUTES:
            headers = {"Authorization": "Bearer definitely-wrong-token"}
            if method == "GET":
                r = anon_client.get(path, headers=headers)
            elif method == "POST":
                r = anon_client.post(path, json={}, headers=headers)
            elif method == "PATCH":
                r = anon_client.patch(path, json={}, headers=headers)
            else:
                continue
            assert r.status_code == 401, f"{method} {path} with wrong token should return 401 but got {r.status_code}"

    def test_phase2_routes_accept_valid_token(self, client):
        """With valid token, routes return 404/422/409 — never 401."""
        for method, path in NEW_PROTECTED_ROUTES:
            if method == "GET":
                r = client.get(path)
            elif method == "POST":
                r = client.post(path, json={"questions": []})
            elif method == "PATCH":
                r = client.patch(path, json={})
            else:
                continue
            assert r.status_code != 401, f"{method} {path} with valid token returned 401 unexpectedly"
            assert r.status_code != 403, f"{method} {path} with valid token returned 403 unexpectedly"

    def test_health_still_public(self, anon_client):
        assert anon_client.get("/health").status_code == 200
        assert anon_client.get("/health/live").status_code == 200
        assert anon_client.get("/health/ready").status_code == 200
