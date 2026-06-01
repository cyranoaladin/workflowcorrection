"""
preprocessor.py
Prétraitement des PDF scannés avant OCR dual.
Deskew · Denoising · Segmentation par blocs (texte / formule / tableau / figure)
"""

import io
import json
import base64
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional

import cv2
import numpy as np
from pdf2image import convert_from_path
from PIL import Image


class BlockType(str, Enum):
    TEXT    = "text"
    FORMULA = "formula"
    TABLE   = "table"
    FIGURE  = "figure"


@dataclass
class Block:
    id: str
    page: int
    block_type: BlockType
    bbox: tuple[int, int, int, int]   # x, y, w, h (pixels)
    image_b64: str                     # crop base64 PNG
    raw_text_mistral: str  = ""
    raw_text_mathpix:  str  = ""
    merged_text:       str  = ""
    confidence:        float = 0.0
    flagged:           bool  = False
    human_correction:  str  = ""

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "page":             self.page,
            "block_type":       self.block_type.value,
            "bbox":             list(self.bbox),
            "image_b64":        self.image_b64,
            "raw_text_mistral": self.raw_text_mistral,
            "raw_text_mathpix": self.raw_text_mathpix,
            "merged_text":      self.merged_text,
            "confidence":       self.confidence,
            "flagged":          self.flagged,
            "human_correction": self.human_correction,
        }


@dataclass
class ProcessedPage:
    page_number: int
    width:  int
    height: int
    blocks: list[Block] = field(default_factory=list)
    full_image_b64: str = ""


# ─────────────────────────────────────────────────────────────────────────────
# Utilitaires image
# ─────────────────────────────────────────────────────────────────────────────

def _pil_to_cv(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _cv_to_b64(img_cv: np.ndarray) -> str:
    _, buf = cv2.imencode(".png", img_cv)
    return base64.b64encode(buf.tobytes()).decode()


def _deskew(img: np.ndarray) -> np.ndarray:
    """Correction de l'inclinaison par transformée de Hough."""
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    blur  = cv2.GaussianBlur(gray, (9, 9), 0)
    edges = cv2.Canny(blur, 50, 150, apertureSize=3)
    lines = cv2.HoughLines(edges, 1, np.pi / 180, 200)
    if lines is None:
        return img
    angles = []
    for rho, theta in lines[:, 0]:
        angle = np.degrees(theta) - 90
        if -10 < angle < 10:
            angles.append(angle)
    if not angles:
        return img
    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.3:
        return img
    h, w = img.shape[:2]
    M = cv2.getRotationMatrix2D((w / 2, h / 2), median_angle, 1.0)
    return cv2.warpAffine(img, M, (w, h), flags=cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_REPLICATE)


def _denoise(img: np.ndarray) -> np.ndarray:
    """Débruitage non-local means (document scan)."""
    return cv2.fastNlMeansDenoisingColored(img, None, 10, 10, 7, 21)


def _enhance_contrast(img: np.ndarray) -> np.ndarray:
    """Amélioration du contraste par CLAHE sur le canal L."""
    lab  = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    l = clahe.apply(l)
    return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2BGR)


# ─────────────────────────────────────────────────────────────────────────────
# Segmentation heuristique (fallback sans modèle ML)
# Pour production : remplacer detect_blocks par LayoutParser + MathDet
# ─────────────────────────────────────────────────────────────────────────────

def _detect_blocks_heuristic(img: np.ndarray, page: int) -> list[Block]:
    """
    Segmentation heuristique par projections de profil horizontal.
    Classe un bloc en FORMULA si sa densité de pixels sombres dans
    les bandes centrales est supérieure au seuil, sinon TEXT.
    En production, utiliser LayoutParser (pip install layoutparser[paddledetection]).
    """
    gray  = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    bw    = cv2.adaptiveThreshold(gray, 255,
                                  cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                  cv2.THRESH_BINARY_INV, 31, 10)
    # Dilatation horizontale pour regrouper les tokens d'une ligne
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 3))
    dilated = cv2.dilate(bw, kernel, iterations=2)
    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL,
                                   cv2.CHAIN_APPROX_SIMPLE)

    blocks: list[Block] = []
    h_img, w_img = img.shape[:2]
    for i, cnt in enumerate(contours):
        x, y, w, h = cv2.boundingRect(cnt)
        if w < 40 or h < 15 or w > w_img * 0.98:
            continue
        # Heuristique formule : ratio pixels noirs, présence signes isolés
        crop_bw = bw[y:y+h, x:x+w]
        black_ratio = np.count_nonzero(crop_bw) / (w * h)
        # Les formules ont tendance à avoir des densités de pixels intermédiaires
        # et des connexions verticales plus nombreuses
        vert_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, 5))
        vert_comp   = cv2.dilate(crop_bw, vert_kernel, iterations=1)
        vc_contours, _ = cv2.findContours(vert_comp, cv2.RETR_EXTERNAL,
                                          cv2.CHAIN_APPROX_SIMPLE)
        n_components = len(vc_contours)
        is_formula = (black_ratio > 0.04 and black_ratio < 0.35
                      and n_components > 3
                      and h > 25)

        crop_color = img[y:y+h, x:x+w]
        b64 = _cv_to_b64(crop_color)
        blocks.append(Block(
            id=f"p{page:03d}_b{i:04d}",
            page=page,
            block_type=BlockType.FORMULA if is_formula else BlockType.TEXT,
            bbox=(x, y, w, h),
            image_b64=b64,
        ))
    # Tri de haut en bas
    blocks.sort(key=lambda b: (b.bbox[1], b.bbox[0]))
    return blocks


# ─────────────────────────────────────────────────────────────────────────────
# Interface publique
# ─────────────────────────────────────────────────────────────────────────────

def preprocess_pdf(pdf_path: str | Path, dpi: int = 300) -> list[ProcessedPage]:
    """
    Convertit un PDF scanné en liste de ProcessedPage avec blocs segmentés.
    
    Args:
        pdf_path: chemin vers le PDF
        dpi: résolution de rendu (300 minimum recommandé)
    
    Returns:
        Liste de ProcessedPage prête pour le dual OCR
    """
    pages_pil = convert_from_path(str(pdf_path), dpi=dpi, fmt="png")
    processed: list[ProcessedPage] = []

    for i, pil_img in enumerate(pages_pil, start=1):
        img = _pil_to_cv(pil_img)
        img = _deskew(img)
        img = _denoise(img)
        img = _enhance_contrast(img)

        h, w = img.shape[:2]
        blocks = _detect_blocks_heuristic(img, page=i)
        full_b64 = _cv_to_b64(img)

        processed.append(ProcessedPage(
            page_number=i,
            width=w,
            height=h,
            blocks=blocks,
            full_image_b64=full_b64,
        ))

    return processed
