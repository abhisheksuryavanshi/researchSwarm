"""Conversation session tables (MySQL)

Revision ID: 002_conversation_sessions
Revises: 001_initial
Create Date: 2026-04-01
"""

import sqlalchemy as sa
from sqlalchemy.dialects.mysql import JSON as MySQLJSON

from alembic import op

revision = "002_conversation_sessions"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "session",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_principal_id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.String(255), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_session_owner_created", "session", ["owner_principal_id", "created_at"])

    op.create_table(
        "session_turn",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("turn_index", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(32), nullable=False),
        sa.Column("content", MySQLJSON(), nullable=False),
        sa.Column("intent", sa.String(64), nullable=True),
        sa.Column("intent_confidence", sa.Float(), nullable=True),
        sa.Column("trace_id", sa.String(36), nullable=True),
        sa.Column("idempotency_key", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("session_id", "turn_index", name="uq_session_turn_index"),
        sa.UniqueConstraint("session_id", "idempotency_key", name="uq_session_turn_idempotency"),
    )
    op.create_index("ix_session_turn_session_id", "session_turn", ["session_id"])

    op.create_table(
        "research_snapshot",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.String(36), nullable=False),
        sa.Column("after_turn_index", sa.Integer(), nullable=False),
        sa.Column("state_blob", MySQLJSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["session.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_research_snapshot_session_id", "research_snapshot", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_research_snapshot_session_id", table_name="research_snapshot")
    op.drop_table("research_snapshot")
    op.drop_index("ix_session_turn_session_id", table_name="session_turn")
    op.drop_table("session_turn")
    op.drop_index("ix_session_owner_created", table_name="session")
    op.drop_table("session")
