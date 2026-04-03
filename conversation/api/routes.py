from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from agents.graph import GraphTimeoutError
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
    creds: Annotated[Optional[HTTPAuthorizationCredentials], Depends(_bearer)],
) -> str:
    if creds is None or not creds.credentials.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Bearer token required (use Authorization: Bearer <principal_id> for local dev)",
            headers={"WWW-Authenticate": "Bearer"},
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
    request: Request,
    session_id: str,
    body: TurnRequest,
    owner: Annotated[str, Depends(_principal)],
    coord: Annotated[ConversationCoordinator, Depends(_coordinator)],
    idempotency_key: Annotated[Optional[str], Header(alias="Idempotency-Key")] = None,
):
    trace_id = str(uuid.uuid4())
    accept = request.headers.get("accept", "")
    wants_stream = "text/event-stream" in accept

    if wants_stream:
        async def _sse_generator():
            try:
                async for chunk in coord.run_turn_streaming(
                    owner_principal_id=owner,
                    session_id=session_id,
                    message=body.message.strip(),
                    trace_id=trace_id,
                    client_session_id=body.client_session_id,
                    idempotency_key=idempotency_key.strip() if idempotency_key else None,
                ):
                    yield chunk
            except SessionAccessDenied:
                yield f"event: error\ndata: {json.dumps(SESSION_NOT_FOUND)}\n\n"
            except IdempotencyConflictError:
                yield f"event: error\ndata: {json.dumps(IdempotencyMismatchBody().model_dump())}\n\n"
            except (StorageDegradedError, CoordinatorLockTimeoutError):
                yield f"event: error\ndata: {json.dumps(SessionDegradedErrorBody().model_dump())}\n\n"
            except GraphTimeoutError as exc:
                yield f"event: error\ndata: {json.dumps({'detail': str(exc), 'trace_id': trace_id, 'code': 'graph_timeout'})}\n\n"
            except Exception as exc:
                yield f"event: error\ndata: {json.dumps({'detail': str(exc), 'code': 'internal_error'})}\n\n"

        return StreamingResponse(
            _sse_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

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
    except GraphTimeoutError as exc:
        return JSONResponse(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            content={
                "detail": str(exc),
                "trace_id": trace_id,
                "code": "graph_timeout",
            },
        )

    return result.model_dump()
