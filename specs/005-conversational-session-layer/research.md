# Research: Conversational session layer (005)

## 1. Durable store: MySQL (registry-aligned)

**Decision**: Use **MySQL** for **session/turn/snapshot** durability—the **same database engine** as the tool registry (typically **new tables in the existing registry database**, or a dedicated MySQL database if ops wants logical isolation without a second engine).

**Rationale**: Operators avoid running **PostgreSQL alongside MySQL**. **Redis + MySQL** preserves the dual-tier pattern (hot working set vs durable history). JSON columns and Alembic migrations match patterns already used for the registry.

**Alternatives considered**: **PostgreSQL for sessions only** — rejected to reduce operational surface area. **SQLite** for dev-only — acceptable for local tests but production follows MySQL + Redis.

---

## 2. Working set: Redis responsibilities

**Decision**: **Redis** holds the **hot working set**: latest merged view for fast reads, **per-session distributed lock** (or lock + queue metadata) for **FR-013 FIFO**, optional **rate-limit / in-flight** counters, and **degraded-mode** detection (connection errors trigger FR-012 path).

**Rationale**: Constitution §Performance targets **< 50ms** session retrieval; Redis matches low-latency working-set requirement (FR-003).

**Alternatives considered**: **MySQL-only** (no Redis) — simpler ops but weaker hot-path latency and harder FIFO without distributed locks. **In-process only** — fails multi-instance coordinator deployment.

---

## 3. Per-session FIFO under multiple workers

**Decision**: **Serialize** with a **Redis lock key** `session:{session_id}:turn_lock` using **SET NX PX** (or Redlock if multi-region — defer). Turn handler **acquires lock**, drains or processes **one** inbound message, **releases** in `finally`. Optional **LIST** `session:{id}:inbox` for enqueue when lock busy; worker **RPUSH** on receive, single consumer **BLPOP** while holding lock — order preserved.

**Rationale**: Meets **FR-013** without requiring a single-threaded process.

**Alternatives considered**: **DB row lock** on `sessions` — viable but adds latency on every turn; **Kafka** — out of scope for v1.

---

## 4. Intent classification implementation

**Decision**: **Structured LLM output** (e.g. Pydantic-parsed JSON) with fields: `intent` enum (`new_query` | `refinement` | `reformat` | `meta_question`), `confidence` float 0–1, optional `rationale` (debug, redacted in traces per observability policy). Thresholds in `conversation/config.py`: below threshold → **FR-015** clarification response (no engine run).

**Rationale**: Matches **SC-002** and **FR-004**/**FR-015**; borderline utterances need nuance that rules alone handle poorly.

**Alternatives considered**: **Rules/regex only** — cheaper but weak on natural phrasing. **Always full graph** — violates selective re-invocation and SC-003.

---

## 5. Continuation: `session_id` and `merge_graph_defaults`

**Decision**: Add a **continuation API** path on the engine entry (e.g. `invoke_research_graph_continuation` or a parameter `reuse_session_id=True`) that **does not** mint a new canonical `session_id` when loading an existing session; still validates UUID format for `trace_id` per run. Coordinator passes **merged** `constraints`, **`accumulated_context`**, prior **`messages`** / snapshot fields as required by route.

**Rationale**: Current `merge_graph_defaults` always generates a **new** `session_id` — incompatible with multi-turn **same** `session_id` observability and FR-001.

**Alternatives considered**: **Client supplies session_id** as only path — risks forgery; coordinator must **verify ownership** before trusting id (FR-014/**FR-016**).

---

## 6. FR-016 ambiguous denial

**Decision**: HTTP mapping uses **404** (or **403** with identical body shape as 404) for both **unknown id** and **wrong owner** on session fetch/mutation; **never** return 200 with empty body for wrong owner. Log server-side with real reason for operators (structured log field `denial_reason`), not exposed to client.

**Rationale**: Matches clarification **Option B** and **SC-005** tests.

**Alternatives considered**: **403 distinct** — easier debugging but leaks existence.

---

## 7. Degraded mode (FR-012)

**Decision**: If Redis unavailable: load **read-only** session view from **MySQL** if possible; **reject** turns that require lock + write path with **structured error** `degraded_mode: true` and user-visible message. If **MySQL** unavailable for required read/write: **503/500** with clear code, **no** partial apply.

**Rationale**: Implements clarified **Option B** + durable fail-closed.

---

## Resolved NEEDS CLARIFICATION

None remaining for Phase 1; optional **break-glass** role implementation deferred to security backlog (spec allows documented audited role).
