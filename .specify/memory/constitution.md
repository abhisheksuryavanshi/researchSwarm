<!--
Sync Impact Report
===================
Version change: N/A → 1.0.0 (initial ratification)
Modified principles: N/A (initial creation)
Added sections:
  - Core Principles (7 principles)
  - Performance Standards & Budgets
  - Development Workflow
  - Governance
Removed sections: N/A
Templates requiring updates:
  - .specify/templates/plan-template.md ✅ no update needed (Constitution Check
    is a dynamic placeholder filled at plan-creation time)
  - .specify/templates/spec-template.md ✅ no update needed (generic template;
    constitution principles drive concrete specs, not the template itself)
  - .specify/templates/tasks-template.md ✅ no update needed (task phases and
    categories are filled at task-creation time; template already supports
    contract tests, integration tests, observability, and parallel tasks)
  - .specify/templates/checklist-template.md ✅ no update needed (generic)
  - .specify/templates/agent-file-template.md ✅ no update needed (generic)
  - README.md ✅ no update needed (already aligned with all 7 principles)
Follow-up TODOs: None
-->

# Research Swarm Constitution

## Core Principles

### I. Dynamic Tool Architecture

Tools MUST be discovered and bound at runtime via a registry service; agents
MUST NOT carry hardcoded tool lists. Every registered tool MUST include:

- A validated input/output schema (Pydantic models enforced at registration)
- A health-check endpoint (proxied through the registry)
- Usage tracking (invocation count, latency percentiles, error rate)

The registry is the single source of truth for tool availability. Agents query
it by capability tags and semantic similarity. If the registry is unreachable,
agents MUST fail explicitly — never fall back to stale or embedded tool
definitions.

### II. Layered Independence

The system is composed of two layers with a strict dependency direction:

1. **Research Engine** (agents + tool registry + observability) — the core.
2. **Conversational Layer** (coordinator + session store) — the interface.

The research engine MUST be fully functional without the conversational layer.
The conversational layer calls into the engine; the engine MUST never import,
reference, or depend on conversational-layer code. Each layer MUST be:

- Independently testable (its own test suite with no cross-layer fixtures)
- Independently deployable (its own container/service boundary)
- Independently versioned

### III. Agent Autonomy with Bounded Scope

Each agent MUST have a clearly defined role with explicit input/output
contracts (typed state schema fields). Agents MUST NOT leak responsibilities
across boundaries:

- **Researcher**: gathers raw information. MUST NOT analyze or synthesize.
- **Analyst**: structures and compares findings. MUST NOT gather new data.
- **Critic**: validates claims and identifies gaps. MUST NOT synthesize.
- **Synthesizer**: produces the final output. MUST NOT gather or critique.
- **Conversation Coordinator**: interprets user intent and routes to the
  engine. MUST NOT perform research, analysis, or synthesis.

An agent that needs a capability outside its scope MUST delegate to the
appropriate agent via the orchestration graph — never by inlining the logic.

### IV. Test-First with Contract Testing

Test-driven development is mandatory. The Red-Green-Refactor cycle MUST be
followed for all production code:

1. Write a failing test that defines the expected behavior.
2. Implement the minimum code to make the test pass.
3. Refactor while keeping tests green.

Contract testing requirements:

- Every agent MUST have contract tests validating its input/output state
  schema fields.
- Every tool registration and binding endpoint MUST have contract tests
  validating request/response schemas.
- Every tool adapter MUST have contract tests validating its declared
  input/output schema against actual behavior.

Integration testing requirements:

- Dynamic tool discovery flow (search → select → bind → invoke).
- Multi-agent collaboration (full graph execution with loop-back paths).
- Conversational multi-turn scenarios (follow-up, refinement, meta-queries).

### V. Observability as Infrastructure

Observability is not an afterthought — it is infrastructure that MUST be
present from the first line of agent code:

- **Tracing**: Every LLM call, tool invocation, and agent decision MUST be
  traced via Langfuse with correlation IDs. Conversational sessions MUST be
  traceable across turns via `session_id`.
- **Logging**: Structured JSON logging via `structlog` is non-negotiable.
  Every log entry MUST include `session_id`, `agent_id`, and `trace_id`.
- **No silent failures**: Every exception MUST be logged with full context
  before being re-raised or handled. Swallowed exceptions are forbidden.
- **Tool invocation logging**: Every dynamic tool call MUST log `agent_id`,
  `tool_id`, `session_id`, latency, and success/failure status.

### VI. Performance Under Budget

Hard latency and resource budgets MUST be enforced:

| Metric | Budget |
|---|---|
| End-to-end research query | < 60 seconds |
| Registry search (capability lookup) | < 100ms |
| Dynamic tool binding | < 200ms |
| Conversational follow-up (no re-research) | Faster than initial query |

Resource tracking requirements:

- Token usage MUST be tracked per-agent, per-session.
- Every LLM call MUST have a timeout policy and a retry policy with
  exponential backoff.
- Budget overruns MUST be logged as warnings, not silently tolerated.

### VII. Session Continuity & Research Accumulation

Conversational sessions MUST persist across turns:

- **Chat history**: Full message transcript (user + system) stored per
  `session_id`.
- **Research state snapshots**: The LangGraph state after each completed run
  (raw findings, analysis, critique, synthesis) MUST be snapshotted.
- **Accumulated sources**: All sources gathered across turns MUST be
  deduplicated and persisted.

Follow-up queries MUST build on prior findings — not restart from scratch.
The Conversation Coordinator MUST classify user intent (new query, refinement,
reformatting, meta-question) and invoke only the minimum set of agents needed.

The engine's state schema MUST support a `constraints` dict (source filters,
entity focus, depth parameters) and an `accumulated_context` field from day
one, even if unused in early phases. This ensures the conversational layer
can steer agent behavior without engine-side refactoring.

## Performance Standards & Budgets

All performance targets are defined in Principle VI. This section captures
additional operational standards:

- **Health checks**: Every registered tool MUST respond to health checks
  within 500ms. Tools failing health checks MUST be marked degraded in the
  registry and excluded from discovery results.
- **Graceful degradation**: If a dynamically discovered tool fails at
  invocation time, the agent MUST log the failure, report it to the registry
  (for stats), and attempt an alternative tool from the same capability
  category before failing the task.
- **Concurrency**: The tool registry MUST support concurrent search and bind
  requests without serialization bottlenecks.
- **Session storage**: Redis for live session state (chat history, active
  constraints). MySQL for durable persistence (research snapshots,
  accumulated sources). Read latency for session retrieval MUST be < 50ms.

## Development Workflow

### Branching & Commits

- Feature branches MUST follow the naming convention
  `<issue-number>-<short-description>`.
- Commits MUST be atomic — one logical change per commit.
- Commit messages MUST follow conventional commits format
  (`feat:`, `fix:`, `test:`, `docs:`, `refactor:`, `chore:`).

### Code Review Gates

Every pull request MUST satisfy before merge:

1. All existing tests pass.
2. New code has corresponding tests (contract + unit at minimum).
3. No decrease in test coverage for touched files.
4. Linter and formatter checks pass (`ruff`, `black`).
5. Constitution compliance verified (reviewer MUST check against principles).

### Definition of Done

A task is complete when:

1. Implementation matches the spec and passes acceptance scenarios.
2. Contract tests validate input/output schemas.
3. Observability is in place (traces, structured logs, no silent failures).
4. Documentation is updated if public interfaces changed.
5. The feature works in isolation (layered independence verified).

## Governance

This constitution is the supreme authority for architectural and process
decisions in Research Swarm. All code reviews, design documents, and
implementation plans MUST verify compliance with these principles.

### Amendment Procedure

1. Propose an amendment via a pull request modifying this file.
2. The amendment MUST include rationale and impact analysis.
3. All active contributors MUST be notified.
4. Amendments take effect upon merge.

### Versioning Policy

This constitution follows semantic versioning:

- **MAJOR**: Principle removed, redefined, or made backward-incompatible.
- **MINOR**: New principle added or existing principle materially expanded.
- **PATCH**: Clarifications, wording improvements, non-semantic changes.

### Compliance Review

- Every plan created via `/speckit.plan` MUST include a Constitution Check
  gate validating alignment with all 7 principles.
- Quarterly reviews SHOULD audit recent PRs for principle adherence.
- Complexity that violates a principle MUST be explicitly justified in the
  plan's Complexity Tracking table.

**Version**: 1.0.0 | **Ratified**: 2026-03-26 | **Last Amended**: 2026-03-26
