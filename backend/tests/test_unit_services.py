from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.core.storage import LocalStorage, StorageError
from app.services.image_preprocess_service import preprocess_image


def test_local_storage_prevents_path_traversal(tmp_path: Path):
    s = LocalStorage(str(tmp_path))
    s.ensure_base_dirs()
    with pytest.raises(StorageError):
        s.save_bytes(b"nope", "../escape.txt")


def test_image_preprocess_service(tmp_path: Path):
    import cv2

    img = (np.ones((120, 80, 3), dtype=np.uint8) * 255).copy()
    cv2.putText(img, "Test", (5, 60), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)

    input_path = tmp_path / "in.png"
    output_path = tmp_path / "out.png"
    assert cv2.imwrite(str(input_path), img)

    info = preprocess_image(input_path, output_path)
    assert output_path.exists()
    assert info["width"] == 80
    assert info["height"] == 120
