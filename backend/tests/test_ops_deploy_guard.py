import importlib.machinery
import importlib.util
import sys
from pathlib import Path

import pytest

ENTRY = Path(__file__).resolve().parents[2] / "scripts/ops/math-correction-compose"
pytestmark = pytest.mark.skipif(not ENTRY.exists(), reason="Operational entry absent from backend-only image")


@pytest.fixture
def entry():
    loader = importlib.machinery.SourceFileLoader("ops_entry", str(ENTRY))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_unverified_commit_is_rejected(entry):
    image = {"Config": {"Labels": {"org.opencontainers.image.revision": "a" * 40}}}
    with pytest.raises(AssertionError, match="Image/source SHA mismatch"):
        entry.verify_revision(image, "b" * 40)
    entry.verify_revision(image, "a" * 40)


def test_up_requires_explicit_commit_before_any_docker_call(entry, monkeypatch):
    monkeypatch.setattr(entry.os, "geteuid", lambda: 0)
    monkeypatch.setattr(sys, "argv", ["entry", "up"])
    called = []
    monkeypatch.setattr(entry.subprocess, "run", lambda *a, **k: called.append(a))
    with pytest.raises(AssertionError, match="Explicit source SHA required"):
        entry.main()
    assert not called


def test_global_cleanup_command_is_not_an_allowed_action(entry, monkeypatch):
    monkeypatch.setattr(entry.os, "geteuid", lambda: 0)
    monkeypatch.setattr(sys, "argv", ["entry", "down"])
    with pytest.raises(AssertionError, match="Allowed actions"):
        entry.main()
