from __future__ import annotations

import json
import logging

import httpx
from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def audit_correction(corrections: list[dict], total_points: float, rubric_questions: list[dict]) -> dict:
    """
    Audit the consistency and fairness of grading results using LLM.

    corrections: list of grade_question() results
    total_points: max total points for the exam
    rubric_questions: original rubric questions list

    Returns:
        {
            "audit_passed": bool,
            "overall_confidence": float,
            "needs_human_review": bool,
            "flags": list[str],         # issues found
            "summary": str,
            "status": "ok" | "error"
        }
    """
    settings = get_settings()

    # Rule-based checks (no LLM needed)
    flags: list[str] = []

    total_awarded = sum(
        c.get("points_awarded") or 0.0
        for c in corrections
        if c.get("status") == "ok" and c.get("points_awarded") is not None
    )

    if total_awarded > total_points:
        flags.append(f"total_exceeds_max: {total_awarded} > {total_points}")

    for c in corrections:
        if c.get("status") == "error":
            flags.append(f"grading_error on {c.get('question_id')}: {c.get('error_message')}")
        if c.get("needs_human_review"):
            flags.append(f"human_review_needed: {c.get('question_id')}")
        if c.get("confidence", 1.0) < 0.5:
            flags.append(f"low_confidence on {c.get('question_id')}: {c.get('confidence'):.2f}")

    missing_ids = {q.get("id") for q in rubric_questions} - {c.get("question_id") for c in corrections}
    for mid in missing_ids:
        flags.append(f"missing_grade: question {mid} not graded")

    needs_human_review = bool(flags)
    overall_confidence = (
        sum(c.get("confidence", 0) or 0 for c in corrections) / len(corrections) if corrections else 0.0
    )

    if not settings.OPENAI_API_KEY or not corrections:
        return {
            "audit_passed": not flags,
            "overall_confidence": overall_confidence,
            "needs_human_review": needs_human_review,
            "flags": flags,
            "summary": "Audit règles uniquement (LLM non disponible)"
            if not settings.OPENAI_API_KEY
            else "Aucune correction à auditer",
            "status": "ok",
        }

    corrections_summary = json.dumps(
        [
            {
                "question_id": c.get("question_id"),
                "points_max": c.get("points_max"),
                "points_awarded": c.get("points_awarded"),
                "confidence": c.get("confidence"),
                "justification": (c.get("justification") or "")[:300],
            }
            for c in corrections
        ],
        ensure_ascii=False,
        indent=2,
    )

    system_prompt = (
        "Tu es un auditeur pédagogique expert en évaluation de copies de mathématiques.\n"
        "Tu analyses la cohérence et la qualité d'une correction automatique.\n"
        "Tu réponds UNIQUEMENT en JSON valide."
    )
    user_prompt = f"""Voici les résultats de correction automatique pour un examen de {total_points} points.

Corrections par question :
{corrections_summary}

Problèmes déjà détectés automatiquement : {json.dumps(flags, ensure_ascii=False)}

Donne ton verdict d'audit en JSON :
{{
  "audit_passed": <true si la correction te semble globalement fiable>,
  "additional_flags": ["<problème supplémentaire éventuel>"],
  "summary": "<résumé de l'audit en 2-3 phrases>",
  "recommendation": "validate" | "review_partial" | "review_full"
}}"""

    try:
        client_kwargs = {"api_key": settings.OPENAI_API_KEY}
        base_url = getattr(settings, "OPENAI_BASE_URL", None)
        if base_url:
            client_kwargs["base_url"] = base_url

        client = OpenAI(**client_kwargs)
        resp = client.chat.completions.create(
            model=settings.OPENAI_AUDIT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0,
            max_tokens=512,
            timeout=httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=10.0),
            response_format={"type": "json_object"},
        )

        raw = resp.choices[0].message.content or ""
        parsed = json.loads(raw)

        all_flags = flags + parsed.get("additional_flags", [])

        return {
            "audit_passed": bool(parsed.get("audit_passed", not flags)),
            "overall_confidence": overall_confidence,
            "needs_human_review": not parsed.get("audit_passed", True) or bool(flags),
            "flags": all_flags,
            "summary": parsed.get("summary", ""),
            "recommendation": parsed.get("recommendation", "review_partial"),
            "status": "ok",
        }

    except Exception as e:
        logger.exception("audit_service: LLM audit failed")
        return {
            "audit_passed": not flags,
            "overall_confidence": overall_confidence,
            "needs_human_review": needs_human_review,
            "flags": flags,
            "summary": f"Audit LLM échoué: {e}",
            "status": "error",
        }
