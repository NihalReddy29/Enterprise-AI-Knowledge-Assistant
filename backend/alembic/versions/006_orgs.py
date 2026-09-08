"""Add organizations, org_members, org_invites tables and documents.org_id.

Revision ID: 006_orgs
Revises: 005_query_logs
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision: str = "006_orgs"
down_revision: Union[str, None] = "005_query_logs"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # --- Create org_role enum if it does not exist ---
    if is_postgres:
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'org_role') THEN
                    CREATE TYPE org_role AS ENUM ('owner', 'admin', 'member');
                END IF;
            END$$;
            """
        )
        org_role_enum = PG_ENUM("owner", "admin", "member", name="org_role", create_type=False)
    else:
        org_role_enum = sa.Enum("owner", "admin", "member", name="org_role")

    # --- organizations ---
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_organizations_id", "organizations", ["id"], unique=False)
    op.create_index("ix_organizations_slug", "organizations", ["slug"], unique=True)

    # --- org_members ---
    op.create_table(
        "org_members",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "role",
            org_role_enum,
            nullable=False,
        ),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_org_members_id", "org_members", ["id"], unique=False)
    op.create_index("ix_org_members_org_id", "org_members", ["org_id"], unique=False)
    op.create_index("ix_org_members_user_id", "org_members", ["user_id"], unique=False)

    # --- org_invites ---
    op.create_table(
        "org_invites",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("org_id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column(
            "role",
            org_role_enum,
            nullable=False,
        ),
        sa.Column("invited_by", sa.Integer(), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invited_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_org_invites_id", "org_invites", ["id"], unique=False)
    op.create_index("ix_org_invites_org_id", "org_invites", ["org_id"], unique=False)
    op.create_index("ix_org_invites_email", "org_invites", ["email"], unique=False)
    op.create_index("ix_org_invites_token", "org_invites", ["token"], unique=True)

    # --- Add org_id to documents ---
    if is_postgres:
        op.add_column(
            "documents",
            sa.Column("org_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_documents_org_id",
            "documents",
            "organizations",
            ["org_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_documents_org_id", "documents", ["org_id"], unique=False)
    else:
        with op.batch_alter_table("documents") as batch_op:
            batch_op.add_column(sa.Column("org_id", sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                "fk_documents_org_id",
                "organizations",
                ["org_id"],
                ["id"],
                ondelete="SET NULL",
            )
            batch_op.create_index("ix_documents_org_id", ["org_id"], unique=False)


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.drop_index("ix_documents_org_id", table_name="documents")
        op.drop_constraint("fk_documents_org_id", "documents", type_="foreignkey")
        op.drop_column("documents", "org_id")
    else:
        with op.batch_alter_table("documents") as batch_op:
            batch_op.drop_index("ix_documents_org_id")
            batch_op.drop_constraint("fk_documents_org_id", type_="foreignkey")
            batch_op.drop_column("org_id")

    op.drop_index("ix_org_invites_token", table_name="org_invites")
    op.drop_index("ix_org_invites_email", table_name="org_invites")
    op.drop_index("ix_org_invites_org_id", table_name="org_invites")
    op.drop_index("ix_org_invites_id", table_name="org_invites")
    op.drop_table("org_invites")

    op.drop_index("ix_org_members_user_id", table_name="org_members")
    op.drop_index("ix_org_members_org_id", table_name="org_members")
    op.drop_index("ix_org_members_id", table_name="org_members")
    op.drop_table("org_members")

    op.drop_index("ix_organizations_slug", table_name="organizations")
    op.drop_index("ix_organizations_id", table_name="organizations")
    op.drop_table("organizations")

    if is_postgres:
        op.execute("DROP TYPE IF EXISTS org_role")

