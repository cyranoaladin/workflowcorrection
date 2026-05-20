"""Chunking service — splits documents into embeddable chunks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import tiktoken

_QUESTION_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:Q(?:uestion)?\s*(\d+)|Exercice\s+(\d+))",
    re.IGNORECASE | re.MULTILINE,
)


@dataclass
class Chunk:
    """A single chunk of text ready to embed."""

    text: str
    latex: str | None = None
    question_id: str | None = None
    chunk_index: int = 0
    tokens: int = 0
    metadata: dict = field(default_factory=dict)


def _count_tokens(text: str, encoding_name: str = "cl100k_base") -> int:
    """Count tokens using tiktoken."""
    try:
        enc = tiktoken.get_encoding(encoding_name)
        return len(enc.encode(text))
    except Exception:
        # Fallback: rough estimate
        return len(text) // 4


def chunk_rubric_json(rubric: dict) -> list[Chunk]:
    """Create one chunk per question from the rubric JSON.

    Expected format: {"questions": [{"id": "Q1", "label": "...", "points_max": 4, "criteria": [...], "expected_answer": "..."}]}
    """
    questions = rubric.get("questions", [])
    chunks: list[Chunk] = []

    for i, q in enumerate(questions):
        qid = str(q.get("id", f"Q{i+1}"))
        parts = [f"Question {qid}: {q.get('label', '')}"]
        parts.append(f"Points max: {q.get('points_max', 0)}")

        criteria = q.get("criteria", [])
        if criteria:
            parts.append("Critères: " + "; ".join(str(c) for c in criteria))

        expected = q.get("expected_answer", "")
        if expected:
            parts.append(f"Réponse attendue: {expected}")

        text = "\n".join(parts)
        chunks.append(
            Chunk(
                text=text,
                latex=expected if "$" in str(expected) or "\\" in str(expected) else None,
                question_id=qid,
                chunk_index=i,
                tokens=_count_tokens(text),
            )
        )

    return chunks


def chunk_correction_pdf(text_per_page: list[str], rubric_questions: list[dict]) -> list[Chunk]:
    """Chunk a correction PDF by question using heuristic regex matching.

    Tries to split the full text into sections per question based on patterns like
    "Question 1", "Q1", "Exercice 2", etc. Falls back to page-based chunking.
    """
    full_text = "\n\n".join(text_per_page)

    # Build question id list from rubric
    q_ids = [str(q.get("id", f"Q{i+1}")) for i, q in enumerate(rubric_questions)]

    # Find all question boundaries
    matches = list(_QUESTION_PATTERN.finditer(full_text))

    if not matches:
        # Fallback: one chunk per page
        return _chunk_by_pages(text_per_page, question_id=None)

    chunks: list[Chunk] = []
    for idx, match in enumerate(matches):
        start = match.start()
        end = matches[idx + 1].start() if idx + 1 < len(matches) else len(full_text)
        section = full_text[start:end].strip()

        # Determine question_id from the match
        q_num = match.group(1) or match.group(2)
        question_id = _match_question_id(q_num, q_ids)

        # Extract LaTeX fragments
        latex_frags = re.findall(r"\$[^$]+\$|\\\[.+?\\\]|\\\(.+?\\\)", section, re.DOTALL)
        latex = "\n".join(latex_frags) if latex_frags else None

        chunks.append(
            Chunk(
                text=section,
                latex=latex,
                question_id=question_id,
                chunk_index=idx,
                tokens=_count_tokens(section),
            )
        )

    return chunks


def chunk_generic_pdf(
    text: str,
    max_tokens: int = 400,
    overlap: int = 50,
    overlap_tokens: int | None = None,
) -> list[Chunk]:
    """Chunk generic text (syllabus, user_doc) by paragraph with token-sized overlap."""
    if not text.strip():
        return []
    overlap_size = overlap if overlap_tokens is None else overlap_tokens

    paragraphs = re.split(r"\n{2,}", text)
    chunks: list[Chunk] = []
    current_parts: list[str] = []
    current_tokens = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_tokens = _count_tokens(para)

        if current_tokens + para_tokens > max_tokens and current_parts:
            # Flush current chunk
            chunk_text = "\n\n".join(current_parts)
            latex_frags = re.findall(r"\$[^$]+\$|\\\[.+?\\\]|\\\(.+?\\\)", chunk_text, re.DOTALL)
            chunks.append(
                Chunk(
                    text=chunk_text,
                    latex="\n".join(latex_frags) if latex_frags else None,
                    chunk_index=len(chunks),
                    tokens=_count_tokens(chunk_text),
                )
            )
            if overlap_size > 0:
                overlap_text = _tail_by_token_budget(chunk_text, overlap_size)
                current_parts = [overlap_text] if overlap_text else []
                current_tokens = _count_tokens(overlap_text) if overlap_text else 0
            else:
                current_parts = []
                current_tokens = 0

        current_parts.append(para)
        current_tokens += para_tokens

    # Final chunk
    if current_parts:
        chunk_text = "\n\n".join(current_parts)
        latex_frags = re.findall(r"\$[^$]+\$|\\\[.+?\\\]|\\\(.+?\\\)", chunk_text, re.DOTALL)
        chunks.append(
            Chunk(
                text=chunk_text,
                latex="\n".join(latex_frags) if latex_frags else None,
                chunk_index=len(chunks),
                tokens=_count_tokens(chunk_text),
            )
        )

    return chunks


def _tail_by_token_budget(text: str, token_budget: int) -> str:
    """Return the shortest word suffix whose token count is at least token_budget."""
    if token_budget <= 0:
        return ""
    words = text.split()
    suffix: list[str] = []
    for word in reversed(words):
        suffix.insert(0, word)
        if _count_tokens(" ".join(suffix)) >= token_budget:
            break
    return " ".join(suffix)


def _chunk_by_pages(pages: list[str], question_id: str | None) -> list[Chunk]:
    """Fallback: one chunk per page."""
    chunks: list[Chunk] = []
    for i, page in enumerate(pages):
        if not page.strip():
            continue
        chunks.append(
            Chunk(
                text=page.strip(),
                question_id=question_id,
                chunk_index=i,
                tokens=_count_tokens(page),
            )
        )
    return chunks


def _match_question_id(q_num: str | None, q_ids: list[str]) -> str | None:
    """Try to match a detected question number to a rubric question ID."""
    if not q_num:
        return None

    # Direct match: "Q1", "q1", "1"
    candidates = [f"Q{q_num}", f"q{q_num}", q_num]
    for candidate in candidates:
        if candidate in q_ids:
            return candidate

    # Case-insensitive search
    for qid in q_ids:
        if qid.lower() == f"q{q_num}" or qid == q_num:
            return qid

    return f"Q{q_num}"
