"""Initial schema with pgvector extension

Revision ID: 001_initial
Revises:
Create Date: 2026-03-26
"""

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "tools",
        sa.Column("tool_id", sa.String(100), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("version", sa.String(50), nullable=False),
        sa.Column("endpoint", sa.String(500), nullable=False),
        sa.Column("method", sa.String(10), server_default="POST"),
        sa.Column("input_schema", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("output_schema", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("health_check", sa.String(500), nullable=True),
        sa.Column("status", sa.String(20), server_default="active"),
        sa.Column("embedding", Vector(768), nullable=True),
        sa.Column("avg_latency_ms", sa.Float(), server_default="0"),
        sa.Column("cost_per_call", sa.Float(), server_default="0"),
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
    )
    op.create_index("ix_tools_status", "tools", ["status"])

    op.create_table(
        "tool_capabilities",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tool_id",
            sa.String(100),
            sa.ForeignKey("tools.tool_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("capability", sa.String(100), nullable=False),
    )
    op.create_index(
        "uq_tool_capability", "tool_capabilities", ["tool_id", "capability"], unique=True
    )
    op.create_index("ix_tool_capabilities_capability", "tool_capabilities", ["capability"])

    op.create_table(
        "tool_usage_logs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "tool_id",
            sa.String(100),
            sa.ForeignKey("tools.tool_id"),
            nullable=False,
        ),
        sa.Column("agent_id", sa.String(100), nullable=True),
        sa.Column("session_id", sa.String(100), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=False),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "invoked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_tool_usage_logs_tool_id", "tool_usage_logs", ["tool_id"])
    op.create_index("ix_tool_usage_logs_invoked_at", "tool_usage_logs", ["invoked_at"])


def downgrade() -> None:
    op.drop_table("tool_usage_logs")
    op.drop_table("tool_capabilities")
    op.drop_table("tools")
    op.execute("DROP EXTENSION IF EXISTS vector")
