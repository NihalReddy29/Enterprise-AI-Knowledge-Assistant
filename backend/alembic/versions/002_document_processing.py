"""Add document processing fields and extracted status.

Revision ID: 002_document_processing
Revises: 001_initial_schema
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_document_processing"
down_revision: Union[str, None] = "001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"
    if is_postgres:
        op.execute("ALTER TYPE document_status ADD VALUE IF NOT EXISTS 'extracted'")

    op.add_column("documents", sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("documents", sa.Column("page_count", sa.Integer(), nullable=True))
    op.add_column("documents", sa.Column("extracted_text_path", sa.String(length=1024), nullable=True))
    op.add_column("documents", sa.Column("error_message", sa.Text(), nullable=True))
    op.add_column(
        "documents",
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    if is_postgres:
        op.alter_column("documents", "file_size", server_default=None)


def downgrade() -> None:
    op.drop_column("documents", "updated_at")
    op.drop_column("documents", "error_message")
    op.drop_column("documents", "extracted_text_path")
    op.drop_column("documents", "page_count")
    op.drop_column("documents", "file_size")

