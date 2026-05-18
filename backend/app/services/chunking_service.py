from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Chunk:
    text: str
    question_id: str | None = None
    latex: str | None = None
    tokens: int | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


_QUESTION_RE = re.compile(r"(?im)^\s*(?:Q(?:uestion)?|Exercice)\s*([0-9]+)\b[^\n]*")


def chunk_rubric_json(rubric: dict) -> list[Chunk]:
    """Create one retrieval chunk per rubric question."""
    chunks: list[Chunk] = []
    for q in rubric.get("questions", []):
        if not isinstance(q, dict):
            continue
        qid = str(q.get("id") or "").strip()
        if not qid:
            continue
        criteria = q.get("criteria") or []
        criteria_text = "\n".join(f"- {c}" for c in criteria)
        expected = q.get("expected_answer") or ""
        text = "\n".join(
            part
            for part in (
                f"Question {qid}",
                str(q.get("label") or ""),
                f"Barème: {q.get('points_max')} points" if q.get("points_max") is not None else "",
                criteria_text,
                f"Réponse attendue: {expected}" if expected else "",
            )
            if part
        )
        chunks.append(
            Chunk(
                text=text,
                question_id=qid,
                tokens=_estimate_tokens(text),
                metadata={"kind": "rubric", "points_max": q.get("points_max")},
            )
        )
    return chunks


def chunk_correction_pdf(text_per_page: list[str], rubric_questions: list[dict]) -> list[Chunk]:
    """Split correction text by French question headers and map sections to rubric ids."""
    full_text = "\n\n".join(t for t in text_per_page if t and t.strip())
    if not full_text.strip():
        return []

    matches = list(_QUESTION_RE.finditer(full_text))
    if not matches:
        return [
            Chunk(
                text=full_text.strip(),
                question_id=None,
                tokens=_estimate_tokens(full_text),
                metadata={"kind": "correction", "mapping": "unmatched"},
            )
        ]

    id_by_number = {
        str(index + 1): str(q.get("id"))
        for index, q in enumerate(rubric_questions)
        if isinstance(q, dict) and q.get("id")
    }

    chunks: list[Chunk] = []
    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(full_text)
        section = full_text[start:end].strip()
        if not section:
            continue
        question_id = id_by_number.get(match.group(1), f"Q{match.group(1)}")
        chunks.append(
            Chunk(
                text=section,
                question_id=question_id,
                tokens=_estimate_tokens(section),
                metadata={"kind": "correction", "mapping": "header_regex"},
            )
        )
    return chunks


def chunk_generic_pdf(text: str, max_tokens: int = 400, overlap: int = 50) -> list[Chunk]:
    """Chunk generic document text by paragraphs with simple overlap and LaTeX-aware boundaries."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[Chunk] = []
    current: list[str] = []
    current_tokens = 0

    for paragraph in paragraphs:
        paragraph_tokens = _estimate_tokens(paragraph)
        if current and current_tokens + paragraph_tokens > max_tokens and _latex_balanced("\n\n".join(current)):
            chunk_text = "\n\n".join(current).strip()
            chunks.append(Chunk(text=chunk_text, tokens=_estimate_tokens(chunk_text), metadata={"kind": "generic"}))
            current = _overlap_tail(current, overlap)
            current_tokens = _estimate_tokens("\n\n".join(current))

        current.append(paragraph)
        current_tokens += paragraph_tokens

    if current:
        chunk_text = "\n\n".join(current).strip()
        chunks.append(Chunk(text=chunk_text, tokens=_estimate_tokens(chunk_text), metadata={"kind": "generic"}))

    return chunks


def _estimate_tokens(text: str) -> int:
    return max(1, len(re.findall(r"\S+", text)))


def _latex_balanced(text: str) -> bool:
    return text.count("$") % 2 == 0 and text.count("\\begin{") == text.count("\\end{")


def _overlap_tail(paragraphs: list[str], overlap: int) -> list[str]:
    if overlap <= 0:
        return []
    tail: list[str] = []
    total = 0
    for paragraph in reversed(paragraphs):
        tokens = _estimate_tokens(paragraph)
        if tail and total + tokens > overlap:
            break
        tail.insert(0, paragraph)
        total += tokens
    return tail
