from __future__ import annotations

from fastapi import UploadFile


class UploadValidationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_pdf_upload(upload: UploadFile) -> None:
    filename = (upload.filename or "").strip()
    if not filename.lower().endswith(".pdf"):
        raise UploadValidationError("invalid_extension", "Only .pdf files are accepted")

    content_type = (upload.content_type or "").strip().lower()
    allowed_types = {"application/pdf", "", "application/octet-stream"}
    if content_type not in allowed_types:
        raise UploadValidationError("invalid_mime_type", f"Unsupported content-type: {content_type}")

    # Basic signature check: PDF header marker should appear near the beginning.
    try:
        upload.file.seek(0)
        head = upload.file.read(1024) or b""
        upload.file.seek(0)
    except Exception as exc:
        raise UploadValidationError("unreadable_upload", "Failed to read uploaded file") from exc

    if b"%PDF-" not in head:
        raise UploadValidationError("invalid_pdf", "File does not look like a PDF")
