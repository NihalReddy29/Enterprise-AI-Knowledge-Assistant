"""Add teams, team membership, invites, chat, messenger, and documents.team_id.

Revision ID: 007_teams
Revises: 006_orgs
Create Date: 2026-09-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision: str = "007_teams"
down_revision: Union[str, None] = "006_orgs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def _column_exists(table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _create_pg_enum(name: str, values: list[str]) -> None:
    values_sql = ", ".join(f"'{v}'" for v in values)
    op.execute(
        f"""
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = '{name}') THEN
                CREATE TYPE {name} AS ENUM ({values_sql});
            END IF;
        END$$;
        """
    )


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    team_member_role_values = ["owner", "admin", "member"]
    team_member_status_values = ["active", "removed"]
    team_invite_status_values = ["pending", "accepted", "rejected", "expired", "revoked"]
    messenger_message_type_values = ["text", "file"]

    if is_postgres:
        _create_pg_enum("team_member_role", team_member_role_values)
        _create_pg_enum("team_member_status", team_member_status_values)
        _create_pg_enum("team_invite_status", team_invite_status_values)
        _create_pg_enum("messenger_message_type", messenger_message_type_values)

        team_member_role_enum = PG_ENUM(
            *team_member_role_values, name="team_member_role", create_type=False
        )
        team_member_status_enum = PG_ENUM(
            *team_member_status_values, name="team_member_status", create_type=False
        )
        team_invite_status_enum = PG_ENUM(
            *team_invite_status_values, name="team_invite_status", create_type=False
        )
        messenger_message_type_enum = PG_ENUM(
            *messenger_message_type_values, name="messenger_message_type", create_type=False
        )
    else:
        team_member_role_enum = sa.Enum(*team_member_role_values, name="team_member_role")
        team_member_status_enum = sa.Enum(*team_member_status_values, name="team_member_status")
        team_invite_status_enum = sa.Enum(*team_invite_status_values, name="team_invite_status")
        messenger_message_type_enum = sa.Enum(
            *messenger_message_type_values, name="messenger_message_type"
        )

    # Repair path: create_all may have created team tables but not documents.team_id.
    if _table_exists("teams"):
        if not _column_exists("documents", "team_id"):
            if is_postgres:
                op.add_column("documents", sa.Column("team_id", sa.Integer(), nullable=True))
                op.create_foreign_key(
                    "fk_documents_team_id",
                    "documents",
                    "teams",
                    ["team_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
                op.create_index("ix_documents_team_id", "documents", ["team_id"], unique=False)
                op.create_check_constraint(
                    "ck_documents_team_org_exclusive",
                    "documents",
                    "(team_id IS NULL) OR (org_id IS NULL)",
                )
            else:
                with op.batch_alter_table("documents") as batch_op:
                    batch_op.add_column(sa.Column("team_id", sa.Integer(), nullable=True))
                    batch_op.create_foreign_key(
                        "fk_documents_team_id",
                        "teams",
                        ["team_id"],
                        ["id"],
                        ondelete="CASCADE",
                    )
                    batch_op.create_index("ix_documents_team_id", ["team_id"], unique=False)
                    batch_op.create_check_constraint(
                        "ck_documents_team_org_exclusive",
                        "(team_id IS NULL) OR (org_id IS NULL)",
                    )
        return

    # --- teams ---
    op.create_table(
        "teams",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("qdrant_collection_name", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("qdrant_collection_name"),
    )
    op.create_index("ix_teams_id", "teams", ["id"], unique=False)
    op.create_index("ix_teams_owner_id", "teams", ["owner_id"], unique=False)
    op.create_index(
        "ix_teams_qdrant_collection_name", "teams", ["qdrant_collection_name"], unique=True
    )

    # --- team_members ---
    op.create_table(
        "team_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("role", team_member_role_enum, nullable=False),
        sa.Column("status", team_member_status_enum, nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("team_id", "user_id", name="uq_team_members_team_user"),
    )
    op.create_index("ix_team_members_id", "team_members", ["id"], unique=False)
    op.create_index("ix_team_members_team_id", "team_members", ["team_id"], unique=False)
    op.create_index("ix_team_members_user_id", "team_members", ["user_id"], unique=False)

    # --- team_invites ---
    op.create_table(
        "team_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("invited_email", sa.String(255), nullable=False),
        sa.Column("invited_by", sa.Integer(), nullable=True),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("status", team_invite_status_enum, nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index("ix_team_invites_id", "team_invites", ["id"], unique=False)
    op.create_index("ix_team_invites_team_id", "team_invites", ["team_id"], unique=False)
    op.create_index("ix_team_invites_invited_email", "team_invites", ["invited_email"], unique=False)
    op.create_index("ix_team_invites_token", "team_invites", ["token"], unique=True)

    # --- team_conversations ---
    op.create_table(
        "team_conversations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_conversations_id", "team_conversations", ["id"], unique=False)
    op.create_index("ix_team_conversations_team_id", "team_conversations", ["team_id"], unique=False)

    # --- team_chat_messages ---
    op.create_table(
        "team_chat_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("citations", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["team_conversations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_chat_messages_id", "team_chat_messages", ["id"], unique=False)
    op.create_index("ix_team_chat_messages_team_id", "team_chat_messages", ["team_id"], unique=False)
    op.create_index(
        "ix_team_chat_messages_conversation_id",
        "team_chat_messages",
        ["conversation_id"],
        unique=False,
    )
    op.create_index("ix_team_chat_messages_user_id", "team_chat_messages", ["user_id"], unique=False)

    # --- documents.team_id (must exist before messenger file_document_id FK) ---
    if not _column_exists("documents", "team_id"):
        if is_postgres:
            op.add_column("documents", sa.Column("team_id", sa.Integer(), nullable=True))
            op.create_foreign_key(
                "fk_documents_team_id",
                "documents",
                "teams",
                ["team_id"],
                ["id"],
                ondelete="CASCADE",
            )
            op.create_index("ix_documents_team_id", "documents", ["team_id"], unique=False)
            op.create_check_constraint(
                "ck_documents_team_org_exclusive",
                "documents",
                "(team_id IS NULL) OR (org_id IS NULL)",
            )
        else:
            with op.batch_alter_table("documents") as batch_op:
                batch_op.add_column(sa.Column("team_id", sa.Integer(), nullable=True))
                batch_op.create_foreign_key(
                    "fk_documents_team_id",
                    "teams",
                    ["team_id"],
                    ["id"],
                    ondelete="CASCADE",
                )
                batch_op.create_index("ix_documents_team_id", ["team_id"], unique=False)
                batch_op.create_check_constraint(
                    "ck_documents_team_org_exclusive",
                    "(team_id IS NULL) OR (org_id IS NULL)",
                )

    # --- team_messenger_messages ---
    op.create_table(
        "team_messenger_messages",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("team_id", sa.Integer(), nullable=False),
        sa.Column("sender_id", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("message_type", messenger_message_type_enum, nullable=False),
        sa.Column("file_document_id", sa.Integer(), nullable=True),
        sa.Column("reply_to_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("edited_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["sender_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["file_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(
            ["reply_to_id"], ["team_messenger_messages.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_team_messenger_messages_id", "team_messenger_messages", ["id"], unique=False
    )
    op.create_index(
        "ix_team_messenger_messages_team_id", "team_messenger_messages", ["team_id"], unique=False
    )
    op.create_index(
        "ix_team_messenger_messages_sender_id",
        "team_messenger_messages",
        ["sender_id"],
        unique=False,
    )
    op.create_index(
        "ix_team_messenger_messages_file_document_id",
        "team_messenger_messages",
        ["file_document_id"],
        unique=False,
    )
    op.create_index(
        "ix_team_messenger_messages_reply_to_id",
        "team_messenger_messages",
        ["reply_to_id"],
        unique=False,
    )

    # --- team_messenger_reads ---
    op.create_table(
        "team_messenger_reads",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "read_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["message_id"], ["team_messenger_messages.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id", "user_id", name="uq_team_messenger_reads_message_user"),
    )
    op.create_index("ix_team_messenger_reads_id", "team_messenger_reads", ["id"], unique=False)
    op.create_index(
        "ix_team_messenger_reads_message_id", "team_messenger_reads", ["message_id"], unique=False
    )
    op.create_index(
        "ix_team_messenger_reads_user_id", "team_messenger_reads", ["user_id"], unique=False
    )

    # --- notifications ---
    op.create_table(
        "notifications",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_notifications_id", "notifications", ["id"], unique=False)
    op.create_index("ix_notifications_user_id", "notifications", ["user_id"], unique=False)
    op.create_index("ix_notifications_type", "notifications", ["type"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.drop_index("ix_notifications_type", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_index("ix_notifications_id", table_name="notifications")
    op.drop_table("notifications")

    op.drop_index("ix_team_messenger_reads_user_id", table_name="team_messenger_reads")
    op.drop_index("ix_team_messenger_reads_message_id", table_name="team_messenger_reads")
    op.drop_index("ix_team_messenger_reads_id", table_name="team_messenger_reads")
    op.drop_table("team_messenger_reads")

    op.drop_index("ix_team_messenger_messages_reply_to_id", table_name="team_messenger_messages")
    op.drop_index(
        "ix_team_messenger_messages_file_document_id", table_name="team_messenger_messages"
    )
    op.drop_index("ix_team_messenger_messages_sender_id", table_name="team_messenger_messages")
    op.drop_index("ix_team_messenger_messages_team_id", table_name="team_messenger_messages")
    op.drop_index("ix_team_messenger_messages_id", table_name="team_messenger_messages")
    op.drop_table("team_messenger_messages")

    if is_postgres:
        op.drop_constraint("ck_documents_team_org_exclusive", "documents", type_="check")
        op.drop_index("ix_documents_team_id", table_name="documents")
        op.drop_constraint("fk_documents_team_id", "documents", type_="foreignkey")
        op.drop_column("documents", "team_id")
    else:
        with op.batch_alter_table("documents") as batch_op:
            batch_op.drop_constraint("ck_documents_team_org_exclusive", type_="check")
            batch_op.drop_index("ix_documents_team_id")
            batch_op.drop_constraint("fk_documents_team_id", type_="foreignkey")
            batch_op.drop_column("team_id")

    op.drop_index("ix_team_chat_messages_user_id", table_name="team_chat_messages")
    op.drop_index("ix_team_chat_messages_conversation_id", table_name="team_chat_messages")
    op.drop_index("ix_team_chat_messages_team_id", table_name="team_chat_messages")
    op.drop_index("ix_team_chat_messages_id", table_name="team_chat_messages")
    op.drop_table("team_chat_messages")

    op.drop_index("ix_team_conversations_team_id", table_name="team_conversations")
    op.drop_index("ix_team_conversations_id", table_name="team_conversations")
    op.drop_table("team_conversations")

    op.drop_index("ix_team_invites_token", table_name="team_invites")
    op.drop_index("ix_team_invites_invited_email", table_name="team_invites")
    op.drop_index("ix_team_invites_team_id", table_name="team_invites")
    op.drop_index("ix_team_invites_id", table_name="team_invites")
    op.drop_table("team_invites")

    op.drop_index("ix_team_members_user_id", table_name="team_members")
    op.drop_index("ix_team_members_team_id", table_name="team_members")
    op.drop_index("ix_team_members_id", table_name="team_members")
    op.drop_table("team_members")

    op.drop_index("ix_teams_qdrant_collection_name", table_name="teams")
    op.drop_index("ix_teams_owner_id", table_name="teams")
    op.drop_index("ix_teams_id", table_name="teams")
    op.drop_table("teams")

    if is_postgres:
        op.execute("DROP TYPE IF EXISTS messenger_message_type")
        op.execute("DROP TYPE IF EXISTS team_invite_status")
        op.execute("DROP TYPE IF EXISTS team_member_status")
        op.execute("DROP TYPE IF EXISTS team_member_role")
