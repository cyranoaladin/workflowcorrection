from __future__ import annotations

from pathlib import Path

import pytest


def test_deploy_server_runs_alembic_upgrade_before_health_checks() -> None:
    script_candidates = [
        Path(__file__).resolve().parents[2] / "scripts" / "deploy_server.sh",
        Path("/repo-scripts/deploy_server.sh"),
    ]
    script = next((candidate for candidate in script_candidates if candidate.exists()), None)
    if script is None:
        pytest.skip("deploy_server.sh is not mounted in this backend-only test image")

    content = script.read_text(encoding="utf-8")

    assert "alembic upgrade head" in content
    assert content.index("alembic upgrade head") < content.index("Tests de santé")
