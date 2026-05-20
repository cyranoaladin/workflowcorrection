from __future__ import annotations

import base64
import logging
from pathlib import Path

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def call_mathpix_image(image_path: str) -> dict:
    settings = get_settings()
    source = "mathpix"

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
    if not settings.MATHPIX_APP_ID or not settings.MATHPIX_APP_KEY:
        return {
            "source": source,
            "status": "error",
            "raw_text": None,
            "raw_latex": None,
            "raw_json": {},
            "confidence": 0,
            "error_message": "missing_mathpix_keys",
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

    try:
        b64 = base64.b64encode(img.read_bytes()).decode("ascii")
        data_uri = f"data:image/png;base64,{b64}"
        payload = {
            "src": data_uri,
            "formats": ["text", "latex_styled"],
            "math_inline_delimiters": ["$", "$"],
            "rm_spaces": True,
        }
        headers = {
            "app_id": settings.MATHPIX_APP_ID,
            "app_key": settings.MATHPIX_APP_KEY,
            "Content-Type": "application/json",
        }

        timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0)
        with httpx.Client(timeout=timeout) as client:
            r = client.post("https://api.mathpix.com/v3/text", json=payload, headers=headers)

        raw_json = {}
        try:
            raw_json = r.json()
        except Exception:
            raw_json = {"_non_json_response": r.text[:2000]}

        # Mathpix frequently returns errors with HTTP 200 and `error`/`error_info`.
        if isinstance(raw_json, dict) and (raw_json.get("error") or (raw_json.get("error_info") or {}).get("id")):
            error_info = raw_json.get("error_info") or {}
            error_id = error_info.get("id") or "mathpix_error"
            error_msg = error_info.get("message") or raw_json.get("error") or "Mathpix error"
            logger.warning("Mathpix API error id=%s", error_id)
            return {
                "source": source,
                "status": "error",
                "raw_text": None,
                "raw_latex": None,
                "raw_json": raw_json,
                "confidence": 0,
                "error_message": f"{error_id}: {error_msg}",
            }

        if r.status_code >= 400:
            logger.warning("Mathpix error status=%s", r.status_code)
            return {
                "source": source,
                "status": "error",
                "raw_text": None,
                "raw_latex": None,
                "raw_json": raw_json,
                "confidence": 0,
                "error_message": f"mathpix_http_{r.status_code}",
            }

        return {
            "source": source,
            "status": "ok",
            "raw_text": raw_json.get("text"),
            "raw_latex": raw_json.get("latex_styled"),
            "raw_json": raw_json,
            "confidence": raw_json.get("confidence"),
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
        logger.exception("Mathpix call failed")
        return {
            "source": source,
            "status": "error",
            "raw_text": None,
            "raw_latex": None,
            "raw_json": {},
            "confidence": 0,
            "error_message": f"{type(e).__name__}: {e}",
        }
