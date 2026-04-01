from __future__ import annotations

import hashlib
import json

from conversation.models import SessionNotFoundErrorBody

# FR-016: identical payload for unknown session vs wrong owner (no existence leak).
SESSION_NOT_FOUND = SessionNotFoundErrorBody().model_dump()


def body_fingerprint(message: str, client_session_id: str | None) -> str:
    payload = json.dumps(
        {"message": message, "client_session_id": client_session_id},
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()


def is_authorized_owner(row_owner: str, caller_owner: str) -> bool:
    return row_owner == caller_owner
