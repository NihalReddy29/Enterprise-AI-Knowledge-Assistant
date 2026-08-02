"""Semantic search schemas."""

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Semantic search query."""

    query: str = Field(..., min_length=1, max_length=2000)
    top_k: int = Field(default=5, ge=1, le=50)
    document_ids: list[int] | None = Field(
        default=None,
        description="Optional filter to search within specific documents",
    )


class SearchHit(BaseModel):
    """A single search result with citation metadata."""

    text: str
    document: str | None = None
    document_id: int
    page_number: int | None = None
    section: str | None = None
    similarity_score: float
    chunk_index: int | None = None


class SearchResponse(BaseModel):
    """Semantic search response."""

    query: str
    results: list[SearchHit]
    total: int
