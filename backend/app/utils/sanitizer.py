"""Input sanitization utilities."""

import html
import re


def sanitize_text(value: str, max_length: int = 10000) -> str:
    """Sanitize user-provided text input."""
    cleaned = html.escape(value.strip())
    return cleaned[:max_length]


def sanitize_filename(filename: str) -> str:
    """Remove dangerous characters from filenames."""
    cleaned = re.sub(r"[^\w\s.\-]", "", filename)
    return cleaned.strip()[:255] or "unnamed_file"
