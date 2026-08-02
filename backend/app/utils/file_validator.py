"""File upload validation utilities."""

import mimetypes
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.config import get_settings

settings = get_settings()

EXTENSION_MIME_MAP = {
    "pdf": {"application/pdf"},
    "docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
    "pptx": {
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "application/octet-stream",
    },
    "txt": {"text/plain", "application/octet-stream"},
    "png": {"image/png"},
    "jpg": {"image/jpeg"},
    "jpeg": {"image/jpeg"},
    "tiff": {"image/tiff"},
    "bmp": {"image/bmp"},
}


def get_file_extension(filename: str) -> str:
    """Return lowercase file extension without dot."""
    return Path(filename).suffix.lstrip(".").lower()


def validate_upload_file(file: UploadFile, file_size: int) -> str:
    """Validate uploaded file type and size. Returns normalized extension."""
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Filename is required",
        )

    extension = get_file_extension(file.filename)
    if extension not in settings.allowed_extensions_list:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File type '.{extension}' is not allowed. "
            f"Allowed: {', '.join(settings.allowed_extensions_list)}",
        )

    if file_size > settings.max_upload_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File exceeds maximum size of {settings.max_upload_size_mb}MB",
        )

    if file_size == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Empty files are not allowed",
        )

    content_type = file.content_type or mimetypes.guess_type(file.filename)[0]
    if content_type:
        allowed_mimes = EXTENSION_MIME_MAP.get(extension, set())
        if allowed_mimes and content_type not in allowed_mimes:
            # Allow generic octet-stream as fallback for office docs
            if content_type != "application/octet-stream":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"MIME type '{content_type}' does not match extension '.{extension}'",
                )

    return extension
