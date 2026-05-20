from __future__ import annotations

import logging
import time
from pathlib import Path

import httpx

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def call_azure_read(image_path: str) -> dict:
    settings = get_settings()
    source = "azure"

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
    if not settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT or not settings.AZURE_DOCUMENT_INTELLIGENCE_KEY:
        return {
            "source": source,
            "status": "error",
            "raw_text": None,
            "raw_latex": None,
            "raw_json": {},
            "confidence": 0,
            "error_message": "missing_azure_document_intelligence_keys",
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

    endpoint = settings.AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT.rstrip("/")
    url = f"{endpoint}/documentintelligence/documentModels/prebuilt-read:analyze?api-version=2024-11-30"
    fallback_url = f"{endpoint}/formrecognizer/documentModels/prebuilt-read:analyze?api-version=2024-11-30"

    headers = {
        "Ocp-Apim-Subscription-Key": settings.AZURE_DOCUMENT_INTELLIGENCE_KEY,
        "Content-Type": "application/octet-stream",
    }

    timeout = httpx.Timeout(connect=10.0, read=45.0, write=10.0, pool=10.0)
    try:
        with httpx.Client(timeout=timeout) as client:
            r = client.post(url, headers=headers, content=img.read_bytes())
            if r.status_code == 404:
                r = client.post(fallback_url, headers=headers, content=img.read_bytes())

            if r.status_code >= 400:
                return {
                    "source": source,
                    "status": "error",
                    "raw_text": None,
                    "raw_latex": None,
                    "raw_json": {"status_code": r.status_code, "body": r.text[:2000]},
                    "confidence": 0,
                    "error_message": f"azure_http_{r.status_code}",
                }

            op_loc = r.headers.get("Operation-Location") or r.headers.get("operation-location")
            if not op_loc:
                return {
                    "source": source,
                    "status": "error",
                    "raw_text": None,
                    "raw_latex": None,
                    "raw_json": {
                        "status_code": r.status_code,
                        "headers": dict(r.headers),
                    },
                    "confidence": 0,
                    "error_message": "missing_operation_location",
                }

            started = time.monotonic()
            raw_json: dict = {}
            while True:
                if time.monotonic() - started > 60:
                    return {
                        "source": source,
                        "status": "error",
                        "raw_text": None,
                        "raw_latex": None,
                        "raw_json": raw_json or {},
                        "confidence": 0,
                        "error_message": "timeout",
                    }
                gr = client.get(op_loc, headers=headers)
                try:
                    raw_json = gr.json()
                except Exception:
                    raw_json = {"_non_json_response": gr.text[:2000]}

                if gr.status_code >= 400:
                    return {
                        "source": source,
                        "status": "error",
                        "raw_text": None,
                        "raw_latex": None,
                        "raw_json": raw_json,
                        "confidence": 0,
                        "error_message": f"azure_http_{gr.status_code}",
                    }

                status = (raw_json or {}).get("status")
                if status in ("succeeded", "failed"):
                    break
                time.sleep(1.0)

        if (raw_json or {}).get("status") != "succeeded":
            return {
                "source": source,
                "status": "error",
                "raw_text": None,
                "raw_latex": None,
                "raw_json": raw_json or {},
                "confidence": 0,
                "error_message": "azure_failed",
            }

        analyze = (raw_json or {}).get("analyzeResult") or {}
        raw_text = analyze.get("content")
        if not raw_text:
            # Fallback: stitch lines if present
            lines: list[str] = []
            for p in analyze.get("pages") or []:
                for line in p.get("lines") or []:
                    content = line.get("content")
                    if content:
                        lines.append(content)
            raw_text = "\n".join(lines) if lines else None

        return {
            "source": source,
            "status": "ok",
            "raw_text": raw_text,
            "raw_latex": None,
            "raw_json": raw_json or {},
            "confidence": None,
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
        logger.exception("Azure OCR call failed")
        return {
            "source": source,
            "status": "error",
            "raw_text": None,
            "raw_latex": None,
            "raw_json": {},
            "confidence": 0,
            "error_message": f"{type(e).__name__}: {e}",
        }
