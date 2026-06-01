# OCR Maths — Pipeline dual Mistral Document AI + Mathpix

Pipeline de transcription de copies de mathématiques scannées avec croisement
de deux moteurs OCR et révision humaine ciblée sur les blocs à faible confiance.

---

## Architecture

```
ocr_maths/
├── core/
│   ├── preprocessor.py   # Deskew · Denoising · Segmentation blocs
│   ├── ocr_engines.py    # Mistral Document AI + Mathpix (async parallèle)
│   ├── fusion.py         # Moteur de consensus par Levenshtein + LaTeX
│   └── exporter.py       # Export JSON · Markdown · LaTeX compilable
├── api/
│   └── server.py         # Backend FastAPI
├── static/
│   └── index.html        # Interface de révision web
├── cli.py                # Ligne de commande (batch)
├── requirements.txt
└── .env                  # Clés API (ne pas committer)
```

---

## Installation

### 1. Dépendances système

```bash
# Ubuntu/Debian
sudo apt-get install -y poppler-utils libglib2.0-0 libsm6 libxrender1 libxext6

# macOS
brew install poppler
```

### 2. Environnement Python

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Variables d'environnement

Créer un fichier `.env` à la racine :

```ini
MISTRAL_API_KEY=sk-...           # https://console.mistral.ai/
MATHPIX_APP_ID=your_app_id       # https://mathpix.com/dashboard
MATHPIX_APP_KEY=your_app_key
```

---

## Usage

### Interface web (recommandé)

```bash
cd api
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

Ouvrir http://localhost:8000 — glisser-déposer un PDF, ajuster les paramètres,
suivre la progression, réviser les blocs flaggés, exporter.

### Ligne de commande (batch)

```bash
# Une seule copie
python cli.py --input copie_eleve.pdf --output ./resultats/

# Dossier entier
python cli.py --input ./copies/ --output ./resultats/ --threshold 0.85 --dpi 300

# Seuil plus strict (moins de révisions auto, plus de sécurité)
python cli.py --input copie.pdf --threshold 0.92
```

### Pipeline Python direct

```python
import asyncio
from core.preprocessor import preprocess_pdf
from core.ocr_engines   import run_dual_ocr
from core.fusion        import fuse_all_pages, compute_stats
from core.exporter      import export_json

async def process(pdf_path):
    pages  = preprocess_pdf(pdf_path, dpi=300)
    pages  = await run_dual_ocr(pages, pdf_path=pdf_path)
    pages  = fuse_all_pages(pages, threshold=0.85)
    stats  = compute_stats(pages)
    result = export_json(pages, output_path="output.json")
    return result, stats

result, stats = asyncio.run(process("copie.pdf"))
```

---

## Logique de fusion

| Type de bloc | Stratégie |
|---|---|
| `formula` | Mathpix prioritaire si `confidence ≥ 0.80`; sinon vote Levenshtein normalisé LaTeX |
| `text`    | Mistral prioritaire si similarité ≥ 0.90; vote pondéré si ≥ 0.70; flag si < 0.70 |
| `table`   | Mistral prioritaire (structure Markdown); Mathpix pour les cellules formules |

Un bloc est **flaggé** quand sa confiance finale < seuil (défaut 0.85).
Seuls les blocs flaggés apparaissent dans la file de révision humaine.

---

## Améliorer la fiabilité

1. **Segmentation ML** : remplacer `_detect_blocks_heuristic()` par LayoutParser :
   ```python
   pip install layoutparser[paddledetection]
   # Modèle recommandé : PubLayNet (inclut détection formules)
   ```

2. **Normalisation LaTeX avancée** :
   ```python
   pip install latexnormalizer
   from latexnormalizer import normalize
   ```

3. **Recalibration automatique** des seuils après 50 copies :
   Les corrections humaines alimentent un fichier `calibration.json` ;
   lancer `python calibrate.py` pour ajuster `DEFAULT_THRESHOLD` et `FORMULA_PRIORITY`.

---

## Coûts estimés (par copie, 4 pages A4)

| Moteur | Appels | Coût estimé |
|---|---|---|
| Mistral OCR (`/v1/ocr`, `mistral-ocr-latest`) | 1 requête PDF entier | ~$0.008 |
| Mistral OCR via Batch API | 1 requête batch | ~$0.004 |
| Mathpix `/v3/text` | blocs `FORMULA` uniquement | variable selon le nombre de formules |

Mistral propose un plan Experiment gratuit pour prototyper. En production,
le tarif OCR public est de $2 / 1 000 pages, avec 50 % de réduction via Batch API,
soit $1 / 1 000 pages. Pour 189 copies de 4 pages, cela représente 756 pages :
environ $1.51 en API directe ou $0.76 via Batch API, hors Mathpix.

---

## Intégration Korrigo / Nexus EAF

Le JSON de sortie est directement compatible avec le schéma Korrigo :

```json
{
  "meta": { "student_id": "...", "ocr_engines": [...], "stats": {...} },
  "pages": [
    {
      "page_number": 1,
      "blocks": [
        { "id": "p001_b0001", "type": "formula", "text": "\\frac{1}{2}x^2",
          "confidence": 0.94, "flagged": false }
      ]
    }
  ]
}
```

Passer `student_id` à `export_json()` pour le lier à l'anonymat Korrigo.
