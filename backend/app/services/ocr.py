"""OCR service using Tesseract."""

import io
import logging
import shutil
from typing import Any

import pytesseract
from PIL import Image

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class OCRService:
    """Extract text from images using Tesseract OCR."""

    def __init__(self) -> None:
        if settings.tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = settings.tesseract_cmd

    @property
    def is_available(self) -> bool:
        """Check if Tesseract is installed and accessible."""
        return shutil.which("tesseract") is not None or bool(settings.tesseract_cmd)

    def extract_from_image(self, image_data: bytes, language: str | None = None) -> str:
        """Run OCR on image bytes and return extracted text."""
        lang = language or settings.ocr_language
        try:
            image = Image.open(io.BytesIO(image_data))
            if image.mode not in ("RGB", "L"):
                image = image.convert("RGB")
            text = pytesseract.image_to_string(image, lang=lang)
            return text.strip()
        except Exception as exc:
            logger.error("OCR failed: %s", exc)
            raise RuntimeError(f"OCR extraction failed: {exc}") from exc

    def extract_from_image_with_data(
        self, image_data: bytes, language: str | None = None
    ) -> dict[str, Any]:
        """Run OCR and return text with confidence data."""
        lang = language or settings.ocr_language
        image = Image.open(io.BytesIO(image_data))
        if image.mode not in ("RGB", "L"):
            image = image.convert("RGB")

        text = pytesseract.image_to_string(image, lang=lang)
        return {
            "text": text.strip(),
            "language": lang,
            "ocr_used": True,
        }


def get_ocr_service() -> OCRService:
    """Return OCR service instance."""
    return OCRService()
