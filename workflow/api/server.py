"""
api/server.py
Backend FastAPI — expose :
  POST /upload          → lance le pipeline OCR
  GET  /session/{id}    → état d'une session
  GET  /review/{id}     → blocs flaggés à réviser
  POST /correction      → soumet une correction humaine
  GET  /export/{id}     → télécharge les sorties finales
  GET  /stats/{id}      → métriques d'une session
"""

import asyncio
import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Imports pipeline
import sys
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load_env_files(project_root: Path = PROJECT_ROOT, fallback_root: Optional[Path] = None) -> None:
    """Load project .env files before OCR engine modules read API keys."""
    env_paths = [project_root / ".env"]
    if fallback_root is None:
        fallback_root = project_root.parent
    if fallback_root:
        env_paths.append(fallback_root / ".env")

    for env_path in env_paths:
        if env_path.exists():
            load_dotenv(env_path, override=False)


_load_env_files()
sys.path.insert(0, str(PROJECT_ROOT))
from core.preprocessor import preprocess_pdf
from core.ocr_engines   import run_dual_ocr
from core.fusion        import fuse_all_pages, compute_stats, DEFAULT_THRESHOLD
from core.exporter      import export_json, export_markdown, export_latex


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(title="OCR Maths — Pipeline dual Mistral/Mathpix", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Session store en mémoire (pour production : Redis ou DB)
SESSIONS: dict[str, dict] = {}
WORK_DIR = Path(tempfile.mkdtemp(prefix="ocr_maths_"))


# ─────────────────────────────────────────────────────────────────────────────
# Modèles Pydantic
# ─────────────────────────────────────────────────────────────────────────────

class CorrectionRequest(BaseModel):
    session_id:  str
    block_id:    str
    correction:  str


class SessionStatus(BaseModel):
    session_id:  str
    status:      str          # pending | processing | review | done | error
    progress:    int          # 0-100
    stats:       Optional[dict] = None
    error:       Optional[str]  = None


# ─────────────────────────────────────────────────────────────────────────────
# Endpoints
# ─────────────────────────────────────────────────────────────────────────────

@app.post("/upload", response_model=SessionStatus)
async def upload_pdf(
    file:      UploadFile = File(...),
    threshold: float      = Form(DEFAULT_THRESHOLD),
    dpi:       int        = Form(300),
):
    """Upload un PDF et lance le pipeline OCR en arrière-plan."""
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(400, "Seuls les fichiers PDF sont acceptés.")

    session_id = str(uuid.uuid4())
    session_dir = WORK_DIR / session_id
    session_dir.mkdir(parents=True)

    # Sauvegarde le PDF
    pdf_path = session_dir / "input.pdf"
    with open(pdf_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    SESSIONS[session_id] = {
        "status":    "processing",
        "progress":  0,
        "pages":     None,
        "threshold": threshold,
        "filename":  file.filename,
        "error":     None,
    }

    # Lance le pipeline en arrière-plan
    asyncio.create_task(_run_pipeline(session_id, pdf_path, threshold, dpi))

    return SessionStatus(session_id=session_id, status="processing", progress=0)


async def _run_pipeline(session_id: str, pdf_path: Path, threshold: float, dpi: int):
    """Pipeline complet : prétraitement → dual OCR → fusion."""
    sess = SESSIONS[session_id]
    try:
        # Étape 1 : prétraitement
        sess["progress"] = 10
        pages = await asyncio.get_event_loop().run_in_executor(
            None, preprocess_pdf, str(pdf_path), dpi
        )
        sess["progress"] = 30

        # Étape 2 : dual OCR (Mistral reçoit le PDF entier, Mathpix les blocs formule)
        pages = await run_dual_ocr(pages, pdf_path=str(pdf_path))
        sess["progress"] = 70

        # Étape 3 : fusion
        pages = fuse_all_pages(pages, threshold)
        sess["progress"] = 90

        # Calcul des stats
        stats = compute_stats(pages)
        sess["pages"]    = pages
        sess["stats"]    = stats
        sess["status"]   = "review" if stats["flagged"] > 0 else "done"
        sess["progress"] = 100

    except Exception as e:
        sess["status"] = "error"
        sess["error"]  = str(e)


@app.get("/session/{session_id}", response_model=SessionStatus)
async def get_session(session_id: str):
    sess = SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(404, "Session introuvable.")
    return SessionStatus(
        session_id=session_id,
        status=sess["status"],
        progress=sess["progress"],
        stats=sess.get("stats"),
        error=sess.get("error"),
    )


@app.get("/review/{session_id}")
async def get_review_queue(session_id: str):
    """Retourne les blocs flaggés en attente de révision humaine."""
    sess = SESSIONS.get(session_id)
    if not sess or not sess.get("pages"):
        raise HTTPException(404, "Session ou pages introuvables.")

    pages = sess["pages"]
    queue = []
    for page in pages:
        for block in page.blocks:
            if block.flagged and not block.human_correction:
                queue.append({
                    **block.to_dict(),
                    "page_number": page.page_number,
                })
    return {"session_id": session_id, "count": len(queue), "blocks": queue}


@app.post("/correction")
async def submit_correction(req: CorrectionRequest):
    """Enregistre la correction humaine d'un bloc flaggé."""
    sess = SESSIONS.get(req.session_id)
    if not sess or not sess.get("pages"):
        raise HTTPException(404, "Session introuvable.")

    found = False
    for page in sess["pages"]:
        for block in page.blocks:
            if block.id == req.block_id:
                block.human_correction = req.correction
                block.flagged = False
                found = True
                break

    if not found:
        raise HTTPException(404, f"Bloc {req.block_id} introuvable.")

    # Recalcul des stats
    sess["stats"] = compute_stats(sess["pages"])
    remaining = sum(
        1 for p in sess["pages"]
        for b in p.blocks
        if b.flagged and not b.human_correction
    )
    if remaining == 0:
        sess["status"] = "done"

    return {"ok": True, "remaining_flagged": remaining}


@app.get("/export/{session_id}/{fmt}")
async def export_results(session_id: str, fmt: str):
    """
    Exporte les résultats dans le format demandé.
    fmt : json | markdown | latex
    """
    sess = SESSIONS.get(session_id)
    if not sess or not sess.get("pages"):
        raise HTTPException(404, "Session introuvable.")
    if sess["status"] not in ("done", "review"):
        raise HTTPException(400, "Le pipeline n'est pas terminé.")

    pages = sess["pages"]
    out_dir = WORK_DIR / session_id
    filename_base = Path(sess.get("filename", "copie")).stem

    if fmt == "json":
        out_path = out_dir / f"{filename_base}.json"
        export_json(pages, source_file=sess.get("filename", ""), output_path=out_path)
        return FileResponse(str(out_path), media_type="application/json",
                            filename=out_path.name)

    elif fmt == "markdown":
        out_path = out_dir / f"{filename_base}.md"
        export_markdown(pages, output_path=out_path)
        return FileResponse(str(out_path), media_type="text/markdown",
                            filename=out_path.name)

    elif fmt == "latex":
        out_path = out_dir / f"{filename_base}.tex"
        export_latex(pages, title=filename_base, output_path=out_path)
        return FileResponse(str(out_path), media_type="text/plain",
                            filename=out_path.name)

    else:
        raise HTTPException(400, f"Format '{fmt}' non supporté. Choisir : json, markdown, latex")


@app.get("/stats/{session_id}")
async def get_stats(session_id: str):
    sess = SESSIONS.get(session_id)
    if not sess:
        raise HTTPException(404, "Session introuvable.")
    return sess.get("stats") or {"error": "Pas encore disponible"}


@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    """Sert l'interface de révision."""
    ui_path = Path(__file__).parent.parent / "static" / "index.html"
    if ui_path.exists():
        return HTMLResponse(ui_path.read_text(encoding="utf-8"))
    return HTMLResponse("<h1>Interface non trouvée — placez index.html dans static/</h1>")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="0.0.0.0", port=8000, reload=True)
