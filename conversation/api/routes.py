from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from conversation.authz import SESSION_NOT_FOUND
from conversation.coordinator import (
    ConversationCoordinator,
    CoordinatorLockTimeoutError,
    IdempotencyConflictError,
    SessionAccessDenied,
    StorageDegradedError,
)
from conversation.models import IdempotencyMismatchBody, SessionDegradedErrorBody, TurnRequest

router = APIRouter()
_bearer = HTTPBearer(auto_error=False)


def _principal(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> str:
    if creds is None or not creds.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization required",
        )
    return creds.credentials.strip()


def _coordinator(request: Request) -> ConversationCoordinator:
    coord = getattr(request.app.state, "conversation_coordinator", None)
    if coord is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Conversation coordinator is not configured",
        )
    return coord


@router.post("/v1/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    owner: Annotated[str, Depends(_principal)],
    coord: Annotated[ConversationCoordinator, Depends(_coordinator)],
) -> dict:
    sid = await coord.create_session_row(owner)
    expires = datetime.now(timezone.utc) + timedelta(days=30)
    return {
        "session_id": sid,
        "status": "active",
        "expires_at": expires.isoformat().replace("+00:00", "Z"),
    }


@router.post("/v1/sessions/{session_id}/turns")
async def post_turn(
    session_id: str,
    body: TurnRequest,
    owner: Annotated[str, Depends(_principal)],
    coord: Annotated[ConversationCoordinator, Depends(_coordinator)],
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
):
    import uuid

    trace_id = str(uuid.uuid4())
    try:
        result = await coord.run_turn(
            owner_principal_id=owner,
            session_id=session_id,
            message=body.message.strip(),
            trace_id=trace_id,
            client_session_id=body.client_session_id,
            idempotency_key=idempotency_key.strip() if idempotency_key else None,
        )
    except SessionAccessDenied:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=SESSION_NOT_FOUND)
    except IdempotencyConflictError:
        return JSONResponse(
            status_code=status.HTTP_409_CONFLICT,
            content=IdempotencyMismatchBody().model_dump(),
        )
    except StorageDegradedError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=SessionDegradedErrorBody().model_dump(),
        )
    except CoordinatorLockTimeoutError:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=SessionDegradedErrorBody().model_dump(),
        )

    return result.model_dump()
