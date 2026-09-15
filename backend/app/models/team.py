"""SQLAlchemy ORM models for multi-tenant teams."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database.base import Base

if TYPE_CHECKING:
    from app.models.user import Document, User


class TeamMemberRole(str, enum.Enum):
    """Role within a team."""

    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class TeamMemberStatus(str, enum.Enum):
    """Membership lifecycle status."""

    ACTIVE = "active"
    REMOVED = "removed"


class TeamInviteStatus(str, enum.Enum):
    """Team invitation status."""

    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    EXPIRED = "expired"
    REVOKED = "revoked"


class TeamJoinRequestStatus(str, enum.Enum):
    """Join request submitted via team code."""

    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class MessengerMessageType(str, enum.Enum):
    """Team messenger message type."""

    TEXT = "text"
    FILE = "file"


class Team(Base):
    """A team workspace with isolated knowledge base and chat."""

    __tablename__ = "teams"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    qdrant_collection_name: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    join_code: Mapped[str] = mapped_column(
        String(12), unique=True, index=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    owner: Mapped["User"] = relationship("User", back_populates="owned_teams")
    members: Mapped[list["TeamMember"]] = relationship(
        "TeamMember",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    invites: Mapped[list["TeamInvite"]] = relationship(
        "TeamInvite",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="team",
    )
    conversations: Mapped[list["TeamConversation"]] = relationship(
        "TeamConversation",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    messenger_messages: Mapped[list["TeamMessengerMessage"]] = relationship(
        "TeamMessengerMessage",
        back_populates="team",
        cascade="all, delete-orphan",
    )
    join_requests: Mapped[list["TeamJoinRequest"]] = relationship(
        "TeamJoinRequest",
        back_populates="team",
        cascade="all, delete-orphan",
    )


class TeamJoinRequest(Base):
    """User request to join a team via join code (requires admin approval)."""

    __tablename__ = "team_join_requests"
    __table_args__ = (
        UniqueConstraint("team_id", "user_id", name="uq_team_join_requests_team_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    status: Mapped[TeamJoinRequestStatus] = mapped_column(
        Enum(
            TeamJoinRequestStatus,
            name="team_join_request_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=TeamJoinRequestStatus.PENDING,
        nullable=False,
    )
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    team: Mapped["Team"] = relationship("Team", back_populates="join_requests")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])
    reviewer: Mapped["User | None"] = relationship("User", foreign_keys=[reviewed_by])


class TeamMember(Base):
    """Membership linking a user to a team."""

    __tablename__ = "team_members"
    __table_args__ = (UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    role: Mapped[TeamMemberRole] = mapped_column(
        Enum(
            TeamMemberRole,
            name="team_member_role",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=TeamMemberRole.MEMBER,
        nullable=False,
    )
    status: Mapped[TeamMemberStatus] = mapped_column(
        Enum(
            TeamMemberStatus,
            name="team_member_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=TeamMemberStatus.ACTIVE,
        nullable=False,
    )
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    team: Mapped["Team"] = relationship("Team", back_populates="members")
    user: Mapped["User"] = relationship("User", back_populates="team_memberships")


class TeamInvite(Base):
    """Pending email invite to a team."""

    __tablename__ = "team_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    invited_email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    invited_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    status: Mapped[TeamInviteStatus] = mapped_column(
        Enum(
            TeamInviteStatus,
            name="team_invite_status",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=TeamInviteStatus.PENDING,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    responded_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    team: Mapped["Team"] = relationship("Team", back_populates="invites")
    inviter: Mapped["User | None"] = relationship("User", foreign_keys=[invited_by])


class TeamConversation(Base):
    """Shared RAG chat conversation thread for a team."""

    __tablename__ = "team_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="New Conversation")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    team: Mapped["Team"] = relationship("Team", back_populates="conversations")
    messages: Mapped[list["TeamChatMessage"]] = relationship(
        "TeamChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="TeamChatMessage.created_at",
    )


class TeamChatMessage(Base):
    """RAG chat message scoped to a team conversation."""

    __tablename__ = "team_chat_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("team_conversations.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    team: Mapped["Team"] = relationship("Team")
    conversation: Mapped["TeamConversation"] = relationship(
        "TeamConversation", back_populates="messages"
    )
    author: Mapped["User | None"] = relationship("User", foreign_keys=[user_id])


class TeamMessengerMessage(Base):
    """Member-to-member real-time chat message within a team."""

    __tablename__ = "team_messenger_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    team_id: Mapped[int] = mapped_column(
        ForeignKey("teams.id", ondelete="CASCADE"), index=True, nullable=False
    )
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    message_type: Mapped[MessengerMessageType] = mapped_column(
        Enum(
            MessengerMessageType,
            name="messenger_message_type",
            values_callable=lambda x: [e.value for e in x],
        ),
        default=MessengerMessageType.TEXT,
        nullable=False,
    )
    file_document_id: Mapped[int | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"), nullable=True, index=True
    )
    reply_to_id: Mapped[int | None] = mapped_column(
        ForeignKey("team_messenger_messages.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    edited_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deleted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    team: Mapped["Team"] = relationship("Team", back_populates="messenger_messages")
    sender: Mapped["User"] = relationship("User", foreign_keys=[sender_id])
    file_document: Mapped["Document | None"] = relationship(
        "Document", foreign_keys=[file_document_id]
    )
    reply_to: Mapped["TeamMessengerMessage | None"] = relationship(
        "TeamMessengerMessage", remote_side="TeamMessengerMessage.id", foreign_keys=[reply_to_id]
    )
    reads: Mapped[list["TeamMessengerRead"]] = relationship(
        "TeamMessengerRead",
        back_populates="message",
        cascade="all, delete-orphan",
    )


class TeamMessengerRead(Base):
    """Read receipt for a team messenger message."""

    __tablename__ = "team_messenger_reads"
    __table_args__ = (
        UniqueConstraint("message_id", "user_id", name="uq_team_messenger_reads_message_user"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    message_id: Mapped[int] = mapped_column(
        ForeignKey("team_messenger_messages.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    read_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    message: Mapped["TeamMessengerMessage"] = relationship(
        "TeamMessengerMessage", back_populates="reads"
    )
    user: Mapped["User"] = relationship("User")


class Notification(Base):
    """In-app notification for a user."""

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User", back_populates="notifications")
