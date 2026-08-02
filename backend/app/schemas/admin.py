"""Admin dashboard schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.user import DocumentStatus, UserRole
from app.schemas.document import DocumentResponse
from app.schemas.user import UserResponse


class TopicStat(BaseModel):
    topic: str
    count: int


class StorageBreakdown(BaseModel):
    file_type: str
    count: int
    total_bytes: int


class StorageStats(BaseModel):
    total_documents: int
    total_bytes: int
    total_mb: float
    by_status: dict[str, int]
    by_type: list[StorageBreakdown]


class AdminStatistics(BaseModel):
    total_users: int
    total_documents: int
    total_questions: int
    total_conversations: int
    total_feedback: int
    helpful_feedback: int
    not_helpful_feedback: int
    indexed_documents: int
    failed_documents: int
    storage_bytes: int
    storage_mb: float
    most_searched_topics: list[TopicStat]


class QueryLogResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    conversation_id: int | None
    message_id: int | None
    question: str
    topic: str | None
    provider: str | None
    citation_count: int
    insufficient_information: bool
    created_at: datetime
    user_email: str | None = None
    user_name: str | None = None


class QueryLogListResponse(BaseModel):
    queries: list[QueryLogResponse]
    total: int


class FeedbackAdminItem(BaseModel):
    id: int
    message_id: int
    rating: int
    comment: str | None
    created_at: datetime
    message_content: str | None = None
    user_email: str | None = None


class FeedbackListResponse(BaseModel):
    feedback: list[FeedbackAdminItem]
    total: int


class AdminDocumentListResponse(BaseModel):
    documents: list[DocumentResponse]
    total: int


class FeedbackCreateRequest(BaseModel):
    rating: int = Field(..., ge=0, le=1, description="1 = helpful, 0 = not helpful")
    comment: str | None = Field(default=None, max_length=2000)


class FeedbackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message_id: int
    rating: int
    comment: str | None
    created_at: datetime
