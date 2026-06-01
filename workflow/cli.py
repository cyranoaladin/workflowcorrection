#!/usr/bin/env python3
"""
cli.py — Point d'entrée CLI pour traitement batch de copies PDF

Usage :
    python cli.py --input copie.pdf --threshold 0.85 --dpi 300
    python cli.py --input /dossier/copies/ --output ./resultats/
"""

import argparse
import asyncio
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Ajouter le parent au path
sys.path.insert(0, str(Path(__file__).parent))

from core.preprocessor import preprocess_pdf
from core.ocr_engines   import run_dual_ocr
from core.fusion        import fuse_all_pages, compute_stats
from core.exporter      import export_json, export_markdown, export_latex


async def process_one(pdf_path: Path, output_dir: Path, threshold: float, dpi: int, verbose: bool):
    name = pdf_path.stem
    print(f"\n[{name}] ── Prétraitement (DPI={dpi})...")
    pages = preprocess_pdf(pdf_path, dpi=dpi)
    n_blocks = sum(len(p.blocks) for p in pages)
    print(f"[{name}] ── {len(pages)} pages · {n_blocks} blocs détectés")

    print(f"[{name}] ── OCR dual (Mistral + Mathpix) en parallèle...")
    pages = await run_dual_ocr(pages, pdf_path=str(pdf_path))

    print(f"[{name}] ── Fusion par consensus (seuil={threshold})...")
    pages = fuse_all_pages(pages, threshold=threshold)

    stats = compute_stats(pages)
    print(f"[{name}] ── Stats : {stats['auto_validated']}/{stats['total_blocks']} auto-validés "
          f"· {stats['flagged']} flaggés ({stats['review_rate_pct']}%) "
          f"· confiance moy. {stats['avg_confidence']:.2%}")

    # Exports
    out_dir = output_dir / name
    out_dir.mkdir(parents=True, exist_ok=True)

    export_json(     pages, source_file=pdf_path.name, output_path=out_dir / f"{name}.json")
    export_markdown( pages, output_path=out_dir / f"{name}.md")
    export_latex(    pages, title=name, output_path=out_dir / f"{name}.tex")

    print(f"[{name}] ── Sorties dans {out_dir}/")

    if stats['flagged'] > 0:
        print(f"[{name}] ⚠  {stats['flagged']} blocs nécessitent une révision humaine.")
        print(f"         → Ouvrir http://localhost:8000 pour révision interactive")

    return stats


async def main():
    parser = argparse.ArgumentParser(description="Pipeline OCR dual pour copies de maths")
    parser.add_argument("--input",     "-i", required=True, help="Fichier PDF ou dossier")
    parser.add_argument("--output",    "-o", default="./output", help="Dossier de sortie")
    parser.add_argument("--threshold", "-t", type=float, default=0.85,
                        help="Seuil de confiance pour validation auto (0-1, défaut 0.85)")
    parser.add_argument("--dpi",       "-d", type=int, default=300,
                        help="Résolution de rendu PDF (défaut 300)")
    parser.add_argument("--verbose",   "-v", action="store_true")
    args = parser.parse_args()

    input_path  = Path(args.input)
    output_dir  = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Collecter les PDFs
    if input_path.is_dir():
        pdfs = sorted(input_path.glob("**/*.pdf"))
    elif input_path.suffix.lower() == ".pdf":
        pdfs = [input_path]
    else:
        print(f"Erreur : {input_path} n'est pas un PDF ni un dossier.")
        sys.exit(1)

    if not pdfs:
        print("Aucun PDF trouvé.")
        sys.exit(1)

    print(f"\n=== OCR Maths Pipeline ===")
    print(f"Fichiers : {len(pdfs)} PDF(s)")
    print(f"Sortie   : {output_dir}")
    print(f"Seuil    : {args.threshold}  |  DPI : {args.dpi}")
    print("=" * 28)

    all_stats = []
    for pdf in pdfs:
        try:
            stats = await process_one(pdf, output_dir, args.threshold, args.dpi, args.verbose)
            all_stats.append({**stats, "file": pdf.name})
        except Exception as e:
            print(f"[ERREUR] {pdf.name} : {e}")

    # Bilan global
    if len(all_stats) > 1:
        total_b = sum(s["total_blocks"]   for s in all_stats)
        total_f = sum(s["flagged"]         for s in all_stats)
        total_a = sum(s["auto_validated"]  for s in all_stats)
        print(f"\n=== Bilan batch ({len(all_stats)} copies) ===")
        print(f"Blocs total       : {total_b}")
        print(f"Auto-validés      : {total_a} ({total_a/total_b*100:.1f}%)")
        print(f"À réviser         : {total_f} ({total_f/total_b*100:.1f}%)")
        # Sauvegarde bilan
        bilan_path = output_dir / "bilan.json"
        bilan_path.write_text(json.dumps(all_stats, ensure_ascii=False, indent=2))
        print(f"Bilan JSON        : {bilan_path}")


if __name__ == "__main__":
    asyncio.run(main())
