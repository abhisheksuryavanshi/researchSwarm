# Quickstart: Conversational session layer (local dev)

## Prerequisites

- Python 3.9+
- Docker (or podman) for **Redis** if not already local; **MySQL** (often same instance as the registry)
- Existing `researchSwarm` env: `uv sync` from repo root

## 1. Start dependencies

```bash
docker run -d --name rs-redis -p 6379:6379 redis:7-alpine
# MySQL: reuse the registry DB (e.g. researchswarm on :3306) or start a dedicated instance:
# docker run -d --name rs-mysql -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=researchswarm -p 3306:3306 mysql:8
```

## 2. Environment variables

```bash
export CONVERSATION_REDIS_URL="redis://localhost:6379/0"
# Align with registry MySQL (same URL pattern as REGISTRY_DATABASE_URL / settings.database_url):
export CONVERSATION_DATABASE_URL="mysql+aiomysql://root:root@localhost:3306/researchswarm"
# Optional until HTTP lands:
export CONVERSATION_LLM_MODEL="gemini-3.1-flash-live-preview"  # align with agents config
```

Add to your process manager or `.env` (do not commit secrets).

## 3. Migrations

After Alembic (or equivalent) for `conversation` tables is added:

```bash
# Example — exact command will match repo tooling
alembic upgrade head
```

## 4. Run tests

```bash
cd /path/to/researchSwarm
uv run pytest tests/unit/test_coordinator_routing.py tests/integration/test_conversation_multi_turn.py -q
```

(Paths activate once tasks from `/speckit.tasks` are implemented.)

## 5. Manual smoke (post-implementation)

1. `POST /v1/sessions` → obtain `session_id`.
2. `POST /v1/sessions/{id}/turns` with a research question → wait for assistant reply.
3. Second turn: refinement utterance → verify constraints and prior synthesis influence answer (logs + snapshot in MySQL).
4. Stop Redis → verify **degraded** read-only or **503** per FR-012 (no silent corruption).

## 6. Observability

- Langfuse + structlog must show **same** `session_id` across turns.
- Verify coordinator emits `agent_id=conversation_coordinator` (or chosen stable id).
