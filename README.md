# Multi-Agent Research Swarm with Dynamic Tool Registry

A system where specialized AI agents collaborate to answer complex research questions. The core innovation is a **tool registry service** — agents don't carry a hardcoded tool list. Mid-execution, an agent realizes it needs a capability (e.g., "parse SEC filings"), queries the registry, discovers a matching tool, binds it dynamically, and uses it.

## Philosophy

- **Distributed agents, not linear workflows** — agents are autonomous collaborators, not chained steps
- **Just-in-time dynamic tooling** — tools are discovered and bound at runtime, not pre-configured
- **Microservices patterns applied to AI** — each concern is isolated, independently testable, independently deployable
- **Observability from day one** — every LLM call, tool invocation, and agent decision is traced and logged
- **Conversational, not transactional** — research is iterative; the system is designed to support multi-turn sessions where users steer, narrow, and deepen research over a conversation

## Architecture

The architecture separates the research engine (the agent graph) from the interface layer. The research engine is a self-contained LangGraph pipeline. The conversational layer (Phase 5) sits on top, managing sessions, interpreting follow-ups, and selectively re-invoking agents — but the engine works standalone first.

```
┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
  Phase 5: Conversational Layer (future)
│                                                         │
  ┌─────────────────────────────────────────────────────┐
│ │              Conversation Coordinator               │ │
  │  - Interprets follow-ups & refinement requests      │
│ │  - Maintains session memory (message history)       │ │
  │  - Decides: re-run full pipeline / partial / reformat│
│ │  - Scopes constraints for targeted re-investigation │ │
  └──────────────────────┬──────────────────────────────┘
│                        │                                │
  ┌──────────────────────▼──────────────────────────────┐
│ │              Session Store (Redis/MySQL)             │ │
  │  - Chat history per session                         │
│ │  - Prior research state snapshots                   │ │
  │  - User-defined constraints & preferences           │
│ └─────────────────────────────────────────────────────┘ │
 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─│─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                          │
                          ▼
┌─────────────────────────────────────────────────────────┐
│                Research Engine (LangGraph)               │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐  │
│  │Researcher│ │ Analyst  │ │ Critic  │ │Synthesizer │  │
│  └────┬─────┘ └────┬─────┘ └────┬────┘ └─────┬──────┘  │
│       └─────────────┴──────┬─────┴─────────────┘         │
│                            │                             │
│                   ┌────────▼────────┐                    │
│                   │  Tool Registry  │                    │
│                   │   (FastAPI +    │                    │
│                   │     MySQL)      │                    │
│                   └────────┬────────┘                    │
│                            │                             │
│            ┌───────────────┼───────────────┐             │
│         ┌──▼──┐        ┌───▼───┐       ┌───▼──┐         │
│         │SerpAPI│      │ArXiv  │       │GitHub│  ...     │
│         │Search│       │Parser │       │ API  │          │
│         └──────┘       └───────┘       └──────┘          │
└─────────────────────────────────────────────────────────┘
            │
    ┌───────▼────────┐
    │  Langfuse /    │
    │  LangSmith     │
    │  (Tracing)     │
    └────────────────┘
```

**Key design constraint:** The research engine MUST be fully functional without the conversational layer. The conversational layer calls into the engine — the engine never depends on it. This keeps Phases 1-4 shippable as a standalone pipeline and makes the conversational layer a pure extension.

## Tech Stack

| Layer              | Technology                                                           |
|--------------------|----------------------------------------------------------------------|
| **Orchestration**  | LangGraph — agent state machine, conditional routing, parallel exec  |
| **LLM**           | OpenAI GPT-4o / Anthropic Claude via LangChain abstraction           |
| **Tool Registry**  | FastAPI + MySQL (tool metadata, capability tags, versioning)          |
| **Tracing**        | Langfuse (self-hosted or cloud) for full trace visibility            |
| **Logging**        | Structlog with correlation IDs per research session                  |
| **Session Store**  | Redis (chat history, state snapshots) + MySQL (persistent sessions)  |
| **Testing**        | Pytest + LangSmith evaluation datasets                               |
| **Containerization** | Docker Compose (MySQL, Redis, Langfuse)                             |
| **Language**       | Python 3.11+                                                         |

## Core Components

### Tool Registry

A standalone FastAPI service that acts as a catalog for all available tools. Each tool is registered with metadata, capability tags, input/output schemas, health checks, and latency stats.

**Endpoints:**
- `POST /tools/register` — register a new tool with metadata + schema
- `GET /tools/search?capability=X` — search by capability tag (or list all tools when no filter)
- `GET /tools/{id}/bind` — returns LangChain-compatible tool definition for runtime binding
- `GET /tools/{id}/health` — proxied health check
- `GET /tools/stats` — usage statistics per tool

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

**Discovery Flow:**
1. Agent receives the full tool catalog from the registry (`GET /tools/search`)
   or filters by capability (`GET /tools/search?capability=financial_data`)
2. The LLM selects the best tool based on the full tool definitions
3. Agent calls the registry for a LangChain-compatible definition (`GET /tools/{id}/bind`)
4. Agent binds the tool and invokes it within the current execution

### Agent layer (LangGraph)

The `agents/` package runs the research **StateGraph**: Researcher → Analyst → Critic, with conditional loop-back to the Researcher when the Critic fails the quality gate, then Synthesizer → end. Agents use the registry **only via HTTP** (`GET /tools/search`, `GET /tools/{id}/bind`, `POST /tools/usage-log` for invocation metrics).

**Quickstart:** [specs/002-agent-layer/quickstart.md](specs/002-agent-layer/quickstart.md) — configure `GOOGLE_API_KEY`, `REGISTRY_BASE_URL`, and optional Langfuse vars in `.env`.

**Entry points:** `build_research_graph()`, `invoke_research_graph()` (wraps `ainvoke` with `asyncio.timeout` from `AgentConfig.graph_timeout_seconds` and a single-flight guard raising `GraphBusyError` if a run is already active), and `default_graph_context()` to build a Gemini client plus `RegistryClient`.

**Graph sketch:** `build_research_graph().get_graph().draw_ascii()` (requires `pip install grandalf`).

### Agent Roles

| Agent           | Role                                              | Static Tools                | Dynamic Tools                                    |
|-----------------|---------------------------------------------------|-----------------------------|--------------------------------------------------|
| **Researcher**  | Gathers raw information from multiple sources     | Web search, URL scraper     | Discovered per-query (domain-specific parsers)   |
| **Analyst**     | Structures, compares, identifies patterns         | Calculator, data formatter  | Discovered per-domain (financial, code analysis) |
| **Critic**      | Fact-checks claims, identifies gaps               | Web search (verification)   | Source-specific validators                       |
| **Synthesizer** | Produces final structured research brief          | Report formatter, citations | None (consumes outputs)                          |

### Agent Orchestration

Agents are wired via LangGraph in a directed graph with conditional edges:

```
Researcher → Analyst → Critic ─┬─→ Synthesizer (if satisfied)
                                └─→ Researcher  (if gaps found)
```

The Critic can loop the workflow back to the Researcher when it identifies information gaps, ensuring research completeness before synthesis.

**State schema extensibility:** The LangGraph state includes a `constraints` dict (source filters, entity focus, depth parameters) and an `accumulated_context` field (prior findings from earlier turns). Both default to empty in Phases 1-4. In Phase 5, the Conversation Coordinator populates them before invoking the graph, and agents read them to scope their work. This means the engine supports conversational steering without any agent code changes — only the input to the graph changes.

### Observability

Every agent interaction is traced end-to-end:
- **Langfuse integration** — traces every agent invocation, tool call, and LLM call
- **Structlog** — JSON-formatted structured logs with correlation IDs per research session
- **Tool usage logging** — every dynamic tool invocation logged with agent_id, session_id, latency, success/failure

### Conversational Interface (Phase 5)

The system extends into a multi-turn research assistant. A **Conversation Coordinator** agent sits in front of the research engine and manages the dialogue:

**Capabilities:**
- **Follow-up interpretation** — understands "go deeper on point 3" or "now compare just Microsoft and Meta" in the context of prior research
- **Selective re-invocation** — doesn't rerun the full pipeline on every follow-up; decides which agents need to re-execute (e.g., only Researcher for new data, only Synthesizer for reformatting)
- **Scope narrowing/widening** — translates user steering into constraints passed to agents (source filters, entity focus, depth parameters)
- **Session memory** — maintains chat history and prior research state snapshots so agents have context from previous turns
- **Research continuity** — accumulated findings persist across turns; new research builds on prior results rather than starting from scratch

**Session State (stored in Redis + MySQL):**
- `session_id` — unique conversation identifier
- `message_history` — full chat transcript (user messages + system responses)
- `research_snapshots` — state of the LangGraph after each completed run (raw findings, analysis, critique, synthesis)
- `active_constraints` — user-defined filters currently in effect (source types, entity focus, time range)
- `accumulated_sources` — all sources gathered across turns, deduplicated

**Coordinator Decision Logic:**
| User Intent              | Action                                          |
|--------------------------|------------------------------------------------|
| New research question    | Full pipeline run, new research state          |
| "Go deeper on X"        | Scoped Researcher re-run → Analyst → Synthesizer |
| "Compare only A and B"  | Analyst re-run with filtered prior data → Synthesizer |
| "Reformat as bullet points" | Synthesizer re-run only, same data          |
| "What sources did you use?" | Direct answer from session state, no agent run |
| "Drop the blog posts"   | Update active_constraints, Analyst re-run      |

**Design for extensibility:** The research engine's LangGraph state schema includes an optional `constraints` dict from day one. In Phases 1-4 it defaults to empty. In Phase 5 the Coordinator populates it. This means no refactoring of the engine is needed when the conversational layer is added.

## Project Structure

```
researchSwarm/
├── README.md
├── docker-compose.yml              # MySQL, Redis, Langfuse
├── pyproject.toml
├── .env.example
├── registry/
│   ├── app.py                       # FastAPI tool registry service
│   ├── models.py                    # SQLAlchemy models
│   ├── schemas.py                   # Pydantic schemas
│   ├── search.py                    # Tool search (capability filtering)
│   └── seed.py                      # Seed initial tools
├── agents/
│   ├── graph.py                     # build_research_graph, invoke_research_graph
│   ├── state.py                     # ResearchState, validators, reducers
│   ├── config.py                   # AgentConfig (pydantic-settings)
│   ├── tracing.py                  # Langfuse callback + structlog helpers
│   ├── response_models.py          # Structured LLM outputs
│   ├── nodes/                      # researcher, analyst, critic, synthesizer
│   ├── prompts/                    # Prompt templates per agent
│   └── tools/
│       └── registry_client.py      # httpx client for registry + tool HTTP invoke
├── tools/
│   ├── base.py                      # Dynamic tool builder
│   ├── serp.py
│   ├── arxiv_tool.py
│   ├── github_tool.py
│   └── sec_parser.py
├── conversation/                    # Phase 5
│   ├── coordinator.py               # Conversation Coordinator agent
│   ├── session.py                   # Session management (Redis + MySQL)
│   ├── intent.py                    # User intent classification
│   └── router.py                    # Maps intents to agent re-invocation strategies
├── observability/
│   ├── tracing.py                   # Langfuse setup
│   └── logging.py                   # Structlog config
└── tests/
    ├── test_registry.py
    ├── test_agents.py
    ├── test_dynamic_binding.py
    └── test_conversation.py         # Phase 5
```

## Implementation Phases

### Phase 1: Tool Registry Service
MySQL schema design, FastAPI endpoints (register, search, bind, health, stats), capability-based search and full catalog listing, seed registry with 7 tools, unit tests for registry CRUD and search.

### Phase 2: Agent Implementation
LangGraph state schema, implement all four agents (Researcher, Analyst, Critic, Synthesizer), wire the conditional graph with loop-back from Critic to Researcher.

### Phase 3: Dynamic Tool Binding
Build the `ToolDiscoveryTool` meta-tool, implement runtime tool binding (agent receives schema, constructs callable LangChain tool on the fly), add tool usage logging, handle failures with fallback strategies, integration tests.

### Phase 4: Observability & Polish
Langfuse trace integration, structured logging with correlation IDs, demo scenario execution, documentation.

### Phase 5: Conversational Session Layer (future)
Conversation Coordinator agent, session store (Redis for live state, MySQL for persistence), user intent classification (new query vs. refinement vs. reformatting vs. meta-question), selective agent re-invocation routing, accumulated research state across turns, constraint propagation into the engine's state schema.

## Success Criteria

### Phases 1-4 (Standalone Research Engine)
- An agent successfully discovers and uses a tool it was NOT pre-configured with
- Full trace visible in Langfuse showing multi-agent collaboration
- Research output includes proper citations to sources
- Tool registry has >5 registered tools with health checks passing
- End-to-end research query completes in <60 seconds
- Critic loop-back triggers when information gaps are detected

### Phase 5 (Conversational Layer)
- User can refine research across multiple turns without restarting from scratch
- "Go deeper on X" triggers only the necessary agents, not the full pipeline
- Session state persists across turns with accumulated sources and findings
- Constraint narrowing (e.g., "only SEC filings") correctly filters subsequent agent runs
- Meta-questions ("what sources did you use?") resolve from session state without invoking agents

## Demo Scenarios

### Standalone Pipeline (Phases 1-4)

> **Query:** "Compare the AI strategies of Microsoft, Google, and Meta based on their latest 10-K filings and recent acquisitions"

This forces: dynamic tool discovery (SEC filing parser), multi-source research, cross-company analysis, fact-checking, structured synthesis with citations.

### Conversational Session (Phase 5)

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

## Performance Targets

| Metric                       | Target          |
|------------------------------|-----------------|
| End-to-end query latency     | < 60 seconds    |
| Tool registry search latency | < 100ms         |
| Tool health check response   | < 500ms         |
| Dynamic tool binding time    | < 200ms         |
| Agent LLM call p95 latency   | < 10 seconds    |
