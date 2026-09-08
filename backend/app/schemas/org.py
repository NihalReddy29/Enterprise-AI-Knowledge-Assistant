"""Organization Pydantic schemas."""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.user import OrgRole


# ---------------------------------------------------------------------------
# Org creation / update
# ---------------------------------------------------------------------------


class OrgCreate(BaseModel):
    """Payload to create a new organization."""

    name: str = Field(..., min_length=1, max_length=255)

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("name must not be blank")
        return v.strip()


# ---------------------------------------------------------------------------
# Responses
# ---------------------------------------------------------------------------


class OrgMemberResponse(BaseModel):
    """Organization member with basic user info."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    org_id: int
    user_id: int
    role: OrgRole
    joined_at: datetime
    user_email: str | None = None
    user_name: str | None = None


class OrgResponse(BaseModel):
    """Lightweight organization response."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    created_by: int | None
    created_at: datetime
    member_count: int = 0
    my_role: OrgRole | None = None


class OrgDetail(OrgResponse):
    """Organization with full member list."""

    members: list[OrgMemberResponse] = []


# ---------------------------------------------------------------------------
# Invite
# ---------------------------------------------------------------------------


class InviteRequest(BaseModel):
    """Request to invite someone to an org."""

    email: str = Field(..., min_length=3, max_length=255)
    role: OrgRole = OrgRole.MEMBER

    @field_validator("email")
    @classmethod
    def valid_email(cls, v: str) -> str:
        v = v.strip().lower()
        if not re.match(r"[^@]+@[^@]+\.[^@]+", v):
            raise ValueError("invalid email address")
        return v


class InviteResponse(BaseModel):
    """Response after creating an invite."""

    id: int
    org_id: int
    email: str
    role: OrgRole
    token: str
    invite_url: str
    created_at: datetime


# ---------------------------------------------------------------------------
# Publish / unpublish
# ---------------------------------------------------------------------------


class PublishDocRequest(BaseModel):
    """Publish a document to an org's shared library."""

    org_id: int
