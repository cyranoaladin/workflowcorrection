"""
exporter.py
Génération des sorties finales après fusion et correction humaine.
Formats : LaTeX compilable · JSON structuré · Markdown annoté
"""

import json
import re
from datetime import datetime
from pathlib import Path

from .preprocessor import Block, BlockType, ProcessedPage
from .fusion import compute_stats


# ─────────────────────────────────────────────────────────────────────────────
# Export JSON (format canonique pour Korrigo / Nexus)
# ─────────────────────────────────────────────────────────────────────────────

def export_json(
    pages: list[ProcessedPage],
    source_file: str = "",
    student_id: str = "",
    output_path: str | Path | None = None,
) -> dict:
    """Exporte la copie corrigée en JSON structuré."""
    stats = compute_stats(pages)

    doc = {
        "meta": {
            "source_file":      source_file,
            "student_id":       student_id,
            "processed_at":     datetime.utcnow().isoformat() + "Z",
            "ocr_engines":      ["mistral_document_ai", "mathpix"],
            "stats":            stats,
        },
        "pages": []
    }

    for page in pages:
        page_dict = {
            "page_number": page.page_number,
            "blocks": [_block_to_export(b) for b in page.blocks],
        }
        doc["pages"].append(page_dict)

    if output_path:
        Path(output_path).write_text(
            json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return doc


def _block_to_export(block: Block) -> dict:
    text = block.human_correction if block.human_correction else block.merged_text
    return {
        "id":           block.id,
        "type":         block.block_type.value,
        "text":         text,
        "confidence":   block.confidence,
        "flagged":      block.flagged,
        "was_corrected": bool(block.human_correction),
        "bbox":         block.bbox,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Export Markdown
# ─────────────────────────────────────────────────────────────────────────────

def export_markdown(
    pages: list[ProcessedPage],
    output_path: str | Path | None = None,
) -> str:
    """Exporte en Markdown avec annotations de confiance."""
    lines = []
    for page in pages:
        lines.append(f"\n## Page {page.page_number}\n")
        for block in page.blocks:
            text = block.human_correction or block.merged_text
            if block.block_type == BlockType.FORMULA:
                lines.append(f"\n$$\n{text}\n$$\n")
            else:
                lines.append(text + "\n")
            if block.flagged and not block.human_correction:
                lines.append(
                    f"> ⚠️ *Bloc flaggé — confiance {block.confidence:.0%}*\n"
                )

    md = "\n".join(lines)
    if output_path:
        Path(output_path).write_text(md, encoding="utf-8")
    return md


# ─────────────────────────────────────────────────────────────────────────────
# Export LaTeX compilable
# ─────────────────────────────────────────────────────────────────────────────

LATEX_PREAMBLE = r"""\documentclass[12pt,a4paper]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage[french]{babel}
\usepackage{amsmath,amssymb,amsthm}
\usepackage{geometry}
\usepackage{xcolor}
\usepackage{mdframed}
\geometry{margin=2.5cm}

\definecolor{flagcolor}{RGB}{220, 100, 0}

\newenvironment{flaggedblock}{%
  \begin{mdframed}[linecolor=flagcolor,linewidth=1pt,
                   backgroundcolor=flagcolor!5]%
  \color{flagcolor}\small\textit{[Bloc à vérifier]}\\[2pt]%
  \normalcolor\normalsize
}{%
  \end{mdframed}%
}

\begin{document}
"""

LATEX_FOOTER = r"\end{document}"


def _escape_latex_text(text: str) -> str:
    """Échappe les caractères spéciaux LaTeX dans un texte brut."""
    # Ne pas échapper si c'est déjà du LaTeX (contient \)
    if '\\' in text or '$' in text:
        return text
    replacements = [
        ('&', r'\&'), ('%', r'\%'), ('#', r'\#'),
        ('_', r'\_'), ('^', r'\^{}'), ('{', r'\{'), ('}', r'\}'),
        ('~', r'\textasciitilde{}'), ('<', r'\textless{}'),
        ('>', r'\textgreater{}'),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def export_latex(
    pages: list[ProcessedPage],
    title: str = "Copie d'élève",
    output_path: str | Path | None = None,
) -> str:
    """Exporte en fichier LaTeX compilable (pdflatex)."""
    lines = [LATEX_PREAMBLE]
    lines.append(f"\\title{{{title}}}\n\\date{{{datetime.now().strftime('%d/%m/%Y')}}}\n\\maketitle\n")

    for page in pages:
        lines.append(f"\n\\section*{{Page {page.page_number}}}\n")
        for block in page.blocks:
            text = block.human_correction or block.merged_text
            if not text or text == "[ILLISIBLE]":
                lines.append("\\textit{[illisible]}\n\n")
                continue

            env_open  = "\\begin{flaggedblock}\n" if (block.flagged and not block.human_correction) else ""
            env_close = "\\end{flaggedblock}\n"   if (block.flagged and not block.human_correction) else ""

            if block.block_type == BlockType.FORMULA:
                # Entoure d'un environnement equation si pas déjà formaté
                if not text.strip().startswith('\\begin{') and '$$' not in text:
                    formatted = f"\\[\n{text}\n\\]\n"
                elif '$$' in text:
                    formatted = text.replace('$$', '').strip()
                    formatted = f"\\[\n{formatted}\n\\]\n"
                else:
                    formatted = text + "\n"
                lines.append(env_open + formatted + env_close)
            else:
                escaped = _escape_latex_text(text)
                lines.append(env_open + escaped + "\n\n" + env_close)

    lines.append(LATEX_FOOTER)
    latex = "\n".join(lines)

    if output_path:
        Path(output_path).write_text(latex, encoding="utf-8")
    return latex
