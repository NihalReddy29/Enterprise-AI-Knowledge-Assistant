"""Add chunk_count for indexed documents.

Revision ID: 003_chunk_indexing
Revises: 002_document_processing
Create Date: 2026-07-28
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_chunk_indexing"
down_revision: Union[str, None] = "002_document_processing"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("chunk_count", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "chunk_count")
