# researchSwarm — Detailed Overview

A multi-agent research system where specialized AI agents collaborate to answer complex research questions. The core innovation is a **tool registry service** — agents don't carry a hardcoded tool list. Mid-execution, an agent realizes it needs a capability (e.g., "parse SEC filings"), queries the registry, discovers a matching tool, binds it dynamically, and uses it.

---

## Philosophy

- **Distributed agents, not linear workflows** — agents are autonomous collaborators, not chained steps
- **Just-in-time dynamic tooling** — tools are discovered and bound at runtime, not pre-configured
- **Microservices patterns applied to AI** — each concern is isolated, independently testable, independently deployable
- **Observability from day one** — every LLM call, tool invocation, and agent decision is traced and logged
- **Conversational, not transactional** — research is iterative; the system supports multi-turn sessions where users steer, narrow, and deepen research over a conversation

---

## Architecture

The system runs as a **single FastAPI process** (`uvicorn registry.app:app`) that exposes both the tool registry API (`/tools/*`) and the conversational session API (`/v1/sessions*`). The research engine is a self-contained LangGraph pipeline. The conversational layer sits on top, managing sessions, interpreting follow-ups, and selectively re-invoking agents — but the engine works standalone.

```
┌─────────────────────────────────────────────────────────────┐
│  Operator Web UI (React + Vite)                             │
│  Chat · Tool Catalog · Stats/Health                         │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTP / SSE
┌──────────────────────────▼──────────────────────────────────┐
│  Conversational Layer                                       │
│  ┌────────────────────────────────────────────────────────┐ │
│  │           Conversation Coordinator                     │ │
│  │  - Interprets follow-ups & refinement requests         │ │
│  │  - Maintains session memory (message history)          │ │
│  │  - Decides: re-run full pipeline / partial / reformat  │ │
│  │  - Scopes constraints for targeted re-investigation    │ │
│  └───────────────────────┬────────────────────────────────┘ │
│  ┌───────────────────────▼────────────────────────────────┐ │
│  │           Session Store (Redis + MySQL)                 │ │
│  │  - Chat history per session                            │ │
│  │  - Prior research state snapshots                      │ │
│  │  - User-defined constraints & preferences              │ │
│  └────────────────────────────────────────────────────────┘ │
└──────────────────────────┬──────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────┐
│  Research Engine (LangGraph StateGraph)                      │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────────┐  │
│  │Researcher│ │ Analyst  │ │ Critic  │ │  Synthesizer   │  │
│  └────┬─────┘ └────┬─────┘ └────┬────┘ └──────┬─────────┘  │
│       └─────────────┴──────┬─────┴──────────────┘           │
│                            │                                │
│                   ┌────────▼────────┐                       │
│                   │  Tool Registry  │                       │
│                   │  (FastAPI +     │                       │
│                   │    MySQL)       │                       │
│                   └────────┬────────┘                       │
│                            │                                │
│            ┌───────────────┼───────────────┐                │
│         ┌──▼──────┐   ┌───▼───────┐   ┌───▼──────┐        │
│         │DuckDuck │   │ Semantic  │   │Wikipedia │  ...    │
│         │Go Search│   │ Scholar   │   │ MediaWiki│        │
│         └─────────┘   └───────────┘   └──────────┘        │
└──────────────────────────┬──────────────────────────────────┘
                           │
                  ┌────────▼────────┐
                  │    Langfuse     │
                  │   (Tracing)    │
                  └────────────────┘
```

**Key design constraint:** The research engine is fully functional without the conversational layer. The conversational layer calls into the engine — the engine never depends on it. This keeps the pipeline shippable as a standalone tool and makes the conversational layer a pure extension.

---

## Tech Stack

| Layer                | Technology                                                                  |
|----------------------|-----------------------------------------------------------------------------|
| **Orchestration**    | LangGraph — agent state machine, conditional routing, parallel execution    |
| **LLM**             | Groq (Llama 3.1), Google Gemini, Ollama (local) via LangChain abstraction  |
| **Tool Registry**    | FastAPI + MySQL (tool metadata, capability tags, versioning)                |
| **Tracing**          | Langfuse (self-hosted via Docker Compose) for full trace visibility         |
| **Logging**          | Structlog with JSON formatting and correlation IDs per research session     |
| **Session Store**    | Redis (turn locks, working-set cache) + MySQL (sessions, turns, snapshots)  |
| **Frontend**         | React 18, Vite, Tailwind CSS 4, React Router, react-markdown               |
| **Testing**          | Pytest + pytest-asyncio                                                     |
| **Containerization** | Docker Compose (MySQL, Langfuse + Postgres) + standalone Redis container    |
| **Language**         | Python 3.9+                                                                 |

---

## Core Components

### Tool Registry

A FastAPI service that acts as a catalog for all available tools. Each tool is registered with metadata, capability tags, input/output schemas, health checks, and latency stats.

**Endpoints:**

| Method | Path                     | Purpose                                          |
|--------|--------------------------|--------------------------------------------------|
| POST   | `/tools/register`        | Register a new tool with metadata + schema       |
| PUT    | `/tools/{tool_id}`       | Update an existing tool                          |
| DELETE | `/tools/{tool_id}`       | Soft-delete (sets status to `deprecated`)        |
| GET    | `/tools/search`          | Search by capability tag or list all tools       |
| GET    | `/tools/{tool_id}/bind`  | Returns LangChain-compatible tool definition     |
| POST   | `/tools/usage-log`       | Log a tool invocation                            |
| GET    | `/tools/{tool_id}/health`| Proxied health check                             |
| GET    | `/tools/stats`           | Usage statistics per tool                        |

**Tool Schema:**
```json
{
  "tool_id": "sec-filing-parser-v1",
  "name": "SEC Filing Parser",
  "description": "Parses SEC EDGAR filings and extracts structured financial data",
  "capabilities": ["financial_data", "sec_filings", "document_parsing"],
  "input_schema": { "ticker": "string", "filing_type": "string" },
  "output_schema": { "sections": "list", "financials": "dict" },
  "endpoint": "http://tools-service:8001/sec-parser",
  "version": "1.0.0",
  "health_check": "/health",
  "avg_latency_ms": 2300,
  "cost_per_call": 0.0
}
```

**Seeded Tools (7):** DuckDuckGo web search, Semantic Scholar academic search, GitHub repository search, Wikipedia MediaWiki API, mathjs calculator, plus two inactive placeholder tools.

**Discovery Flow:**
1. Agent queries the registry — full catalog (`GET /tools/search`) or filtered by capability (`GET /tools/search?capability=financial_data`)
2. The LLM evaluates tool definitions and selects the best match(es) via structured output (`ToolSelectionResponse`)
3. Agent calls the registry for a LangChain-compatible bind definition (`GET /tools/{id}/bind`)
4. Agent constructs a dynamic Pydantic model from the JSON Schema and wraps it as a `StructuredTool`
5. Agent invokes the tool via HTTP and logs usage metrics

### Agent Layer (LangGraph)

The `agents/` package runs the research **StateGraph**: Researcher → Analyst → Critic, with conditional loop-back to the Researcher when the Critic fails the quality gate, then Synthesizer → end.

**Graph flow:**
```
Researcher → Analyst → Critic ─┬─→ Synthesizer (if satisfied)
                                └─→ Researcher  (if gaps found, up to max_iterations)
```

**Entry points:**
- `build_research_graph()` — compiles the full four-agent StateGraph
- `build_synthesizer_only_graph()` — light path for reformat/meta queries
- `invoke_research_graph()` — wraps `ainvoke` with `asyncio.wait_for` timeout and a single-flight guard (`GraphBusyError` if a run is already active)
- `invoke_research_graph_continuation()` — preserves canonical `session_id` for follow-up turns
- `default_graph_context()` — builds LLM client + `RegistryClient` + `ToolDiscoveryTool`

**LLM Factory (`create_default_llm`):** Supports three providers selected by `LLM_PROVIDER` env var:
- `groq` — ChatGroq (default, Llama 3.1 8B Instant)
- `google` — ChatGoogleGenerativeAI (Gemini)
- `ollama` — ChatOllama (local models)

### Agent Roles

| Agent           | Role                                              | Static Tools                | Dynamic Tools                                    |
|-----------------|---------------------------------------------------|-----------------------------|--------------------------------------------------|
| **Researcher**  | Gathers raw information from multiple sources     | Web search, URL scraper     | Discovered per-query (domain-specific parsers)   |
| **Analyst**     | Structures, compares, identifies patterns         | Calculator, data formatter  | Discovered per-domain (financial, code analysis) |
| **Critic**      | Fact-checks claims, identifies gaps               | Web search (verification)   | Source-specific validators                       |
| **Synthesizer** | Produces final structured research brief          | Report formatter, citations | None (consumes prior outputs)                    |

The Critic can loop the workflow back to the Researcher when it identifies information gaps, ensuring research completeness before synthesis. Max loop iterations are configurable (1–5, default 3).

### State Schema

The `ResearchState` TypedDict uses LangGraph annotated reducers:

| Field                | Type / Reducer              | Purpose                                        |
|----------------------|-----------------------------|-------------------------------------------------|
| `query`              | `str`                       | The research question                          |
| `constraints`        | `dict`                      | Source filters, entity focus, depth params      |
| `accumulated_context`| `list[str]` (append)        | Prior findings from earlier turns               |
| `messages`           | `list[AnyMessage]` (add)    | LangChain message history                      |
| `raw_findings`       | `list[dict]` (append)       | Raw tool output from Researcher                |
| `sources`            | `list[dict]` (dedupe by URL)| All gathered sources across turns              |
| `analysis`           | `str`                       | Analyst's structured analysis                  |
| `critique`           | `str`                       | Critic's assessment                            |
| `critique_pass`      | `bool`                      | Whether Critic approved                        |
| `gaps`               | `list[str]`                 | Information gaps identified by Critic          |
| `synthesis`          | `str`                       | Final output from Synthesizer                  |
| `iteration_count`    | `int`                       | Current loop iteration                         |
| `token_usage`        | `dict` (sum per key)        | Accumulated token counts                       |
| `errors`             | `list[str]` (append)        | Error messages from any stage                  |
| `trace_id`           | `str` (UUID)                | Per-turn tracing correlation ID                |
| `session_id`         | `str`                       | Canonical session identifier                   |

The `constraints` dict and `accumulated_context` field default to empty in standalone mode. When the conversational layer is active, the Coordinator populates them before invoking the graph, so agents read them to scope their work — no agent code changes needed.

### Observability

Every agent interaction is traced end-to-end:

- **Langfuse integration** — traces every agent invocation, tool call, and LLM call with a truncating callback handler that caps output size to `trace_excerpt_max_chars`
- **Custom Langfuse spans** — critic routing decisions and per-tool invocations emit dedicated spans via the Langfuse client API
- **Structlog** — JSON-formatted structured logs with correlation IDs (`trace_id`, `session_id`, `agent_id`, `client_session_id`) bound per research run
- **Tool usage logging** — every dynamic tool invocation logged to MySQL via `POST /tools/usage-log` with agent_id, session_id, latency, success/failure
- **Progress events** — SSE streaming of per-node stage events (`event: status`) for real-time UI updates

### Conversational Session Layer

The system extends into a multi-turn research assistant. A **Conversation Coordinator** agent sits in front of the research engine and manages the dialogue.

**Capabilities:**
- **Follow-up interpretation** — understands "go deeper on point 3" or "now compare just Microsoft and Meta" in the context of prior research
- **Query rewriting** — rewrites ambiguous follow-ups using prior synthesis context before classification
- **Intent classification** — LLM-based structured classification into `new_query | refinement | reformat | meta_question | needs_clarification`
- **Selective re-invocation** — doesn't rerun the full pipeline on every follow-up; decides which agents need to re-execute
- **Scope narrowing/widening** — translates user steering into constraints passed to agents
- **Session memory** — maintains chat history and prior research state snapshots so agents have context
- **Idempotency** — duplicate turn submissions with the same `Idempotency-Key` return cached responses
- **Concurrency control** — Redis-based per-session turn locks prevent concurrent mutations

**Session State (stored in Redis + MySQL):**
- `session_id` — unique conversation identifier (UUID)
- `message_history` — full chat transcript (user messages + system responses)
- `research_snapshots` — state of the LangGraph after each completed run
- `active_constraints` — user-defined filters currently in effect
- `accumulated_sources` — all sources gathered across turns, deduplicated

**Coordinator Decision Logic:**

| User Intent              | Action                                             |
|--------------------------|---------------------------------------------------|
| New research question    | Full pipeline run, new research state             |
| "Go deeper on X"        | Scoped Researcher re-run → Analyst → Synthesizer  |
| "Compare only A and B"  | Analyst re-run with filtered prior data            |
| "Reformat as bullets"   | Synthesizer re-run only, same data                |
| "What sources?"         | Direct answer from session state, no agent run    |
| Low-confidence intent   | Clarification request, no agent run               |

**API Endpoints:**

| Method | Path                            | Purpose                      |
|--------|---------------------------------|------------------------------|
| POST   | `/v1/sessions`                  | Create a new session         |
| POST   | `/v1/sessions/{id}/turns`       | Submit a turn (JSON or SSE)  |

SSE streaming is triggered by `Accept: text/event-stream` and emits `event: status` frames as graph nodes execute, followed by a final `event: result` frame.

### Operator Web UI

A React single-page application served by Vite with three views:

- **Chat** — create sessions, send messages, view streaming responses with stage indicators
- **Tool Catalog** — browse/search registry, view tool details and capabilities
- **Stats** — tool usage metrics, health check status, registry overview

The frontend proxies API calls to the backend via Vite's dev server (`/v1` and `/tools` → `http://127.0.0.1:8000`).

---

## Project Structure

```
researchSwarm/
├── README.md
├── Overview.md                      # This file
├── setup.sh                         # One-command local setup
├── teardown.sh                      # Clean shutdown of all services
├── docker-compose.yml               # MySQL, Langfuse + Postgres
├── pyproject.toml                   # Python package definition + deps
├── alembic.ini                      # Database migration config
├── .env.example                     # Environment variable template
├── registry/
│   ├── app.py                       # FastAPI app (registry + session APIs)
│   ├── config.py                    # Registry settings (DB URL, CORS, logging)
│   ├── models.py                    # SQLAlchemy models (Tool, ToolCapability, ToolUsageLog)
│   ├── schemas.py                   # Pydantic request/response schemas
│   ├── search.py                    # Tool search (capability filtering, status exclusion)
│   ├── seed.py                      # Seed 7 initial tools
│   ├── routers/                     # FastAPI routers (register, search, bind, usage, health, stats)
│   └── middleware/                   # Request logging middleware
├── agents/
│   ├── graph.py                     # build_research_graph, invoke_research_graph, LLM factory
│   ├── state.py                     # ResearchState TypedDict, validators, reducers
│   ├── config.py                    # AgentConfig (pydantic-settings, all LLM/tool/trace knobs)
│   ├── context.py                   # GraphContext TypedDict (LLM, registry, config, discovery)
│   ├── tracing.py                   # Langfuse callback, structlog helpers, progress queue
│   ├── response_models.py           # Structured LLM output schemas
│   ├── nodes/                       # researcher, analyst, critic, synthesizer node functions
│   ├── prompts/                     # Prompt templates per agent
│   └── tools/
│       ├── discovery.py             # ToolDiscoveryTool — search, select, bind, invoke, log
│       └── registry_client.py       # httpx client for registry + tool HTTP invocation
├── conversation/
│   ├── coordinator.py               # ConversationCoordinator — turn orchestration
│   ├── config.py                    # ConversationSettings (Redis, DB, thresholds)
│   ├── intent.py                    # LLM-based intent classification
│   ├── routing.py                   # Maps intent → RoutePlan (full_graph / synthesizer_only / clarify)
│   ├── merge.py                     # Builds engine input from snapshot + new message
│   ├── rewrite.py                   # Query rewriting with prior context
│   ├── models.py                    # IntentResult, TurnResult, SessionRow Pydantic models
│   ├── authz.py                     # Body fingerprinting for idempotency
│   ├── api/
│   │   └── routes.py                # Session + turn HTTP endpoints
│   └── persistence/
│       ├── mysql_store.py           # Session rows, turns, snapshots (SQLAlchemy async)
│       └── redis_store.py           # Turn locks, working-set document cache
├── alembic/
│   └── versions/                    # 001_initial_schema, 002_conversation_session_tables
├── web/
│   ├── src/
│   │   ├── App.tsx                  # React Router layout
│   │   ├── pages/                   # ChatView, ToolsPage, StatsPage
│   │   ├── components/              # ChatMessage, ToolCard, etc.
│   │   └── api/                     # sessions.ts, registry.ts (API clients)
│   ├── package.json
│   └── vite.config.ts               # Dev proxy to backend
├── scripts/
│   └── alembic_upgrade_lenient.py   # Idempotent migration runner
├── tests/
│   ├── test_registry.py
│   ├── test_agents.py
│   ├── test_dynamic_binding.py
│   └── test_conversation.py
└── postman/                          # Postman collection for API testing
```

---

## Implementation Phases

### Phase 1: Tool Registry Service
MySQL schema design, FastAPI endpoints (register, search, bind, health, stats), capability-based search and full catalog listing, seed registry with 7 tools, unit tests for registry CRUD and search.

### Phase 2: Agent Implementation
LangGraph state schema with annotated reducers, implement all four agents (Researcher, Analyst, Critic, Synthesizer), wire the conditional graph with loop-back from Critic to Researcher, multi-provider LLM factory.

### Phase 3: Dynamic Tool Binding
`ToolDiscoveryTool` meta-tool, runtime tool binding (agent receives schema, constructs callable LangChain tool on the fly via `StructuredTool.from_function`), tool usage logging, fallback strategies with ordered candidate list, Wikipedia enrichment pipeline.

### Phase 4: Observability & Polish
Langfuse trace integration with truncating callback handler, custom spans for critic routing and tool invocations, structured logging with correlation IDs, progress event streaming.

### Phase 5: Conversational Session Layer
Conversation Coordinator agent, session store (Redis for live locks/cache, MySQL for durable persistence), LLM-based intent classification, query rewriting, selective agent re-invocation routing, accumulated research state across turns, constraint propagation, idempotency support, SSE streaming.

### Phase 6: Operator Web UI
React chat interface with SSE streaming, tool catalog browser, usage statistics dashboard, Vite dev proxy configuration.

---

## Demo Scenarios

### Standalone Pipeline

> **Query:** "Compare the AI strategies of Microsoft, Google, and Meta based on their latest 10-K filings and recent acquisitions"

This forces: dynamic tool discovery (SEC filing parser), multi-source research, cross-company analysis, fact-checking, structured synthesis with citations.

### Conversational Session

```
You:    "Compare the AI strategies of Microsoft, Google, and Meta"
System: [Full pipeline run — Researcher, Analyst, Critic, Synthesizer]
        → Structured report with 23 sources, 3-company comparison

You:    "Drop Meta, focus on just Microsoft and Google"
System: [Analyst re-runs on filtered data, Synthesizer regenerates]
        → Updated 2-company comparison, same sources, no new research

You:    "Go deeper on Google's TPU investment specifically"
System: [Researcher re-runs scoped to "Google TPU investment", Analyst merges with prior findings]
        → Expanded section on Google TPUs added to existing report

You:    "What sources did you use for the Microsoft section?"
System: [No agents invoked — answered from session state]
        → List of 8 sources with titles, URLs, and which claims they support
```

---

## Performance Targets

| Metric                       | Target          |
|------------------------------|-----------------|
| End-to-end query latency     | < 60 seconds    |
| Tool registry search latency | < 100ms         |
| Tool health check response   | < 500ms         |
| Dynamic tool binding time    | < 200ms         |
| Agent LLM call p95 latency   | < 10 seconds    |

---

## Success Criteria

### Standalone Research Engine
- An agent successfully discovers and uses a tool it was NOT pre-configured with
- Full trace visible in Langfuse showing multi-agent collaboration
- Research output includes proper citations to sources
- Tool registry has >5 registered tools with health checks passing
- End-to-end research query completes in <60 seconds
- Critic loop-back triggers when information gaps are detected

### Conversational Layer
- User can refine research across multiple turns without restarting from scratch
- "Go deeper on X" triggers only the necessary agents, not the full pipeline
- Session state persists across turns with accumulated sources and findings
- Constraint narrowing (e.g., "only SEC filings") correctly filters subsequent agent runs
- Meta-questions ("what sources did you use?") resolve from session state without invoking agents
