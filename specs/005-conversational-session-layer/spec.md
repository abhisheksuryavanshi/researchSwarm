# Feature Specification: Conversational session layer

**Feature Branch**: `005-conversational-session-layer`  
**Created**: 2026-04-01  
**Status**: Draft  
**Input**: User description: "Build the Conversational Session Layer — Conversation Coordinator agent, Redis + MySQL session store, user intent classification (new query / refinement / reformat / meta-question), selective agent re-invocation routing, accumulated research state across turns, and constraint propagation into the engine's state schema."

## Clarifications

### Session 2026-04-01

- Q: When the low-latency session tier is unavailable but durable tier is available (or other partial storage failure), what user-facing behavior is required? → A: **Durable-fallback (degraded)** — read-only session view from durable when possible; block or defer turns that require healthy hot/working-set state, with user-visible notice; no silent inconsistent context. (User selected **Option B**; durable-unavailable case aligned to fail-closed with visible error when durable reads/writes are required.)
- Q: How should concurrent user messages in flight for the same session be handled? → A: **Strict per-session FIFO queue** — serialize processing in receive order; no interleaved mutations to accumulated state. (User selected **Option A**.)
- Q: Who may access a given session (same session id)? → A: **Single owner** — one authenticated principal for routine use; optional documented platform **break-glass** roles. (User selected **Option A**.)
- Q: When intent classification is low-confidence or ambiguous, what should happen before routing? → A: **Clarify with the user** — short clarifying question or disambiguation choices before committing to a route. (User selected **Option A**.)
- Q: What denial behavior should non-owners see for a valid session id vs unknown id? → A: **Ambiguous denial** — **same** outcome for wrong-owner and non-existent id (no existence leak). (User selected **Option B**.)

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Durable multi-turn research dialogue (Priority: P1)

A researcher asks an initial question, receives a structured research outcome, then continues in the same conversation. On each turn, the system recalls prior topic, findings, and constraints so answers build on earlier work instead of restarting from zero.

**Why this priority**: Without durable, cumulative context, multi-turn research feels broken and wastes user time. This is the foundation for every other session behavior.

**Independent Test**: Complete one research turn, send a follow-up that only makes sense with prior context (e.g. "narrow that to the last five years"), and verify the response reflects both the original topic and the narrowing constraint without requiring the user to restate the full question.

**Acceptance Scenarios**:

1. **Given** a user has completed at least one research turn in a session, **When** they send a follow-up message, **Then** the system uses accumulated session context (topic, prior conclusions, and stated constraints) as input to the next processing step.
2. **Given** a user returns after a short idle period within the same session, **When** they continue the conversation, **Then** prior turns and research state are still available up to the documented retention window.
3. **Given** a session identifier is established for a conversation, **When** the user sends messages under that session, **Then** all turns are ordered and attributable to the same session for replay or audit.

---

### User Story 2 — Intent-aware routing (Priority: P2)

The user’s message is classified into one of: new research question, refinement of prior work, reformat or repackage of existing results (e.g. shorter summary, different outline), or meta-question about the session or process. The system routes each type to the appropriate depth of work—full research only when needed, lighter paths when prior material suffices.

**Why this priority**: Correct routing saves latency and cost and avoids redundant research when the user only wants a tweak or a different presentation.

**Independent Test**: For each intent category, submit representative utterances after a seeded session state and verify observable behavior matches the expected route (e.g. refinement updates or extends prior conclusions without discarding them; reformat reuses prior substance without a full fresh investigation unless the user explicitly widens scope).

**Acceptance Scenarios**:

1. **Given** an active session with prior research output, **When** the user asks a clearly new, unrelated topic, **Then** the system treats it as a new research question and does not silently merge it with unrelated prior conclusions.
2. **Given** an active session with prior research output, **When** the user refines scope, depth, or focus, **Then** the system preserves relevant prior findings and applies the refinement without restarting unrelated parts of the investigation unless necessary.
3. **Given** an active session with prior research output, **When** the user asks only to reformat or shorten existing material, **Then** the system reuses substantive prior results and does not trigger a full new investigation unless required to satisfy the request.
4. **Given** an active session, **When** the user asks a meta-question (e.g. what was assumed, what sources mattered, how to phrase the next question), **Then** the system answers from session-visible context and process metadata without inventing research that was not performed.
5. **Given** a user message whose intent is **ambiguous** or **low-confidence** per documented thresholds, **When** the system handles the turn, **Then** it responds with a **brief clarifying question** or **disambiguation choices** before executing a routed research or reformat workflow (and does **not** silently pick a high-cost or misleading path).

---

### User Story 3 — Constraints carry forward (Priority: P2)

The user states limits (time range, geography, source preferences, tone, length, excluded topics). Those constraints persist as part of the session’s working context and apply to subsequent turns unless explicitly overridden or replaced.

**Why this priority**: Inconsistent application of constraints erodes trust and forces users to repeat themselves.

**Independent Test**: State a constraint in turn one; in turn two ask a follow-up that does not repeat the constraint; verify the outcome still honors it. Override with a new constraint in turn three and verify the new rule applies while prior incompatible rules are resolved per documented precedence.

**Acceptance Scenarios**:

1. **Given** a user has stated explicit constraints, **When** they send further messages in the same session, **Then** outputs respect those constraints unless the user clearly revokes or replaces them.
2. **Given** conflicting constraints across turns, **When** the system resolves them, **Then** the behavior follows documented precedence (e.g. later explicit override wins) and the user-visible result reflects the effective constraint set.

---

### User Story 4 — Selective re-invocation of research capabilities (Priority: P3)

When only part of the workflow needs to run again (e.g. reformat, small refinement), the system invokes deeper research components only when classification and session state indicate they are needed—not on every message.

**Why this priority**: Efficiency and predictable latency; subordinate to correct classification and state retention.

**Independent Test**: Instrument or observe (via acceptance tests or product-visible signals documented for QA) that a reformat-only request does not trigger the same full pipeline as an initial open-ended research question, while a genuine new query does.

**Acceptance Scenarios**:

1. **Given** a message classified as reformat-only, **When** the session is processed, **Then** the system does not discard accumulated research state and does not perform a full new investigation by default.
2. **Given** a message classified as requiring fresh investigation, **When** the session is processed, **Then** the system runs the research path to the depth needed and merges or replaces prior conclusions according to documented rules for new versus overlapping topics.

---

### Edge Cases

- Session identifier missing or unknown: system rejects or starts a new session per documented API behavior; user sees a clear, safe outcome.
- Session expired or purged: user receives a clear message; sensitive details from old sessions are not leaked into a new session.
- Extremely long conversations: system retains or summarizes per documented limits without silent truncation that drops active constraints without notice.
- **Concurrent messages for the same session**: The system MUST **serialize** handling **per session** in **FIFO (receive) order**—at most one mutating turn executes against accumulated state at a time; additional requests wait in a **per-session queue** (or equivalent) so outcomes match a single clear ordering. **Idempotency** for retries (e.g. client-supplied idempotency key) MUST be documented so duplicate delivery does not double-apply state changes.
- **Storage partial failure**: If the **working-set (low-latency) tier** is unavailable, the system MUST enter **degraded mode**: reconstruct and expose session context **read-only** from the **durable** tier when possible; **block or clearly defer**, with a **user-visible notice**, any turn that requires a healthy working-set tier until recovery; it MUST NOT silently fabricate or return inconsistent context. If the **durable** tier is unavailable when a durable read or write is required, the system MUST **fail closed** with a **user-visible error** (no silent pretense that history is safe or complete).
- **Ambiguous or low-confidence intent**: The system MUST **clarify** (question or choices) before routing; it MUST NOT silently default to full research or reformat when below documented confidence. (Aligns with **FR-004** / **FR-015**.)
- Malformed or ambiguous **content** (not only intent): system asks a brief clarification or applies a conservative default that is visible to the user, not a silent wrong route.
- **Cross-principal session access**: If the caller is **not** the session owner (and not an explicitly authorized **break-glass** role), the system MUST **deny** access with **ambiguous denial** per **FR-016**—the **same** user-visible and API-level outcome as for a **non-existent** session id, so callers cannot infer whether the id exists; session contents MUST NOT be exposed.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST maintain a **session** abstraction that ties together ordered user and assistant turns, identifiers, and accumulated research context for that conversation.
- **FR-002**: The system MUST persist session data so that an authorized client can resume work within the documented retention period after normal process restarts.
- **FR-003**: The system MUST provide low-latency read/write access to the **active working set** of a session during live conversation (sufficient for interactive use under normal load).
- **FR-004**: The system MUST classify each inbound user message into at least these categories: **new research question**, **refinement**, **reformat**, and **meta-question**, and MUST document **borderline** handling, **confidence thresholds**, and tie-in to **FR-015**.
- **FR-005**: The system MUST route processing based on classification and current session state so that full research runs occur only when required by the classified intent and scope.
- **FR-006**: The system MUST accumulate research state across turns (e.g. topic focus, intermediate conclusions, cited material references as applicable) in a form that downstream steps can consume.
- **FR-007**: The system MUST propagate user-stated **constraints** into the engine’s running context for the session and MUST apply them to subsequent turns until overridden or cleared according to documented rules.
- **FR-008**: The system MUST expose or encode effective constraints in a way that validation tests (or documented QA signals) can confirm they influenced outputs on follow-up turns.
- **FR-009**: The system MUST include a **conversation coordination** responsibility that decides routing and merging of state across turns without requiring the end user to manually select internal pipelines.
- **FR-010**: The system MUST define precedence for conflicting constraints and for merging new research with prior conclusions when topics overlap.
- **FR-011**: The system MUST correlate session activity with observability identifiers where the platform already defines them (e.g. canonical session id for tracing), without breaking session semantics.
- **FR-012**: The system MUST implement **degraded mode** when the working-set tier is unavailable: **read-only** reconstruction from the durable tier when possible; **block or defer** (with user-visible notice) mutating steps and full research turns that depend on a healthy working-set tier; MUST NOT silently invent or misrepresent context. When the durable tier is unavailable and durable-backed reads or writes are required, the system MUST **fail closed** with a user-visible error.
- **FR-013**: For a given **session**, the system MUST process inbound turns **one at a time** in **FIFO (receive) order**, preventing interleaved updates to accumulated session or research state. The API or product docs MUST define **retry/idempotency** behavior so duplicate submissions do not corrupt ordering or state.
- **FR-014**: Each **session** MUST have exactly **one owning authenticated principal** for routine read/write use. The system MUST **deny** session operations to non-owners except for **documented break-glass or platform-support** roles that are **audited** and **least-privilege**. Multi-user collaborative sessions are **out of scope** for this feature unless superseded by a later spec.
- **FR-015**: When classification is **ambiguous** or below documented **confidence**, the system MUST **not** execute a routed workflow silently; it MUST ask a **brief clarifying question** or present **disambiguation choices** first, then proceed only after the user’s follow-up (or documented timeout / cancellation behavior).
- **FR-016**: For session access attempts by a **non-owner** (excluding documented **break-glass**), the system MUST return the **same** externally observable denial as for an **unknown** session identifier on that API surface, so **session existence** is not leaked to unauthorized principals.

### Key Entities *(include if feature involves data)*

- **Session**: Logical conversation container; stable identifier; **single owning principal** (authenticated user or service identity) plus optional **tenant** scope; lifecycle (created, active, closed/expired).
- **Turn**: One inbound user message plus the system’s processing outcome for that step; ordering; optional link to classification outcome.
- **Accumulated research state**: Structured summary of what has been established in the session (findings, open questions, scope); distinct from raw chat text where the product stores both.
- **Constraint set**: Active limits and preferences with source (which turn introduced them), effective window, and resolution rules when they conflict.
- **Intent classification result**: Category label; **confidence** (or equivalent) used with **FR-015**; optional rationale for debugging; used for routing and logging as appropriate to privacy policy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In moderated usability or QA scenarios, at least **90%** of scripted multi-turn flows correctly preserve topic and constraints across turns without the user repeating prior constraints (sample size agreed with product, minimum 20 scenarios covering refinement and reformat).
- **SC-002**: For a labeled evaluation set of user utterances (minimum 50 per category across new / refinement / reformat / meta), **intent classification accuracy** meets or exceeds **85%** against gold labels, with errors skewing toward clarification prompts rather than silent wrong routing.
- **SC-003**: **P95 latency** for classified **reformat** requests (no new external research) is at least **40% lower** than **P95 latency** for classified **new research question** requests under comparable load in a controlled performance test, measured over a one-week window or equivalent benchmark runs.
- **SC-004**: After controlled chaos tests (process restart mid-session), **100%** of resumed sessions within the retention window reload prior turn count and constraint set consistent with pre-restart acceptance fixtures (no silent loss without user-visible notice).
- **SC-005**: Session-scoped data is only retrievable by authorized principals; unauthorized access attempts have **zero** successful retrievals in security test suites, and **non-owner** denials are **indistinguishable** from **unknown id** denials per **FR-016** in those tests.

## Assumptions

- A **dual persistence pattern** is mandated for this initiative: a low-latency tier for the active session working set and a **MySQL-backed** durable tier for authoritative session history and recovery (the same database technology as the tool registry), without requiring a second database engine or separate PostgreSQL deployment for sessions.
- **Authentication and authorization** for sessions reuse the platform’s existing identity model; this spec does not introduce a new identity provider.
- **Session access** is **single-owner** for routine use; shared or team-visible sessions are **not** in scope here.
- **Enumeration resistance**: Wrong-owner and unknown-session responses are **indistinguishable** to callers without privilege (**FR-016**), except where **break-glass** behavior is explicitly documented and audited.
- **Retention windows** and maximum conversation length follow product defaults (e.g. 30–90 days for durable history unless compliance dictates otherwise), with explicit user-visible behavior when limits are reached.
- The **research engine** already exposes or will expose a **state schema** that can carry constraints and accumulated context; this feature integrates with that contract rather than redefining the core research algorithms.
- **Canonical session identification** aligns with existing observability and API conventions (server-issued session id, optional client hints as auxiliary metadata only), consistent with prior platform specs.
