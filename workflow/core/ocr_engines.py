"""
ocr_engines.py  — v2
Appels asynchrones aux deux moteurs OCR :
  - Mistral Document AI  →  POST /v1/ocr  (endpoint natif, modèle mistral-ocr-latest)
  - Mathpix              →  POST /v3/text  (par bloc image crop)

Mistral OCR reçoit le PDF entier en base64 et retourne le Markdown structuré
page par page avec scores de confiance. Mathpix est appelé en parallèle sur
les seuls blocs de type FORMULA pour son expertise LaTeX.
"""

import asyncio
import base64
import os
from pathlib import Path
from typing import Optional

import httpx

from .preprocessor import Block, BlockType, ProcessedPage


# ─────────────────────────────────────────────────────────────────────────────
# Configuration (depuis variables d'environnement / .env)
# ─────────────────────────────────────────────────────────────────────────────

MISTRAL_API_KEY  = os.getenv("MISTRAL_API_KEY", "")
MATHPIX_APP_ID   = os.getenv("MATHPIX_APP_ID", "")
MATHPIX_APP_KEY  = os.getenv("MATHPIX_APP_KEY", "")

# ── Mistral OCR natif ──────────────────────────────────────────────────────
MISTRAL_OCR_ENDPOINT = "https://api.mistral.ai/v1/ocr"
MISTRAL_OCR_MODEL    = "mistral-ocr-latest"   # alias stable → pointe sur mistral-ocr-2512

# ── Mathpix ────────────────────────────────────────────────────────────────
MATHPIX_ENDPOINT = "https://api.mathpix.com/v3/text"

TIMEOUT = httpx.Timeout(120.0)   # 2 min ; les grands PDF prennent du temps


# ─────────────────────────────────────────────────────────────────────────────
# MISTRAL DOCUMENT AI  —  endpoint /v1/ocr
# ─────────────────────────────────────────────────────────────────────────────

async def mistral_ocr_pdf(
    client: httpx.AsyncClient,
    pdf_path: str | Path,
    pages: list[ProcessedPage],
) -> list[ProcessedPage]:
    """
    Envoie le PDF entier à Mistral OCR (/v1/ocr).
    - Modèle : mistral-ocr-latest
    - Format de réponse : Markdown par page + confidence_scores par mot
    - Une seule requête pour tout le PDF (bien moins cher que bloc par bloc)

    Le Markdown de chaque page est ensuite distribué aux blocs de la page.
    """
    # Encode le PDF en base64
    pdf_bytes = Path(pdf_path).read_bytes()
    pdf_b64   = base64.b64encode(pdf_bytes).decode()

    payload = {
        "model": MISTRAL_OCR_MODEL,
        "document": {
            "type":          "document_url",
            # data-URI base64 directement supportée par l'API
            "document_url":  f"data:application/pdf;base64,{pdf_b64}",
        },
        "table_format":                   "markdown",   # tableaux en Markdown
        "include_image_base64":           False,        # on a déjà les images
        "confidence_scores_granularity":  "word",       # scores par mot
        # extract_header / extract_footer : False par défaut (intégré au Markdown)
    }
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type":  "application/json",
    }

    try:
        r = await client.post(
            MISTRAL_OCR_ENDPOINT, json=payload, headers=headers, timeout=TIMEOUT
        )
        r.raise_for_status()
        data = r.json()
    except httpx.HTTPStatusError as e:
        err = f"[ERREUR_MISTRAL_OCR HTTP {e.response.status_code}: {e.response.text[:200]}]"
        for page in pages:
            for block in page.blocks:
                block.raw_text_mistral = err
        return pages
    except Exception as e:
        err = f"[ERREUR_MISTRAL_OCR: {e}]"
        for page in pages:
            for block in page.blocks:
                block.raw_text_mistral = err
        return pages

    # Réponse : {"pages": [{"index": 0, "markdown": "...", "confidence_scores": {...}}, ...]}
    ocr_pages: list[dict] = data.get("pages", [])

    # Construction d'un index page_index → résultat OCR
    ocr_by_page: dict[int, dict] = {}
    for op in ocr_pages:
        idx = op.get("index", 0)   # 0-based dans la réponse Mistral
        ocr_by_page[idx] = op

    for page in pages:
        page_idx = page.page_number - 1   # notre numérotation est 1-based
        ocr_page = ocr_by_page.get(page_idx, {})
        markdown  = ocr_page.get("markdown", "")
        conf_data = ocr_page.get("confidence_scores", {}) or {}
        avg_conf  = conf_data.get("average_page_confidence_score", 0.75)

        # Distribue le Markdown global à chaque bloc de la page
        # (segmentation fine par bbox réservée à une version avec layout parsing ML)
        # Pour l'instant : tous les blocs TEXT d'une page reçoivent le même Markdown
        # et on laisse le moteur de fusion trier selon le type de bloc.
        for block in page.blocks:
            block.raw_text_mistral = markdown
            # On stocke la confiance page comme confiance initiale du bloc
            # (sera affinée par la fusion)
            if not block.confidence:
                block.confidence = float(avg_conf)

    return pages


# ─────────────────────────────────────────────────────────────────────────────
# Variante image (si on veut envoyer des pages individuelles en PNG)
# Utile quand le PDF n'est pas disponible — envoie chaque page comme image_url
# ─────────────────────────────────────────────────────────────────────────────

async def mistral_ocr_page_image(
    client: httpx.AsyncClient,
    page: ProcessedPage,
) -> str:
    """
    Envoie une page (full_image_b64) à Mistral OCR en mode image_url.
    Retourne le Markdown extrait.
    """
    payload = {
        "model": MISTRAL_OCR_MODEL,
        "document": {
            "type":      "image_url",
            "image_url": f"data:image/png;base64,{page.full_image_b64}",
        },
        "table_format":                  "markdown",
        "confidence_scores_granularity": "page",
    }
    headers = {
        "Authorization": f"Bearer {MISTRAL_API_KEY}",
        "Content-Type":  "application/json",
    }
    try:
        r = await client.post(
            MISTRAL_OCR_ENDPOINT, json=payload, headers=headers, timeout=TIMEOUT
        )
        r.raise_for_status()
        data = r.json()
        pages = data.get("pages", [])
        if pages:
            return pages[0].get("markdown", "")
        return ""
    except Exception as e:
        return f"[ERREUR_MISTRAL_OCR_IMAGE: {e}]"


async def mistral_ocr_pages_images(
    client: httpx.AsyncClient,
    pages: list[ProcessedPage],
) -> list[ProcessedPage]:
    """
    Fallback : envoie chaque page comme image séparée (si pas de PDF brut dispo).
    Lance toutes les pages en parallèle.
    """
    tasks = [mistral_ocr_page_image(client, p) for p in pages]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for page, result in zip(pages, results):
        markdown = result if isinstance(result, str) else f"[ERREUR: {result}]"
        for block in page.blocks:
            block.raw_text_mistral = markdown

    return pages


# ─────────────────────────────────────────────────────────────────────────────
# MATHPIX  —  endpoint /v3/text  (par bloc FORMULA uniquement)
# ─────────────────────────────────────────────────────────────────────────────

async def _mathpix_ocr_block(
    client: httpx.AsyncClient,
    block: Block,
) -> tuple[str, float]:
    """
    Envoie un bloc image crop à Mathpix.
    Retourne (latex_ou_text, confidence).
    """
    payload = {
        "src": f"data:image/png;base64,{block.image_b64}",
        "formats":      ["text", "latex_styled"],
        "data_options": {
            "include_asciimath": True,
            "include_latex":     True,
        },
        "include_detected_alphabets": True,
        "include_line_data":          True,
        "confidence_threshold":       0.0,   # on veut tout, filtrage dans fusion.py
    }
    headers = {
        "app_id":       MATHPIX_APP_ID,
        "app_key":      MATHPIX_APP_KEY,
        "Content-Type": "application/json",
    }
    try:
        r = await client.post(
            MATHPIX_ENDPOINT, json=payload, headers=headers, timeout=TIMEOUT
        )
        r.raise_for_status()
        data = r.json()

        # Priorité latex_styled pour les formules, text sinon
        if block.block_type == BlockType.FORMULA:
            text = (data.get("latex_styled") or data.get("text") or "").strip()
        else:
            text = (data.get("text") or "").strip()

        confidence = float(data.get("confidence", 0.0))
        return text, confidence

    except Exception as e:
        return f"[ERREUR_MATHPIX: {e}]", 0.0


async def mathpix_ocr_formula_blocks(
    client: httpx.AsyncClient,
    pages: list[ProcessedPage],
) -> list[ProcessedPage]:
    """
    Lance Mathpix uniquement sur les blocs FORMULA (économie de crédits).
    Les blocs TEXT conservent raw_text_mathpix = "" (fusion.py le gère).
    """
    formula_blocks = [
        b for p in pages for b in p.blocks
        if b.block_type == BlockType.FORMULA
    ]

    if not formula_blocks:
        return pages

    tasks   = [_mathpix_ocr_block(client, b) for b in formula_blocks]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    for block, result in zip(formula_blocks, results):
        if isinstance(result, Exception):
            block.raw_text_mathpix = f"[ERREUR: {result}]"
            block.confidence = 0.0
        else:
            text, conf = result
            block.raw_text_mathpix = text
            block.confidence = conf   # confiance Mathpix (référence pour fusion.py)

    return pages


# ─────────────────────────────────────────────────────────────────────────────
# Orchestration principale : dual OCR parallèle
# ─────────────────────────────────────────────────────────────────────────────

async def run_dual_ocr(
    pages: list[ProcessedPage],
    pdf_path: Optional[str | Path] = None,
) -> list[ProcessedPage]:
    """
    Lance Mistral OCR ET Mathpix en parallèle.

    - Si pdf_path est fourni → Mistral reçoit le PDF entier via /v1/ocr (1 requête)
    - Sinon → Mistral reçoit chaque page comme image séparée (fallback)
    - Mathpix reçoit uniquement les blocs FORMULA en parallèle

    Args:
        pages:    liste de ProcessedPage issue de preprocess_pdf()
        pdf_path: chemin vers le PDF original (recommandé pour Mistral)

    Returns:
        pages enrichies avec raw_text_mistral et raw_text_mathpix
    """
    async with httpx.AsyncClient() as client:
        if pdf_path and Path(pdf_path).exists():
            # Mode optimal : PDF entier → Mistral, formules → Mathpix
            mistral_task = mistral_ocr_pdf(client, pdf_path, pages)
        else:
            # Fallback : images page par page
            mistral_task = mistral_ocr_pages_images(client, pages)

        mathpix_task = mathpix_ocr_formula_blocks(client, pages)

        # Exécution parallèle
        await asyncio.gather(mistral_task, mathpix_task)

    return pages
