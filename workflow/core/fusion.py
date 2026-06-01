"""
fusion.py
Moteur de fusion par consensus entre Mistral et Mathpix.

Stratégie :
  FORMULA  → Mathpix prioritaire si confidence ≥ seuil, sinon vote
  TEXT     → vote majoritaire par distance de Levenshtein normalisée
  Tout bloc avec confiance fusionnée < seuil_flag → flagged = True
"""

import re
import unicodedata
from difflib import SequenceMatcher

from .preprocessor import Block, BlockType, ProcessedPage


# ─────────────────────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_THRESHOLD   = 0.85   # confiance minimale pour validation auto
FORMULA_PRIORITY    = 0.80   # seuil Mathpix pour lui donner priorité sur formule
TEXT_SIMILARITY_MIN = 0.70   # similarité Levenshtein minimale pour vote


# ─────────────────────────────────────────────────────────────────────────────
# Normalisation LaTeX
# ─────────────────────────────────────────────────────────────────────────────

_LATEX_SPACES = re.compile(r'\s+')
_LATEX_REDUNDANT = re.compile(
    r'\\left\s*([({[])|\\right\s*([)}\]])'
    r'|\\,|\\;|\\!|\\:|\\quad|\\qquad'
    r'|\\mbox\{([^}]*)\}'
)

def normalize_latex(s: str) -> str:
    """
    Normalise une expression LaTeX pour comparaison.
    Supprime les espaces superflus, les commandes de taille optionnelles.
    """
    if not s:
        return ""
    # Supprime délimiteurs \left \right optionnels
    s = re.sub(r'\\left\s*', r'\\left', s)
    s = re.sub(r'\\right\s*', r'\\right', s)
    # Normalise espaces
    s = _LATEX_SPACES.sub(' ', s).strip()
    # Unifie les variantes de fraction
    s = re.sub(r'\\dfrac', r'\\frac', s)
    s = re.sub(r'\\tfrac', r'\\frac', s)
    # Supprime accolades unitaires autour d'un seul caractère : {x} → x
    s = re.sub(r'\{([^{}])\}', r'\1', s)
    return s


def normalize_text(s: str) -> str:
    """Normalise un texte brut pour comparaison."""
    if not s:
        return ""
    s = unicodedata.normalize("NFC", s)
    s = s.lower()
    s = re.sub(r'\s+', ' ', s).strip()
    return s


# ─────────────────────────────────────────────────────────────────────────────
# Mesure de similarité
# ─────────────────────────────────────────────────────────────────────────────

def levenshtein_similarity(a: str, b: str) -> float:
    """Similarité normalisée [0, 1] basée sur SequenceMatcher (Levenshtein approché)."""
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def formula_similarity(a: str, b: str) -> float:
    """Similarité entre deux expressions LaTeX (après normalisation)."""
    return levenshtein_similarity(normalize_latex(a), normalize_latex(b))


def text_similarity(a: str, b: str) -> float:
    """Similarité entre deux textes (après normalisation)."""
    return levenshtein_similarity(normalize_text(a), normalize_text(b))


# ─────────────────────────────────────────────────────────────────────────────
# Fusion d'un bloc
# ─────────────────────────────────────────────────────────────────────────────

def _fuse_formula_block(block: Block, threshold: float) -> tuple[str, float]:
    """
    Fusion pour un bloc FORMULA.
    Mathpix prioritaire si sa confiance native ≥ FORMULA_PRIORITY.
    Sinon : vote pondéré.
    """
    mp_text  = block.raw_text_mathpix.strip()
    mi_text  = block.raw_text_mistral.strip()
    mp_conf  = block.confidence       # confiance native Mathpix

    # Erreurs brutes → confiance 0
    mp_ok = not mp_text.startswith("[ERREUR")
    mi_ok = not mi_text.startswith("[ERREUR")

    if not mp_ok and not mi_ok:
        return "[ILLISIBLE]", 0.0

    if not mp_ok:
        return mi_text, 0.5

    if not mi_ok:
        return mp_text, mp_conf

    # Mathpix prioritaire si confiance suffisante
    if mp_conf >= FORMULA_PRIORITY:
        return mp_text, mp_conf

    # Sinon : compare les deux
    sim = formula_similarity(mp_text, mi_text)
    if sim >= TEXT_SIMILARITY_MIN:
        # Accord suffisant → on prend Mathpix (meilleur LaTeX)
        merged_conf = (mp_conf + 0.75) / 2  # 0.75 = confiance estimée Mistral
        return mp_text, min(merged_conf, 0.95)
    else:
        # Désaccord → on retourne Mathpix mais on flag
        return mp_text, max(mp_conf * 0.6, 0.3)


def _fuse_text_block(block: Block) -> tuple[str, float]:
    """
    Fusion pour un bloc TEXT.
    Vote token par token pondéré par la similarité globale.
    """
    mp_text = block.raw_text_mathpix.strip()
    mi_text = block.raw_text_mistral.strip()

    mp_ok = mp_text and not mp_text.startswith("[ERREUR")
    mi_ok = mi_text and not mi_text.startswith("[ERREUR")

    if not mp_ok and not mi_ok:
        return "[ILLISIBLE]", 0.0
    if not mp_ok:
        return mi_text, 0.70
    if not mi_ok:
        return mp_text, 0.65

    sim = text_similarity(mp_text, mi_text)

    if sim >= 0.90:
        # Fort accord : on prend Mistral (meilleure ponctuation/structure)
        return mi_text, 0.92

    if sim >= TEXT_SIMILARITY_MIN:
        # Accord partiel : fusion par alignement de séquences (longer wins)
        merged = mi_text if len(mi_text) >= len(mp_text) else mp_text
        return merged, 0.75

    # Désaccord fort : on prend Mistral mais on signal la divergence
    return mi_text, sim * 0.8


def fuse_block(block: Block, threshold: float = DEFAULT_THRESHOLD) -> Block:
    """Applique la stratégie de fusion selon le type de bloc."""
    if block.block_type in (BlockType.FORMULA,):
        merged, conf = _fuse_formula_block(block, threshold)
    else:
        merged, conf = _fuse_text_block(block)

    block.merged_text = merged
    block.confidence  = round(conf, 4)
    block.flagged     = conf < threshold
    return block


# ─────────────────────────────────────────────────────────────────────────────
# Fusion d'une page complète
# ─────────────────────────────────────────────────────────────────────────────

def fuse_page(page: ProcessedPage, threshold: float = DEFAULT_THRESHOLD) -> ProcessedPage:
    for block in page.blocks:
        fuse_block(block, threshold)
    return page


def fuse_all_pages(
    pages: list[ProcessedPage],
    threshold: float = DEFAULT_THRESHOLD
) -> list[ProcessedPage]:
    """
    Fusionne toutes les pages.
    Retourne des statistiques de révision dans les métadonnées.
    """
    for page in pages:
        fuse_page(page, threshold)
    return pages


# ─────────────────────────────────────────────────────────────────────────────
# Statistiques
# ─────────────────────────────────────────────────────────────────────────────

def compute_stats(pages: list[ProcessedPage]) -> dict:
    all_blocks    = [b for p in pages for b in p.blocks]
    total         = len(all_blocks)
    flagged       = sum(1 for b in all_blocks if b.flagged)
    auto_valid    = total - flagged
    avg_conf      = sum(b.confidence for b in all_blocks) / total if total else 0
    formulas      = sum(1 for b in all_blocks if b.block_type == BlockType.FORMULA)
    texts         = sum(1 for b in all_blocks if b.block_type == BlockType.TEXT)

    return {
        "total_blocks":    total,
        "auto_validated":  auto_valid,
        "flagged":         flagged,
        "review_rate_pct": round(flagged / total * 100, 1) if total else 0,
        "avg_confidence":  round(avg_conf, 3),
        "formula_blocks":  formulas,
        "text_blocks":     texts,
        "pages":           len(pages),
    }
