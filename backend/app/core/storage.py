from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from fastapi import UploadFile

from app.core.config import get_settings


class StorageError(RuntimeError):
    pass


@dataclass(frozen=True)
class StoredFile:
    relative_path: str


class LocalStorage:
    def __init__(self, root_path: str) -> None:
        self.root = Path(root_path).resolve()

    def ensure_base_dirs(self) -> None:
        for sub in ("exams", "copies", "pages", "zones", "transcriptions", "reports"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    def _safe_join(self, relative_path: str) -> Path:
        rel = Path(relative_path)
        if rel.is_absolute():
            raise StorageError("Absolute paths are not allowed")
        full = (self.root / rel).resolve()
        if not str(full).startswith(str(self.root) + os.sep) and full != self.root:
            raise StorageError("Path traversal detected")
        return full

    def resolve(self, relative_path: str) -> Path:
        return self._safe_join(relative_path)

    def save_upload(self, upload: UploadFile, relative_path: str, *, max_bytes: int | None = None) -> StoredFile:
        dest = self._safe_join(relative_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        written = 0
        try:
            with dest.open("wb") as f:
                while True:
                    chunk = upload.file.read(1024 * 1024)
                    if not chunk:
                        break
                    written += len(chunk)
                    if max_bytes is not None and written > max_bytes:
                        raise StorageError(f"Upload too large (>{max_bytes} bytes)")
                    f.write(chunk)
        except StorageError:
            try:
                if dest.exists():
                    dest.unlink()
            except Exception:
                pass
            raise
        finally:
            try:
                upload.file.close()
            except Exception:
                pass
        if written == 0:
            try:
                if dest.exists():
                    dest.unlink()
            except Exception:
                pass
            raise StorageError("Empty upload")
        return StoredFile(relative_path=relative_path)

    def save_bytes(self, data: bytes, relative_path: str) -> StoredFile:
        dest = self._safe_join(relative_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return StoredFile(relative_path=relative_path)

    def open(self, relative_path: str, mode: str = "rb") -> BinaryIO:
        full = self._safe_join(relative_path)
        return full.open(mode)

    def read(self, relative_path: str) -> bytes:
        return self._safe_join(relative_path).read_bytes()

    def exists(self, relative_path: str) -> bool:
        return self._safe_join(relative_path).exists()


_storage: LocalStorage | None = None


def get_storage() -> LocalStorage:
    global _storage
    if _storage is None:
        settings = get_settings()
        if settings.STORAGE_BACKEND != "local":
            # MVP: only local implemented
            raise StorageError(f"Unsupported STORAGE_BACKEND={settings.STORAGE_BACKEND} (MVP supports local only)")
        _storage = LocalStorage(settings.LOCAL_STORAGE_PATH)
        _storage.ensure_base_dirs()
    return _storage
