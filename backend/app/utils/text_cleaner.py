"""Text cleaning utilities for extracted document content."""

import re
import unicodedata


def clean_text(text: str) -> str:
    """Normalize and clean extracted text."""
    if not text:
        return ""

    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)

    # Replace common artifacts
    text = text.replace("\x00", "")
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Collapse excessive whitespace while preserving paragraph breaks
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def is_text_sufficient(text: str, min_chars: int = 50) -> bool:
    """Check if extracted text has enough content to skip OCR."""
    if not text:
        return False
    # Count alphanumeric characters only
    alnum_count = sum(1 for c in text if c.isalnum())
    return alnum_count >= min_chars
