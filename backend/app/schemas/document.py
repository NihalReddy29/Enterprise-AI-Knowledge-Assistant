"""Pydantic schemas for document resources."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import DocumentStatus


class DocumentResponse(BaseModel):
    """Public document representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    file_type: str
    owner_id: int
    org_id: int | None = None
    file_size: int
    page_count: int | None
    chunk_count: int | None = None
    status: DocumentStatus
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated document list."""

    documents: list[DocumentResponse]
    total: int


class DocumentUploadResponse(BaseModel):
    """Response after successful upload."""

    document: DocumentResponse
    message: str = "Document uploaded and queued for processing"


class ExtractedPageResponse(BaseModel):
    """A single extracted page/section."""

    page_number: int
    text: str
    section: str | None = None
    ocr_used: bool = False


class DocumentContentResponse(BaseModel):
    """Extracted text content of a document."""

    document_id: int
    filename: str
    status: DocumentStatus
    pages: list[ExtractedPageResponse]
    total_pages: int
    ocr_used: bool


class HighlightMatch(BaseModel):
    """A matched span within page text for source highlighting."""

    start: int
    end: int
    matched_text: str


class DocumentHighlightResponse(BaseModel):
    """Highlight payload for citation source viewer."""

    document_id: int
    filename: str
    file_type: str
    page_number: int
    section: str | None = None
    page_text: str
    excerpt: str
    matches: list[HighlightMatch]
    total_pages: int | None = None
