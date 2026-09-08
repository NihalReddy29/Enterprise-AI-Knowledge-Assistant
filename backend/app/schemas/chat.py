"""Chat and RAG query schemas."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CitationSchema(BaseModel):
    """Source citation attached to an assistant answer."""

    index: int
    document: str | None = None
    document_id: int
    page_number: int | None = None
    section: str | None = None
    text: str = ""
    similarity_score: float = 0.0


class ChatQueryRequest(BaseModel):
    """Ask a question against indexed company knowledge."""

    question: str = Field(..., min_length=1, max_length=4000)
    conversation_id: int | None = None
    document_ids: list[int] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)
    compare: bool = False
    org_id: int | None = None


class MessageResponse(BaseModel):
    """Chat message representation."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: int
    role: str
    content: str
    citations: list[CitationSchema] | None = None
    created_at: datetime


class ConversationResponse(BaseModel):
    """Conversation metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    title: str
    created_at: datetime


class ConversationDetailResponse(ConversationResponse):
    """Conversation with messages."""

    messages: list[MessageResponse] = []


class ConversationListResponse(BaseModel):
    """List of conversations."""

    conversations: list[ConversationResponse]
    total: int


class ChatQueryResponse(BaseModel):
    """RAG answer with citations and conversation linkage."""

    conversation_id: int
    question: str
    answer: str
    citations: list[CitationSchema]
    message_id: int
    provider: str
    model: str
    insufficient_information: bool = False
