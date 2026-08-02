"""Helpers for citation source highlighting."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class TextSpan:
    start: int
    end: int
    matched_text: str


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def find_highlight_spans(page_text: str, excerpt: str, max_matches: int = 5) -> list[TextSpan]:
    """Find excerpt occurrences in page text (exact, then fuzzy whitespace-normalized)."""
    if not page_text or not excerpt:
        return []

    excerpt = excerpt.strip()
    if not excerpt:
        return []

    spans: list[TextSpan] = []

    # Exact case-insensitive search first
    pattern = re.escape(excerpt)
    for match in re.finditer(pattern, page_text, flags=re.IGNORECASE):
        spans.append(TextSpan(match.start(), match.end(), match.group(0)))
        if len(spans) >= max_matches:
            return spans

    if spans:
        return spans

    # Fallback: search a shortened excerpt (first ~180 chars of meaningful text)
    short = normalize_whitespace(excerpt)[:180]
    if len(short) < 12:
        return []

    # Build flexible whitespace regex
    flexible = re.escape(short).replace(r"\ ", r"\s+")
    for match in re.finditer(flexible, page_text, flags=re.IGNORECASE | re.DOTALL):
        spans.append(TextSpan(match.start(), match.end(), match.group(0)))
        if len(spans) >= max_matches:
            break

    if spans:
        return spans

    # Last resort: find best overlapping sentence/paragraph containing key tokens
    tokens = [t for t in re.findall(r"[A-Za-z0-9]{4,}", short.lower())][:6]
    if not tokens:
        return []

    best: TextSpan | None = None
    best_score = 0
    for paragraph in re.split(r"\n{2,}", page_text):
        lower = paragraph.lower()
        score = sum(1 for token in tokens if token in lower)
        if score > best_score and score >= max(1, len(tokens) // 2):
            start = page_text.find(paragraph)
            if start >= 0:
                best = TextSpan(start, start + len(paragraph), paragraph)
                best_score = score

    return [best] if best else []


def render_highlighted_html(page_text: str, spans: list[TextSpan]) -> str:
    """Return plain text with [[HL]] markers around matches (frontend converts to mark)."""
    if not spans:
        return page_text

    ordered = sorted(spans, key=lambda s: s.start)
    parts: list[str] = []
    cursor = 0
    for span in ordered:
        if span.start < cursor:
            continue
        parts.append(page_text[cursor : span.start])
        parts.append("[[HL]]")
        parts.append(page_text[span.start : span.end])
        parts.append("[[/HL]]")
        cursor = span.end
    parts.append(page_text[cursor:])
    return "".join(parts)
