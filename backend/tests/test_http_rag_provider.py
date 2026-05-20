from __future__ import annotations

import httpx
import pytest

from app.services.rag.http_provider import HttpRagProvider, RagAuthError


def test_http_rag_provider_retrieve_maps_hits() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/rag/query"
        assert request.headers["Authorization"] == "Bearer test-token"
        payload = httpx.Request("POST", request.url, content=request.content).read()
        assert b'"query":"derivee"' in payload
        return httpx.Response(
            200,
            json={
                "hits": [
                    {
                        "id": "chunk-1",
                        "document": "corrige Q1",
                        "metadata": {
                            "document_id": "doc-1",
                            "chunk_index": 2,
                            "kind": "correction",
                            "question_id": "Q1",
                            "tokens": 10,
                        },
                        "score": 0.12,
                    }
                ]
            },
        )

    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    )

    chunks = provider.retrieve(
        exam_id="exam-1",
        question_id="Q1",
        query="derivee",
        top_k=3,
        kinds=["correction"],
    )

    assert len(chunks) == 1
    assert chunks[0].id == "chunk-1"
    assert chunks[0].text == "corrige Q1"
    assert chunks[0].kind == "correction"
    assert chunks[0].question_id == "Q1"


def test_http_rag_provider_retrieve_empty() -> None:
    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(lambda _: httpx.Response(200, json={"hits": []})),
    )

    assert provider.retrieve(exam_id="exam-1", question_id=None, query="x") == []


def test_http_rag_provider_raises_on_unauthorized() -> None:
    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="bad-token",
        transport=httpx.MockTransport(lambda _: httpx.Response(401, json={"detail": "Unauthorized"})),
    )

    with pytest.raises(RagAuthError):
        provider.retrieve(exam_id="exam-1", question_id=None, query="x")


def test_http_rag_provider_retries_5xx() -> None:
    calls = 0

    def handler(_: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls < 3:
            return httpx.Response(500, text="temporary")
        return httpx.Response(200, json={"hits": []})

    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )

    assert provider.retrieve(exam_id="exam-1", question_id=None, query="x") == []
    assert calls == 3


def test_http_rag_provider_timeout_surfaces_as_runtime_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
        sleep=lambda _: None,
    )

    with pytest.raises(RuntimeError, match="rag_http_request_failed"):
        provider.retrieve(exam_id="exam-1", question_id=None, query="x")


def test_ingest_document_uses_upload_files_endpoint() -> None:
    """ingest_document must POST multipart to /ingest/upload-files, not JSON to /ingest."""
    captured_requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        captured_requests.append(request)
        if "/check-duplicates" in str(request.url):
            return httpx.Response(200, json={"results": [{"already_ingested": False}]})
        if "/upload-files" in str(request.url):
            return httpx.Response(
                200,
                json={"status": "ok", "total_added": 3, "total_skipped": 0, "results": []},
            )
        return httpx.Response(404)

    provider = HttpRagProvider(
        base_url="https://rag.example.test",
        token="test-token",
        transport=httpx.MockTransport(handler),
    )

    result = provider.ingest_document(
        exam_id="exam-42",
        kind="correction",
        source_path="exams/42/correction.md",
        content_hash="abc123",
        title="Correction Exam 42",
        chunks_or_text="# Q1\nLa derivee de x^2 est 2x.",
    )

    assert result["status"] == "ok"
    assert result["total_added"] == 3

    # Verify the upload request
    upload_req = [r for r in captured_requests if "/upload-files" in str(r.url)][0]
    assert upload_req.method == "POST"
    assert "multipart/form-data" in upload_req.headers.get("content-type", "")

    # Verify metadata query param contains collection and metadata
    url_str = str(upload_req.url)
    assert "metadata=" in url_str
    assert "mode=text" in url_str
