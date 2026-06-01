import importlib
import inspect
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_expected_runtime_layout_exists():
    assert (ROOT / "core" / "preprocessor.py").is_file()
    assert (ROOT / "core" / "ocr_engines.py").is_file()
    assert (ROOT / "core" / "fusion.py").is_file()
    assert (ROOT / "core" / "exporter.py").is_file()
    assert (ROOT / "api" / "server.py").is_file()
    assert (ROOT / "static" / "index.html").is_file()


def test_core_modules_import_from_workflow_root(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))

    for module_name in (
        "core.preprocessor",
        "core.ocr_engines",
        "core.fusion",
        "core.exporter",
        "api.server",
    ):
        importlib.import_module(module_name)


def test_api_server_can_load_env_file_before_pipeline_import(monkeypatch, tmp_path):
    monkeypatch.syspath_prepend(str(ROOT))
    monkeypatch.delenv("MISTRAL_API_KEY", raising=False)
    (tmp_path / ".env").write_text("MISTRAL_API_KEY=test-mistral\n", encoding="utf-8")

    server = importlib.import_module("api.server")
    server._load_env_files(tmp_path, fallback_root=None)

    assert os.environ["MISTRAL_API_KEY"] == "test-mistral"


def test_mistral_ocr_uses_native_endpoint(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    ocr_engines = importlib.import_module("core.ocr_engines")

    assert ocr_engines.MISTRAL_OCR_ENDPOINT == "https://api.mistral.ai/v1/ocr"
    assert ocr_engines.MISTRAL_OCR_MODEL == "mistral-ocr-latest"
    assert "/chat/completions" not in inspect.getsource(ocr_engines)
    assert "pixtral" not in inspect.getsource(ocr_engines).lower()


def test_run_dual_ocr_accepts_pdf_path(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    ocr_engines = importlib.import_module("core.ocr_engines")
    signature = inspect.signature(ocr_engines.run_dual_ocr)

    assert "pdf_path" in signature.parameters


def test_fastapi_pipeline_passes_pdf_path_to_dual_ocr(monkeypatch):
    monkeypatch.syspath_prepend(str(ROOT))
    server = importlib.import_module("api.server")

    source = inspect.getsource(server._run_pipeline)
    assert "run_dual_ocr(pages, pdf_path=str(pdf_path))" in source
