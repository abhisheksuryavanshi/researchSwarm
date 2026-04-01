from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class SessionRecord(BaseModel):
    session_id: str
    owner_principal_id: str
    status: str
    created_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None


class TurnRequest(BaseModel):
    message: str = Field(min_length=1)
    client_session_id: Optional[str] = None


class TurnResult(BaseModel):
    turn_index: int
    assistant_message: str
    intent: str
    intent_confidence: float
    degraded_mode: bool = False
    trace_id: str
    route_mode: Optional[str] = None
    engine_entry: Optional[str] = None


class IntentResult(BaseModel):
    intent: Literal[
        "new_query",
        "refinement",
        "reformat",
        "meta_question",
        "needs_clarification",
    ]
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: Optional[str] = None
    constraints_suggested: dict[str, Any] = Field(default_factory=dict)


class SessionNotFoundErrorBody(BaseModel):
    error: Literal["session_not_found"] = "session_not_found"
    message: str = "The requested session could not be found."


class SessionDegradedErrorBody(BaseModel):
    error: Literal["session_degraded"] = "session_degraded"
    message: str = "Session storage is temporarily read-only. Try again shortly."
    degraded_mode: Literal[True] = True


class IdempotencyMismatchBody(BaseModel):
    error: Literal["idempotency_mismatch"] = "idempotency_mismatch"
    message: str = "Idempotency-Key reused with a different request body."
