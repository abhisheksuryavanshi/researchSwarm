from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, String, Text, func
from sqlalchemy.dialects.mysql import JSON as MySQLJSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from registry.database import Base


class Tool(Base):
    """
    SQLAlchemy model representing a registered tool in the registry.
    Continuously stores metadata, configuration, performance metrics, and schema information.
    """
    __tablename__ = "tools"

    tool_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    endpoint: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="POST", server_default="POST")
    input_schema: Mapped[dict] = mapped_column(MySQLJSON, nullable=False)
    output_schema: Mapped[dict] = mapped_column(MySQLJSON, nullable=False)
    health_check: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="active", server_default="active"
    )
    avg_latency_ms: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    cost_per_call: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    capabilities: Mapped[list["ToolCapability"]] = relationship(
        back_populates="tool", cascade="all, delete-orphan", lazy="selectin"
    )

    __table_args__ = (
        Index("ix_tools_status", "status"),
    )


class ToolCapability(Base):
    """
    SQLAlchemy model representing a specific capability associated with a tool.
    Enables categorizing and discovering tools effectively by their capabilities.
    """
    __tablename__ = "tool_capabilities"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tool_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("tools.tool_id", ondelete="CASCADE"), nullable=False
    )
    capability: Mapped[str] = mapped_column(String(100), nullable=False)

    tool: Mapped["Tool"] = relationship(back_populates="capabilities")

    __table_args__ = (
        Index("uq_tool_capability", "tool_id", "capability", unique=True),
        Index("ix_tool_capabilities_capability", "capability"),
    )


class ToolUsageLog(Base):
    """
    SQLAlchemy model representing an execution log of a tool invocation.
    Meticulously tracks invocation metrics including latency and success/failure status.
    """
    __tablename__ = "tool_usage_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tool_id: Mapped[str] = mapped_column(
        String(100), ForeignKey("tools.tool_id"), nullable=False
    )
    agent_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    session_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, nullable=False)
    success: Mapped[bool] = mapped_column(nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    invoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    __table_args__ = (
        Index("ix_tool_usage_logs_tool_id", "tool_id"),
        Index("ix_tool_usage_logs_invoked_at", "invoked_at"),
    )
