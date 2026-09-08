"""Add query_logs table for admin analytics.

Revision ID: 005_query_logs
Revises: 004_message_citations
Create Date: 2026-07-29
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_query_logs"
down_revision: Union[str, None] = "004_message_citations"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    op.create_table(
        "query_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("conversation_id", sa.Integer(), nullable=True),
        sa.Column("message_id", sa.Integer(), nullable=True),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("topic", sa.String(length=255), nullable=True),
        sa.Column("provider", sa.String(length=50), nullable=True),
        sa.Column("citation_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("insufficient_information", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_query_logs_id"), "query_logs", ["id"], unique=False)
    op.create_index(op.f("ix_query_logs_user_id"), "query_logs", ["user_id"], unique=False)
    op.create_index(op.f("ix_query_logs_conversation_id"), "query_logs", ["conversation_id"], unique=False)
    op.create_index(op.f("ix_query_logs_message_id"), "query_logs", ["message_id"], unique=False)
    op.create_index(op.f("ix_query_logs_topic"), "query_logs", ["topic"], unique=False)
    if is_postgres:
        op.alter_column("query_logs", "citation_count", server_default=None)
        op.alter_column("query_logs", "insufficient_information", server_default=None)


def downgrade() -> None:
    op.drop_index(op.f("ix_query_logs_topic"), table_name="query_logs")
    op.drop_index(op.f("ix_query_logs_message_id"), table_name="query_logs")
    op.drop_index(op.f("ix_query_logs_conversation_id"), table_name="query_logs")
    op.drop_index(op.f("ix_query_logs_user_id"), table_name="query_logs")
    op.drop_index(op.f("ix_query_logs_id"), table_name="query_logs")
    op.drop_table("query_logs")

