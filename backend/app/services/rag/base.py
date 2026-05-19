from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


@dataclass(frozen=True)
class RetrievedChunk:
    id: str
    document_id: str
    chunk_index: int
    text: str
    latex: str | None
    question_id: str | None
    tokens: int | None
    metadata: dict[str, Any]
    kind: str
    score: float

    @property
    def chunk_id(self) -> str:
        return self.id


class RagProvider(Protocol):
    def health(self) -> bool: ...

    def retrieve(
        self,
        *,
        exam_id: str | None,
        question_id: str | None,
        query: str,
        top_k: int | None = None,
        kinds: list[str] | None = None,
    ) -> list[RetrievedChunk]: ...

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
    ) -> dict[str, Any]: ...
