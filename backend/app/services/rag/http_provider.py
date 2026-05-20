from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from typing import Any

import httpx

from app.services.rag.base import RetrievedChunk

logger = logging.getLogger(__name__)


class RagAuthError(RuntimeError):
    pass


class HttpRagProvider:
    def __init__(
        self,
        *,
        base_url: str,
        token: str,
        auth_header: str = "Authorization",
        timeout: float = 30.0,
        collection: str = "rag_math_correction",
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._headers = (
            {auth_header: f"Bearer {token}"} if auth_header.lower() == "authorization" else {auth_header: token}
        )
        self._timeout = httpx.Timeout(connect=5.0, read=timeout, write=timeout, pool=5.0)
        self._collection = collection
        self._transport = transport
        self._sleep = sleep

    def health(self) -> bool:
        try:
            response = self._request("GET", "/health", retries=1)
            return response.status_code == 200
        except RuntimeError:
            return False

    def retrieve(
        self,
        *,
        exam_id: str | None,
        question_id: str | None,
        query: str,
        top_k: int | None = None,
        kinds: list[str] | None = None,
    ) -> list[RetrievedChunk]:
        filters: dict[str, Any] = {"metadata": {}}
        if exam_id:
            filters["metadata"]["exam_id"] = str(exam_id)
        if question_id:
            filters["metadata"]["question_id"] = question_id
        if kinds:
            filters["metadata"]["kind"] = kinds[0] if len(kinds) == 1 else {"$in": kinds}

        response = self._request(
            "POST",
            "/rag/query",
            json={
                "query": query,
                "collection": self._collection,
                "top_k": top_k or 5,
                "filters": filters,
            },
        )
        payload = response.json()
        return [self._map_hit(hit) for hit in payload.get("hits", [])]

    def ingest_document(
        self,
        *,
        exam_id: str | None,
        kind: str,
        source_path: str,
        content_hash: str,
        title: str | None,
        chunks_or_text: Any,
        metadata: dict[str, Any] | None = None,
        force: bool = False,
    ) -> dict[str, Any]:
        merged_metadata = {
            "exam_id": str(exam_id) if exam_id else None,
            "kind": kind,
            "source_path": source_path,
            "content_hash": content_hash,
            **(metadata or {}),
        }
        text = chunks_or_text if isinstance(chunks_or_text, str) else "\n\n".join(c.text for c in chunks_or_text)
        if not force:
            dedup = self._request(
                "POST",
                "/ingest/check-duplicates",
                json={"sources": [source_path], "collection": self._collection},
            ).json()
            if any(item.get("already_ingested") for item in dedup.get("results", [])):
                return {
                    "status": "skipped",
                    "chunks_count": 0,
                    "collection": self._collection,
                }

        hints = {
            "collection": self._collection,
            "title": title or source_path,
            **{key: str(value) for key, value in merged_metadata.items() if value is not None},
        }
        safe_name = source_path.replace("/", "_") if source_path else "document"
        if not safe_name.endswith(".md"):
            safe_name += ".md"
        response = self._request(
            "POST",
            "/ingest/upload-files",
            files=[("files", (safe_name, text.encode("utf-8"), "text/markdown"))],
            params={"metadata": json.dumps(hints), "mode": "text"},
        )
        payload = response.json()
        # Normalize upload-files response to match downstream expectations
        if "total_added" in payload and "chunks_count" not in payload:
            payload["chunks_count"] = payload["total_added"]
        payload.setdefault("collection", self._collection)
        return payload

    def _request(self, method: str, path: str, *, retries: int = 3, **kwargs: Any) -> httpx.Response:
        url = f"{self._base_url}{path}"
        last_exc: Exception | None = None
        for attempt in range(retries):
            try:
                with httpx.Client(timeout=self._timeout, transport=self._transport) as client:
                    response = client.request(method, url, headers=self._headers, **kwargs)
                if response.status_code in {401, 403}:
                    raise RagAuthError("rag_http_auth_failed")
                if response.status_code >= 500 and attempt < retries - 1:
                    self._sleep(0.2 * (2**attempt))
                    continue
                response.raise_for_status()
                return response
            except RagAuthError:
                raise
            except httpx.HTTPError as exc:
                last_exc = exc
                if attempt < retries - 1:
                    self._sleep(0.2 * (2**attempt))
                    continue
        logger.warning("RAG HTTP request failed: method=%s path=%s", method, path)
        raise RuntimeError("rag_http_request_failed") from last_exc

    @staticmethod
    def _map_hit(hit: dict[str, Any]) -> RetrievedChunk:
        metadata = hit.get("metadata") or {}
        return RetrievedChunk(
            id=str(hit.get("id", "")),
            document_id=str(metadata.get("document_id", "")),
            chunk_index=int(metadata.get("chunk_index", 0) or 0),
            text=str(hit.get("document") or hit.get("text") or ""),
            latex=metadata.get("latex"),
            question_id=metadata.get("question_id"),
            tokens=int(metadata["tokens"]) if metadata.get("tokens") is not None else None,
            metadata=metadata,
            kind=str(metadata.get("kind", "")),
            score=float(hit.get("score", 0.0) or 0.0),
        )
