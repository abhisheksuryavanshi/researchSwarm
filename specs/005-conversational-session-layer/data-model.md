# Data model: Conversational session layer

Derived from [spec.md](./spec.md) key entities and FR-001–FR-016.

## MySQL (durable)

Session tables live in the **same MySQL deployment as the tool registry** (same database with new tables, or a dedicated MySQL database per ops policy—one engine only).

### `session`

| Column | Type | Notes |
|--------|------|--------|
| `id` | `CHAR(36)` or `BINARY(16)`, PK | Server-generated session id (same value as canonical `session_id` in traces) |
| `owner_principal_id` | `VARCHAR(767)` | Owning identity from auth (bounded for MySQL: `TEXT` cannot be indexed without a prefix length) |
| `tenant_id` | `VARCHAR(255)`, nullable | Optional multi-tenant scope |
| `status` | `ENUM` or `VARCHAR(32)` | `active`, `closed`, `expired` |
| `created_at` | `DATETIME(6)` | UTC |
| `updated_at` | `DATETIME(6)` | UTC |
| `expires_at` | `DATETIME(6)`, nullable | Retention / TTL |

**Constraints**: Index on `(owner_principal_id, created_at DESC)` for listing; unique `id`.

### `session_turn`

| Column | Type | Notes |
|--------|------|--------|
| `id` | `BIGINT`, PK, auto-increment | |
| `session_id` | `CHAR(36)` (FK → `session.id`) | |
| `turn_index` | `INT` | Monotonic per session (0-based or 1-based — pick one in migration) |
| `role` | `ENUM` or `VARCHAR(32)` | `user`, `assistant`, `system` (if needed) |
| `content` | `JSON` | User message or assistant final reply (shape TBD) |
| `intent` | `VARCHAR(64)`, nullable | `new_query`, `refinement`, `reformat`, `meta_question`, `clarification` |
| `intent_confidence` | `FLOAT`, nullable | |
| `trace_id` | `CHAR(36)`, nullable | Per-turn trace correlation |
| `idempotency_key` | `VARCHAR(255)`, nullable | UNIQUE per `(session_id, idempotency_key)` when present (partial unique index or app-enforced uniqueness per MySQL version) |
| `created_at` | `DATETIME(6)` | UTC |

**Constraints**: UNIQUE `(session_id, turn_index)`; UNIQUE `(session_id, idempotency_key)` for non-null idempotency keys (partial/functional index on MySQL 8+ or equivalent pattern).

### `research_snapshot`

| Column | Type | Notes |
|--------|------|--------|
| `id` | `BIGINT`, PK, auto-increment | |
| `session_id` | `CHAR(36)`, FK | |
| `after_turn_index` | `INT` | Snapshot applies after this turn completes |
| `state_blob` | `JSON` | Serializable subset of `ResearchState` (query, constraints, accumulated_context, synthesis, sources refs, etc.) |
| `created_at` | `DATETIME(6)` | UTC |

**Rules**: Append-only; coordinator loads **latest** snapshot for continuation unless a specific version is needed for audit.

---

## Redis (working set)

Keys (example conventions — final in implementation):

| Key | Purpose |
|-----|---------|
| `session:{uuid}:doc` | JSON hash of working fields (cached snapshot id, last turn_index, flags) |
| `session:{uuid}:turn_lock` | Lock token for FIFO processing |
| `session:{uuid}:inbox` | Optional LIST of pending inbound payloads (FIFO) |

**TTL**: Align `session:{uuid}:*` TTL with product retention or idle timeout; must not delete while **MySQL** is source of truth for recovery — prefer **lazy** Redis repopulation from MySQL on miss.

---

## In-memory / API (non-persisted)

### Intent classification result

- `intent`: enum (four + optional `needs_clarification` internal)
- `confidence`: float
- `rationale`: optional string (debug)

### Route plan

- `mode`: `full_graph` | `light_reformat` | `light_meta` | `clarify_only` | `no_op_degraded`
- `engine_entry`: which function/subgraph to call
- `state_patch`: dict merged into engine input

---

## Engine alignment (`agents/state.py`)

Existing fields used by coordinator:

- `constraints: dict[str, Any]` — **FR-007**; merge policy: last explicit user override wins per key family (document per key in `merge.py`).
- `accumulated_context: list[str]` — append prior synthesis bullets / summaries each turn as per routing.
- `messages` — transcript for nodes that consume chat history.
- `session_id`, `trace_id`, `client_session_id` — observability and API contract.

**Validation**: Coordinator-built dict must pass `validate_graph_input` (or a stricter **continuation** validator) before `invoke_*`.

---

## State transitions

- **Session**: `active` → `closed` (user action or API) → `expired` (TTL job) or direct `active` → `expired`.
- **Turn**: immutable after write; corrections = new turn with `intent=refinement` or explicit “undo” out of scope.

---

## FR mapping

| FR | Data support |
|----|----------------|
| FR-013 | `turn_index` monotonic + Redis lock + idempotency UNIQUE |
| FR-014/FR-016 | `owner_principal_id` on session; authz check before any read/write |
| FR-012 | Degraded flags in API response; read path from MySQL when Redis down |
