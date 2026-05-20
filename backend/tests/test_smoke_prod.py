"""Smoke tests executable against the production API.

Usage:
    PUBLIC_API_BASE_URL=https://maths.labomaths.tn/correction/api \
    ADMIN_API_TOKEN=... \
    pytest tests/test_smoke_prod.py -m smoke -v
"""

from __future__ import annotations

import os

import pytest

pytestmark = pytest.mark.smoke

PROD_URL = os.environ.get("PUBLIC_API_BASE_URL", "")
ADMIN_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")


def _skip_if_no_prod():
    if not PROD_URL:
        pytest.skip("PUBLIC_API_BASE_URL not set — skipping smoke tests")


@pytest.fixture
def prod_client():
    _skip_if_no_prod()
    import httpx

    client = httpx.Client(base_url=PROD_URL, timeout=15)
    yield client
    client.close()


@pytest.fixture
def prod_admin_client():
    _skip_if_no_prod()
    if not ADMIN_TOKEN:
        pytest.skip("ADMIN_API_TOKEN not set")
    import httpx

    client = httpx.Client(
        base_url=PROD_URL,
        headers={"Authorization": f"Bearer {ADMIN_TOKEN}"},
        timeout=15,
    )
    yield client
    client.close()


def test_smoke_health(prod_client):
    r = prod_client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_smoke_health_ready(prod_client):
    r = prod_client.get("/health/ready")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "ready"
    assert data["checks"]["rag"]["ok"] is True


def test_smoke_integrations_status(prod_admin_client):
    r = prod_admin_client.get("/integrations/status")
    assert r.status_code == 200
