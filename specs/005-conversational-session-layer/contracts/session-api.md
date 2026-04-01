# Contract: Session and turn API

HTTP surface is **optional** if the coordinator is only embedded; when exposed (e.g. FastAPI under `conversation/api/routes.py`), clients and contract tests MUST conform to the following.

## Conventions

- **Base path**: `/v1/sessions` (versioned).
- **Auth**: `Authorization: Bearer <token>`; owner derived from token **must** match `session.owner_principal_id` for all session-scoped operations.
- **Canonical ids**: `session_id` and `trace_id` are UUID strings.
- **FR-016**: Responses for **unknown** `session_id` and **wrong owner** MUST be **byte-identical** for status + body schema (recommend **404** with generic error body).

---

## `POST /v1/sessions`

Creates a new session for the authenticated principal.

**Response 201**

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "active",
  "expires_at": "2026-05-01T00:00:00Z"
}
```

---

## `POST /v1/sessions/{session_id}/turns`

Submits one user turn. **FR-013**: server serializes per `session_id`; concurrent requests may **block** or **202** with `turn_id` + poll (implementation choice — document one).

### Headers

| Header | Required | Description |
|--------|----------|-------------|
| `Idempotency-Key` | Optional | If repeated with same body, returns same result without double-applying state |

### Request body

```json
{
  "message": "Please narrow the last answer to 2020–2024.",
  "client_session_id": "optional-client-hint"
}
```

### Response 200 (success)

```json
{
  "turn_index": 3,
  "assistant_message": "...",
  "intent": "refinement",
  "intent_confidence": 0.91,
  "degraded_mode": false,
  "trace_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8"
}
```

### Response 200 (clarification — FR-015)

```json
{
  "turn_index": 3,
  "assistant_message": "Do you want a shorter summary or new sources on the same topic?",
  "intent": "needs_clarification",
  "intent_confidence": 0.42,
  "degraded_mode": false,
  "trace_id": "..."
}
```

### Response 409 (idempotency conflict)

Same `Idempotency-Key` but **different** request body hash → **409** with stable error code `idempotency_mismatch`.

### Response 404 (FR-016)

Unknown session or wrong owner:

```json
{
  "error": "session_not_found",
  "message": "The requested session could not be found."
}
```

### Response 503 (degraded — FR-012)

```json
{
  "error": "session_degraded",
  "message": "Session storage is temporarily read-only. Try again shortly.",
  "degraded_mode": true
}
```

---

## `GET /v1/sessions/{session_id}`

Read-only session metadata + recent transcript slice (exact shape TBD; must not leak other users’ data).

**404**: Same body as POST wrong-owner/unknown (**FR-016**).

---

## Observability (contract with Principle V)

- Every turn handler MUST emit structlog with `session_id`, `agent_id` (e.g. `conversation_coordinator`), `trace_id`.
- Langfuse trace root per turn linked to `trace_id` / `session_id`.

---

## Contract tests (required)

1. **FR-016**: Same response for random UUID vs other user’s valid UUID.
2. **Idempotency**: Duplicate `Idempotency-Key` + same body → single side effect (turn_index stable).
3. **FIFO**: Two rapid posts from same client preserve `turn_index` order matching send order (within clock skew tolerance).
