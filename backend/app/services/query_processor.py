"""Query preprocessing service for RAG pipeline."""

import re

MAX_QUERY_LENGTH = 4000


def preprocess_query(question: str) -> str:
    """Clean and normalize a user question for embedding, lexical search, and retrieval.

    - Normalizes whitespace (strips leading/trailing and collapses internal runs).
    - Removes non-printable/control characters while preserving punctuation and technical terms.
    - Handles empty/whitespace-only input safely.
    """
    if not question:
        return ""

    # Remove non-printable control characters (except standard whitespace)
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", question)

    # Collapse multiple whitespaces and newlines into single spaces
    cleaned = " ".join(cleaned.split())

    # Match the chat request limit so direct service callers cannot create an
    # unexpectedly large embedding request.
    return cleaned.strip()[:MAX_QUERY_LENGTH]
