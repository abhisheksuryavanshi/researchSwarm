"""
MySQL session tables using the registry SQLAlchemy ``Base`` so Alembic and the
registry engine share one metadata (single MySQL database).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    BigInteger,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from registry.database import Base


class SessionRow(Base):
    """Durable session row (MySQL)."""

    __tablename__ = "session"
    __table_args__ = (Index("ix_session_owner_created", "owner_principal_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    owner_principal_id: Mapped[str] = mapped_column(Text, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, server_default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    turns: Mapped[list["SessionTurnRow"]] = relationship(back_populates="session")
    snapshots: Mapped[list["ResearchSnapshotRow"]] = relationship(back_populates="session")


class SessionTurnRow(Base):
    __tablename__ = "session_turn"
    __table_args__ = (
        UniqueConstraint("session_id", "turn_index", name="uq_session_turn_index"),
        UniqueConstraint("session_id", "idempotency_key", name="uq_session_turn_idempotency"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(32), nullable=False)
    content: Mapped[dict[str, Any] | list[Any] | str | float | bool | None] = mapped_column(
        MySQLJSON,
        nullable=False,
    )
    intent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    intent_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    trace_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped["SessionRow"] = relationship(back_populates="turns")


class ResearchSnapshotRow(Base):
    __tablename__ = "research_snapshot"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("session.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    after_turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    state_blob: Mapped[dict[str, Any]] = mapped_column(MySQLJSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    session: Mapped["SessionRow"] = relationship(back_populates="snapshots")
