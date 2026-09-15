"""Add team join codes and join requests.

Revision ID: 008_team_join_codes
Revises: 007_teams
Create Date: 2026-09-10
"""

import secrets
import string
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy import inspect
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM

revision: str = "008_team_join_codes"
down_revision: Union[str, None] = "007_teams"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_JOIN_ALPHABET = "".join(
    ch for ch in (string.ascii_uppercase + string.digits) if ch not in "O0I1L"
)


def _table_exists(name: str) -> bool:
    return inspect(op.get_bind()).has_table(name)


def _column_exists(table: str, column: str) -> bool:
    return column in {c["name"] for c in inspect(op.get_bind()).get_columns(table)}


def _random_code() -> str:
    raw = "".join(secrets.choice(_JOIN_ALPHABET) for _ in range(8))
    return f"{raw[:4]}-{raw[4:]}"


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    join_request_status_values = ["pending", "approved", "rejected"]

    if is_postgres:
        op.execute(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'team_join_request_status') THEN
                    CREATE TYPE team_join_request_status AS ENUM ('pending', 'approved', 'rejected');
                END IF;
            END$$;
            """
        )
        join_request_status_enum = PG_ENUM(
            *join_request_status_values, name="team_join_request_status", create_type=False
        )
    else:
        join_request_status_enum = sa.Enum(
            *join_request_status_values, name="team_join_request_status"
        )

    if not _column_exists("teams", "join_code"):
        op.add_column("teams", sa.Column("join_code", sa.String(length=12), nullable=True))

        teams = bind.execute(sa.text("SELECT id FROM teams")).fetchall()
        used: set[str] = set()
        for (team_id,) in teams:
            while True:
                code = _random_code()
                if code not in used:
                    used.add(code)
                    break
            bind.execute(
                sa.text("UPDATE teams SET join_code = :code WHERE id = :id"),
                {"code": code, "id": team_id},
            )

        with op.batch_alter_table("teams") as batch_op:
            batch_op.alter_column("join_code", nullable=False)
            batch_op.create_index("ix_teams_join_code", ["join_code"], unique=True)

    if not _table_exists("team_join_requests"):
        op.create_table(
            "team_join_requests",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("team_id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("status", join_request_status_enum, nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("reviewed_by", sa.Integer(), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("CURRENT_TIMESTAMP"),
                nullable=False,
            ),
            sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
            sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["team_id"], ["teams.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("team_id", "user_id", name="uq_team_join_requests_team_user"),
        )
        op.create_index("ix_team_join_requests_id", "team_join_requests", ["id"])
        op.create_index("ix_team_join_requests_team_id", "team_join_requests", ["team_id"])
        op.create_index("ix_team_join_requests_user_id", "team_join_requests", ["user_id"])


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if _table_exists("team_join_requests"):
        op.drop_table("team_join_requests")

    if _column_exists("teams", "join_code"):
        with op.batch_alter_table("teams") as batch_op:
            batch_op.drop_index("ix_teams_join_code")
            batch_op.drop_column("join_code")

    if is_postgres:
        op.execute("DROP TYPE IF EXISTS team_join_request_status")
