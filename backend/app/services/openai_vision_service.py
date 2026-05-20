from __future__ import annotations

import base64
import json
import logging
from pathlib import Path

import httpx
from openai import OpenAI

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def call_openai_vision_for_transcription(image_path: str, question_context: str) -> dict:
    settings = get_settings()
    source = "openai_vision"

    if not settings.OCR_ENABLE_PAID_CALLS:
        return {
            "source": source,
            "status": "error",
            "raw_text": None,
            "raw_latex": None,
            "raw_json": {},
            "confidence": 0,
            "error_message": "paid_calls_disabled",
        }
    if not settings.OPENAI_API_KEY:
        return {
            "source": source,
            "status": "error",
            "raw_text": None,
            "raw_latex": None,
            "raw_json": {},
            "confidence": 0,
            "error_message": "missing_openai_api_key",
        }

    img = Path(image_path)
    if not img.exists():
        return {
            "source": source,
            "status": "error",
            "raw_text": None,
            "raw_latex": None,
            "raw_json": {},
            "confidence": 0,
            "error_message": f"image_not_found: {img}",
        }

    system_instructions = (
        "Tu lis une page de copie manuscrite de mathématiques.\n"
        "Tu dois transcrire fidèlement ce qui est visible.\n"
        "Tu ne dois pas corriger.\n"
        "Tu ne dois pas noter.\n"
        "Tu ne dois pas inventer.\n"
        "Si une zone est illisible, indique [illisible].\n"
        "Conserve les expressions mathématiques en LaTeX quand c’est possible.\n"
        "Retourne un JSON strict."
    )

    schema = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "visible_questions": {"type": "array", "items": {"type": "string"}},
            "transcription": {"type": "string"},
            "latex_fragments": {"type": "array", "items": {"type": "string"}},
            "uncertain_zones": {"type": "array", "items": {"type": "string"}},
            "confidence": {"type": "number"},
        },
        "required": [
            "visible_questions",
            "transcription",
            "latex_fragments",
            "uncertain_zones",
            "confidence",
        ],
    }

    try:
        b64 = base64.b64encode(img.read_bytes()).decode("ascii")
        data_uri = f"data:image/png;base64,{b64}"

        user_text = "Transcris fidèlement tout le contenu visible de la page."
        if question_context:
            user_text += f"\n\nContexte (optionnel):\n{question_context}"

        client = OpenAI(api_key=settings.OPENAI_API_KEY)
        resp = client.responses.create(
            model=settings.OPENAI_VISION_MODEL,
            instructions=system_instructions,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": user_text},
                        {
                            "type": "input_image",
                            "image_url": data_uri,
                            "detail": "high",
                        },
                    ],
                }
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "page_transcription",
                    "schema": schema,
                    "strict": True,
                }
            },
            temperature=0,
            timeout=httpx.Timeout(connect=10.0, read=90.0, write=10.0, pool=10.0),
        )

        raw_text = getattr(resp, "output_text", None)
        if not raw_text:
            # Fallback: resp.output might still contain the message
            raw_text = str(resp)

        parsed: dict = {}
        try:
            parsed = json.loads(raw_text)
        except Exception:
            # Keep the raw text for debugging, but mark as error.
            return {
                "source": source,
                "status": "error",
                "raw_text": None,
                "raw_latex": None,
                "raw_json": {"raw_output_text": raw_text[:4000]},
                "confidence": 0,
                "error_message": "invalid_json_output",
            }

        # Attach non-sensitive metadata (helps debugging & token accounting).
        try:
            usage = resp.usage.model_dump() if getattr(resp, "usage", None) is not None else None
        except Exception:
            usage = None
        parsed["_openai_meta"] = {
            "response_id": getattr(resp, "id", None),
            "usage": usage,
        }

        transcription = parsed.get("transcription")
        latex_fragments = parsed.get("latex_fragments")
        raw_latex = None
        if isinstance(latex_fragments, list) and latex_fragments:
            raw_latex = "\n".join(str(x) for x in latex_fragments if x is not None)

        return {
            "source": source,
            "status": "ok",
            "raw_text": transcription if isinstance(transcription, str) else None,
            "raw_latex": raw_latex,
            "raw_json": parsed,
            "confidence": parsed.get("confidence"),
            "error_message": None,
        }
    except httpx.TimeoutException:
        return {
            "source": source,
            "status": "error",
            "raw_text": None,
            "raw_latex": None,
            "raw_json": {},
            "confidence": 0,
            "error_message": "timeout",
        }
    except Exception as e:
        logger.exception("OpenAI vision call failed")
        return {
            "source": source,
            "status": "error",
            "raw_text": None,
            "raw_latex": None,
            "raw_json": {},
            "confidence": 0,
            "error_message": f"{type(e).__name__}: {e}",
        }
