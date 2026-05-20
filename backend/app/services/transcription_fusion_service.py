from __future__ import annotations

import difflib
from typing import Any


def _norm(s: str | None) -> str:
    return (s or "").strip()


def _similarity(a: str | None, b: str | None) -> float:
    aa = _norm(a)
    bb = _norm(b)
    if not aa and not bb:
        return 1.0
    if not aa or not bb:
        return 0.0
    return difflib.SequenceMatcher(a=aa, b=bb).ratio()


def fuse_transcriptions(
    *,
    page_id: str,
    mathpix: dict[str, Any] | None,
    azure: dict[str, Any] | None,
    openai: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Conservative fusion: picks a primary text source, records disagreements, and
    flags `needs_human_review` when sources diverge or confidence is low.

    Inputs are expected to be normalized OCR payloads (raw_text/raw_latex/raw_json/confidence).
    """

    m_text = (mathpix or {}).get("raw_text")
    a_text = (azure or {}).get("raw_text")
    o_text = (openai or {}).get("raw_text")

    m_latex = (mathpix or {}).get("raw_latex")
    o_latex = (openai or {}).get("raw_latex")

    if not (m_text or a_text or o_text):
        raise ValueError("No OCR inputs available for fusion")

    # Choose a primary text. Heuristic: OpenAI Vision often captures full-page context,
    # Azure is good for plain text, Mathpix is good for math-heavy content.
    final_text = o_text or a_text or m_text
    final_latex = m_latex or o_latex

    disagreements: list[dict[str, Any]] = []

    # Detect major text divergence
    ratios = {
        "mathpix_vs_azure": _similarity(m_text, a_text),
        "mathpix_vs_openai": _similarity(m_text, o_text),
        "azure_vs_openai": _similarity(a_text, o_text),
    }
    divergent_pairs = [k for k, v in ratios.items() if v < 0.7]
    if divergent_pairs:
        disagreements.append(
            {
                "field": "text",
                "mathpix": m_text,
                "azure": a_text,
                "openai": o_text,
                "similarity": ratios,
            }
        )

    # Detect latex disagreement if both present
    if _norm(m_latex) and _norm(o_latex) and _similarity(m_latex, o_latex) < 0.7:
        disagreements.append({"field": "latex", "mathpix": m_latex, "azure": None, "openai": o_latex})

    # Conservative confidence: min of provided confidences (or 0.0 if missing)
    confidences: list[float] = []
    for v in (
        (mathpix or {}).get("confidence"),
        (azure or {}).get("confidence"),
        (openai or {}).get("confidence"),
    ):
        try:
            if v is None:
                continue
            confidences.append(float(v))
        except Exception:
            continue
    confidence = min(confidences) if confidences else 0.0

    needs_human_review = False
    if disagreements:
        needs_human_review = True
    if confidence and confidence < 0.6:
        needs_human_review = True
    if isinstance(final_text, str) and "[illisible]" in final_text:
        needs_human_review = True

    return {
        "source": "fusion",
        "page_id": page_id,
        "final_text": final_text,
        "final_latex": final_latex,
        "disagreements": disagreements,
        "confidence": confidence,
        "needs_human_review": needs_human_review,
    }
