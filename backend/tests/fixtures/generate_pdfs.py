from __future__ import annotations

from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

FIXTURE_DIR = Path(__file__).resolve().parent


def _write_pdf(path: Path, lines: list[str]) -> None:
    c = canvas.Canvas(str(path), pagesize=A4)
    y = 800
    for line in lines:
        c.drawString(72, y, line)
        y -= 22
    c.showPage()
    c.save()


def main() -> None:
    _write_pdf(
        FIXTURE_DIR / "correction.pdf",
        [
            "Correction E2E",
            "Q1: La derivee de f(x)=x^2 est f'(x)=2x.",
            "Q2: Une primitive de x^2 est x^3/3.",
        ],
    )
    _write_pdf(
        FIXTURE_DIR / "student_copy.pdf",
        [
            "Copie eleve E2E",
            "Q1: f'(x)=2x.",
            "Q2: La primitive est x^3/3.",
        ],
    )


if __name__ == "__main__":
    main()
