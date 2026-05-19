from __future__ import annotations

from pathlib import Path

import cv2


class ImagePreprocessError(RuntimeError):
    pass


def preprocess_image(input_path: Path, output_path: Path) -> dict:
    if not input_path.exists():
        raise ImagePreprocessError(f"Input image not found: {input_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    img = cv2.imread(str(input_path), cv2.IMREAD_COLOR)
    if img is None:
        raise ImagePreprocessError("Failed to read image")

    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    denoised = cv2.medianBlur(gray, 3)
    thresh = cv2.adaptiveThreshold(
        denoised,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        10,
    )

    ok = cv2.imwrite(str(output_path), thresh)
    if not ok:
        raise ImagePreprocessError(f"Failed to write processed image: {output_path}")

    h, w = thresh.shape[:2]
    return {"width": int(w), "height": int(h)}
