"""Utilities for query topic extraction and analytics."""

from __future__ import annotations

import re
from collections import Counter


STOPWORDS = {
    "a",
    "an",
    "the",
    "is",
    "are",
    "was",
    "were",
    "what",
    "which",
    "who",
    "whom",
    "how",
    "why",
    "when",
    "where",
    "do",
    "does",
    "did",
    "can",
    "could",
    "should",
    "would",
    "our",
    "my",
    "your",
    "their",
    "of",
    "in",
    "on",
    "for",
    "to",
    "and",
    "or",
    "with",
    "about",
    "from",
    "into",
    "me",
    "we",
    "you",
    "it",
    "this",
    "that",
    "please",
    "tell",
    "give",
}


def extract_topic(question: str) -> str:
    """Derive a short topic label from a question for analytics."""
    tokens = re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", question.lower())
    keywords = [t for t in tokens if t not in STOPWORDS]
    if not keywords:
        return "general"
    # Prefer first meaningful keyword phrase (up to 3 tokens)
    return " ".join(keywords[:3])


def top_topics(questions: list[str], limit: int = 8) -> list[tuple[str, int]]:
    counter: Counter[str] = Counter()
    for question in questions:
        counter[extract_topic(question)] += 1
    return counter.most_common(limit)
