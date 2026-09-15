"""Team workspace Pydantic schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.team import (
    MessengerMessageType,
    TeamInviteStatus,
    TeamJoinRequestStatus,
    TeamMemberRole,
    TeamMemberStatus,
)
from app.schemas.chat import CitationSchema


# ---------------------------------------------------------------------------
# Team CRUD
# ---------------------------------------------------------------------------


class TeamCreate(BaseModel):
    """Payload to create a new team."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v.strip()

    @field_validator("description")
    @classmethod
    def description_strip(cls, v: str | None) -> str | None:
        if v is None:
            return None
        return v.strip() or None


class TeamUpdate(BaseModel):
    """Payload to update team metadata."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str | None) -> str | None:
        if v is not None and not v.strip():
            raise ValueError("name must not be blank")
        return v.strip() if v else None


class TeamMemberOut(BaseModel):
    """Team member with basic user info."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    user_id: int
    role: TeamMemberRole
    status: TeamMemberStatus
    joined_at: datetime
    user_email: str | None = None
    user_name: str | None = None


class TeamOut(BaseModel):
    """Team summary for list/detail responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    owner_id: int
    qdrant_collection_name: str
    created_at: datetime
    updated_at: datetime
    member_count: int = 0
    my_role: TeamMemberRole | None = None


class TeamDetail(TeamOut):
    """Team with member list."""

    members: list[TeamMemberOut] = []
    join_code: str | None = None
    pending_join_request_count: int = 0


# ---------------------------------------------------------------------------
# Join codes & requests
# ---------------------------------------------------------------------------


class TeamJoinCodePreview(BaseModel):
    """Preview a team before requesting to join."""

    team_id: int
    team_name: str
    team_description: str | None
    member_count: int


class TeamJoinRequestCreate(BaseModel):
    """Request to join a team using its join code."""

    join_code: str = Field(..., min_length=8, max_length=12)
    message: str | None = Field(default=None, max_length=500)

    @field_validator("join_code")
    @classmethod
    def join_code_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("join code must not be blank")
        return v.strip()


class TeamJoinRequestOut(BaseModel):
    """Join request for admin review."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    user_id: int
    status: TeamJoinRequestStatus
    message: str | None
    reviewed_by: int | None
    created_at: datetime
    responded_at: datetime | None
    user_email: str | None = None
    user_name: str | None = None


class TeamJoinRequestListResponse(BaseModel):
    """Pending join requests for a team."""

    requests: list[TeamJoinRequestOut]
    total: int


# ---------------------------------------------------------------------------
# Invites
# ---------------------------------------------------------------------------


class TeamInviteCreate(BaseModel):
    """Request to invite someone to a team by email."""

    email: str = Field(..., min_length=3, max_length=255)

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError("invalid email address")
        return v


class TeamInviteOut(BaseModel):
    """Team invite response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    invited_email: str
    invited_by: int | None
    token: str
    status: TeamInviteStatus
    created_at: datetime
    responded_at: datetime | None
    expires_at: datetime | None
    invite_url: str | None = None


class TeamInvitePreview(BaseModel):
    """Public preview of an invite (token-authenticated)."""

    team_name: str
    team_description: str | None
    inviter_name: str | None
    inviter_email: str | None
    status: TeamInviteStatus
    expires_at: datetime | None


class TeamInviteListResponse(BaseModel):
    """Pending invites for the current user."""

    invites: list[TeamInviteOut]
    total: int


# ---------------------------------------------------------------------------
# Team RAG chat
# ---------------------------------------------------------------------------


class TeamChatQueryRequest(BaseModel):
    """Ask a question against a team's knowledge base."""

    question: str = Field(..., min_length=1, max_length=4000)
    conversation_id: int | None = None
    document_ids: list[int] | None = None
    top_k: int | None = Field(default=None, ge=1, le=20)


class TeamChatMessageOut(BaseModel):
    """Team RAG chat message."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    conversation_id: int
    user_id: int | None
    role: str
    content: str
    citations: list[CitationSchema] | None = None
    created_at: datetime
    author_name: str | None = None


class TeamConversationOut(BaseModel):
    """Team conversation metadata."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    title: str
    created_at: datetime


class TeamConversationDetailOut(TeamConversationOut):
    """Team conversation with messages."""

    messages: list[TeamChatMessageOut] = []


class TeamChatQueryResponse(BaseModel):
    """RAG answer scoped to a team knowledge base."""

    conversation_id: int
    question: str
    answer: str
    citations: list[CitationSchema]
    message_id: int
    provider: str
    model: str
    insufficient_information: bool = False


# ---------------------------------------------------------------------------
# Team messenger
# ---------------------------------------------------------------------------


class TeamMessengerMessageCreate(BaseModel):
    """Send a team messenger message."""

    content: str = Field(..., min_length=1, max_length=10000)
    message_type: MessengerMessageType = MessengerMessageType.TEXT
    file_document_id: int | None = None
    reply_to_id: int | None = None


class TeamMessengerMessageOut(BaseModel):
    """Team messenger message response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    team_id: int
    sender_id: int
    content: str
    message_type: MessengerMessageType
    file_document_id: int | None
    reply_to_id: int | None
    created_at: datetime
    edited_at: datetime | None
    deleted_at: datetime | None
    sender_name: str | None = None
    read_by_user_ids: list[int] = []


class TeamMessengerMessageListResponse(BaseModel):
    """Paginated messenger history."""

    messages: list[TeamMessengerMessageOut]
    total: int
    has_more: bool = False


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------


class NotificationOut(BaseModel):
    """In-app notification."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    type: str
    title: str
    body: str | None
    payload: dict | None
    read_at: datetime | None
    created_at: datetime
