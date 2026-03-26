# AI/Agent Project Portfolio

## Philosophy

- Distributed agents, not linear workflows with LLMs bolted on
- Just-in-time dynamic tooling over hardcoded tool lists
- Microservices and distributed systems patterns applied to AI
- Advanced RAG with modular, scalable, maintainable modules
- Observability (monitoring, logging, tracing) baked in from day one
- Use existing industry abstractions (LangChain, LangGraph, etc.) to build impressive systems

---

## Project Ideas Overview

### #1 — Multi-Agent Research Swarm with Dynamic Tool Registry
Specialized agents (researcher, analyst, critic, synthesizer) collaborate on complex research. Agents discover and bind tools at runtime via a tool registry service, not a hardcoded list.

### #2 — Production RAG Platform with Evaluation & Drift Detection
End-to-end RAG with multi-source ingestion, hybrid retrieval, and the real differentiator: a continuous evaluation loop that measures retrieval quality, answer faithfulness, detects quality degradation over time, and alerts.

### #3 — Self-Healing Agentic Data Pipeline
Data pipeline where AI agents supervise, diagnose, and fix failures autonomously. Full audit trail of every autonomous decision. Circuit breakers, retries, fallbacks — but decision-making is agentic.

### #4 — Multi-Tenant RAG-as-a-Service with Auto Strategy Selection
API where tenants upload a corpus and the system automatically determines the best retrieval strategy. Per-tenant usage metrics, cost tracking, quality monitoring.

### #5 — Distributed Agent Mesh with Observability Console
Agents run as independent services communicating via message queues. Real-time observability console: agent status, message flow, latency, token usage, error rates, conversation replay with decision traces.

### #6 — Agentic Competitive Intelligence System
Give it a company/product, agent swarm gathers news, filings, social sentiment, GitHub activity, synthesizes a competitive brief. Runs on schedule with delta detection.

---

## Timeline Summary

| Project | Part-time (2-3h/day) | Full-time Sprint | Complexity | Demo Impact |
|---------|----------------------|-------------------|------------|-------------|
| #1 Dynamic Tool Registry | 3-4 weeks | 8-10 days | Medium-High | High |
| #2 RAG + Eval/Drift | 4-5 weeks | 9-12 days | Medium-High | High |
| #3 Self-Healing Pipeline | 3-4 weeks | 7-11 days | Medium | Medium-High |
| #4 RAG-as-a-Service | 5-6 weeks | 13-15 days | Highest | Medium-High |
| #5 Agent Mesh + Console | 4-5 weeks | 10-12 days | Highest | Highest |
| #6 Competitive Intel | 3-4 weeks | 7-10 days | Medium | High |

---
---

# DETAILED PLANS

---

## Plan: #1 — Multi-Agent Research Swarm with Dynamic Tool Registry

### Vision
A system where multiple specialized AI agents collaborate to answer complex research questions. The core innovation is a **tool registry service** — agents don't have a hardcoded tool list. Mid-execution, an agent realizes it needs a capability (e.g., "parse SEC filings"), queries the registry, discovers a matching tool, binds it dynamically, and uses it. This is the "just-in-time dynamic tooling" thesis made real.

### Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    LangGraph Orchestrator                │
│  ┌──────────┐ ┌──────────┐ ┌─────────┐ ┌────────────┐  │
│  │Researcher│ │ Analyst  │ │ Critic  │ │Synthesizer │  │
│  └────┬─────┘ └────┬─────┘ └────┬────┘ └─────┬──────┘  │
│       │             │            │             │         │
│       └─────────────┴──────┬─────┴─────────────┘         │
│                            │                             │
│                   ┌────────▼────────┐                    │
│                   │  Tool Registry  │                    │
│                   │   (FastAPI +    │                    │
│                   │   PostgreSQL)   │                    │
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

### Tech Stack
- **Orchestration:** LangGraph (agent state machine, conditional routing, parallel execution)
- **LLM:** OpenAI GPT-4o / Anthropic Claude (via LangChain's LLM abstraction)
- **Tool Registry:** FastAPI service + PostgreSQL (tool metadata, capability tags, versioning)
- **Tracing/Observability:** Langfuse (self-hosted or cloud) for full trace visibility
- **Logging:** Structlog with correlation IDs per research session
- **Testing:** Pytest + LangSmith evaluation datasets

### Tool Registry Design

Each tool registered in the system has:
```json
{
  "tool_id": "sec-filing-parser-v1",
  "name": "SEC Filing Parser",
  "description": "Parses SEC EDGAR filings (10-K, 10-Q, 8-K) and extracts structured financial data",
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
1. Agent determines it needs a capability (e.g., "I need financial data for AAPL")
2. Agent calls registry: `GET /tools/search?capability=financial_data`
3. Registry returns matching tools ranked by relevance
4. Agent selects tool, registry returns the tool's LangChain-compatible definition
5. Agent binds the tool and invokes it within the current execution

### Agent Definitions

| Agent | Role | Tools (static) | Tools (dynamic) |
|-------|------|-----------------|-----------------|
| **Researcher** | Gathers raw information from multiple sources | Web search, URL scraper | Discovered per-query (domain-specific parsers) |
| **Analyst** | Structures, compares, identifies patterns | Calculator, data formatter | Discovered per-domain (financial tools, code analyzers) |
| **Critic** | Fact-checks claims, identifies gaps, challenges assumptions | Web search (verification) | Source-specific validators |
| **Synthesizer** | Produces final structured research brief | Report formatter, citation manager | None (consumes outputs) |

### Detailed Phase Plan

#### Phase 1: Tool Registry Service (Days 1-5)
- [ ] Design PostgreSQL schema: `tools`, `tool_capabilities`, `tool_usage_logs`
- [ ] FastAPI endpoints:
  - `POST /tools/register` — register a new tool with metadata + schema
  - `GET /tools/search?capability=X&query=Y` — semantic search over tool descriptions
  - `GET /tools/{id}/bind` — returns LangChain-compatible tool definition
  - `GET /tools/{id}/health` — proxied health check
  - `GET /tools/stats` — usage statistics per tool
- [ ] Embed tool descriptions with a small embedding model for semantic search
- [ ] Seed registry with 5-8 tools (SerpAPI, ArXiv, GitHub, Wikipedia, calculator, URL scraper, etc.)
- [ ] Unit tests for registry CRUD and search

#### Phase 2: Agent Implementation (Days 6-12)
- [ ] Define LangGraph state schema (research question, gathered data, analysis, critiques, final output)
- [ ] Implement Researcher agent:
  - Takes research question, decomposes into sub-questions
  - Searches tool registry for relevant data-gathering tools
  - Executes searches, stores raw findings in state
- [ ] Implement Analyst agent:
  - Takes raw findings, identifies patterns and structures data
  - Can request additional tools if analysis requires specific capabilities
- [ ] Implement Critic agent:
  - Reviews analyst output, fact-checks key claims
  - Identifies gaps, sends back to researcher if needed (conditional loop)
- [ ] Implement Synthesizer agent:
  - Produces final structured brief with citations
- [ ] LangGraph wiring: Researcher → Analyst → Critic → (loop back or) Synthesizer

#### Phase 3: Dynamic Tool Binding (Days 13-19)
- [ ] Build the `ToolDiscoveryTool` — a meta-tool that agents use to search the registry
- [ ] Implement runtime tool binding: agent receives tool schema from registry, constructs a callable LangChain tool on the fly
- [ ] Add tool usage logging: every dynamic tool invocation is logged with agent_id, session_id, latency, success/failure
- [ ] Handle failures: if a dynamically discovered tool fails, agent falls back to alternative tools or reports limitation
- [ ] Integration test: end-to-end research query that requires a tool the agent wasn't pre-configured with

#### Phase 4: Observability & Demo (Days 20-26)
- [ ] Integrate Langfuse: trace every agent invocation, tool call, LLM call
- [ ] Structured logging with structlog: correlation_id per research session, log levels, JSON output
- [ ] Build a demo scenario:
  - Query: "Compare the AI strategies of Microsoft, Google, and Meta based on their latest 10-K filings and recent acquisitions"
  - This forces: dynamic tool discovery (SEC parser), multi-source research, cross-company analysis
- [ ] Record a walkthrough showing the trace in Langfuse (agent flow, tool discovery, latencies)
- [ ] Write README with architecture diagram, setup instructions, demo video link

### Key Files / Directory Structure
```
agent-research-swarm/
├── README.md
├── docker-compose.yml              # Postgres, Redis, Langfuse
├── pyproject.toml
├── .env.example
├── registry/
│   ├── app.py                       # FastAPI tool registry
│   ├── models.py                    # SQLAlchemy models
│   ├── schemas.py                   # Pydantic schemas
│   ├── search.py                    # Semantic tool search
│   └── seed.py                      # Seed initial tools
├── agents/
│   ├── graph.py                     # LangGraph definition
│   ├── state.py                     # State schema
│   ├── researcher.py
│   ├── analyst.py
│   ├── critic.py
│   ├── synthesizer.py
│   └── tool_discovery.py           # Meta-tool for runtime discovery
├── tools/
│   ├── base.py                      # Dynamic tool builder
│   ├── serp.py
│   ├── arxiv_tool.py
│   ├── github_tool.py
│   └── sec_parser.py
├── observability/
│   ├── tracing.py                   # Langfuse setup
│   └── logging.py                   # Structlog config
└── tests/
    ├── test_registry.py
    ├── test_agents.py
    └── test_dynamic_binding.py
```

### Success Criteria
- [ ] An agent successfully discovers and uses a tool it was NOT pre-configured with
- [ ] Full trace visible in Langfuse showing multi-agent collaboration
- [ ] Research output includes proper citations to sources
- [ ] Tool registry has >5 registered tools with health checks passing
- [ ] Average end-to-end research query completes in <60 seconds

---
---

## Plan: #2 — Production RAG Platform with Evaluation & Drift Detection

### Vision
An end-to-end RAG system where the *real* value is not the retrieval itself but the **production monitoring layer**: continuous evaluation of retrieval quality, answer faithfulness measurement via LLM-as-judge, embedding drift detection, and automated alerting when quality degrades. This is what separates a demo from a production system.

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                      Ingestion Pipeline                      │
│  ┌─────┐  ┌─────┐  ┌──────┐  ┌────────┐  ┌──────────────┐  │
│  │ PDF │  │ Web │  │ SQL  │  │Markdown│  │   API JSON   │  │
│  └──┬──┘  └──┬──┘  └──┬───┘  └───┬────┘  └──────┬───────┘  │
│     └────────┴────────┴──────────┴───────────────┘           │
│                         │                                    │
│              ┌──────────▼──────────┐                         │
│              │  Chunking Engine    │                         │
│              │  (recursive, semantic│                        │
│              │   parent-child)     │                         │
│              └──────────┬──────────┘                         │
│                         │                                    │
│              ┌──────────▼──────────┐                         │
│              │  Embedding + Store  │                         │
│              │  (Qdrant / Chroma)  │                         │
│              └─────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                    Retrieval Pipeline                         │
│  ┌────────────┐  ┌────────────┐  ┌─────────────────────┐    │
│  │Dense Search│  │BM25 Sparse │  │  Reciprocal Rank    │    │
│  │ (Vector)   │  │  Search    │  │  Fusion (Hybrid)    │    │
│  └─────┬──────┘  └─────┬──────┘  └──────────┬──────────┘    │
│        └───────────────┬┘                    │               │
│              ┌─────────▼─────────┐           │               │
│              │   Re-Ranker       │◄──────────┘               │
│              │(Cohere/CrossEnc.) │                            │
│              └─────────┬─────────┘                            │
│                        │                                     │
│              ┌─────────▼─────────┐                           │
│              │  LLM Generation   │                           │
│              │  (with citations) │                           │
│              └───────────────────┘                           │
└─────────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────▼───────────────────────────────────┐
│                 Evaluation & Monitoring                       │
│  ┌──────────────┐  ┌───────────────┐  ┌─────────────────┐   │
│  │ RAGAS /      │  │  Embedding    │  │  Prometheus     │   │
│  │ DeepEval     │  │  Drift        │  │  + Grafana      │   │
│  │ (Quality)    │  │  Detection    │  │  (Dashboards)   │   │
│  └──────┬───────┘  └───────┬───────┘  └────────┬────────┘   │
│         └──────────────────┴───────────────────┘             │
│                            │                                 │
│                   ┌────────▼────────┐                        │
│                   │  Alerting       │                        │
│                   │  (Slack/Email)  │                        │
│                   └─────────────────┘                        │
└─────────────────────────────────────────────────────────────┘
```

### Tech Stack
- **RAG Framework:** LangChain (document loaders, text splitters, retrievers, chains)
- **Vector Store:** Qdrant (self-hosted via Docker) — supports dense + sparse in one store
- **Sparse Search:** BM25 via rank_bm25 or Qdrant's built-in sparse vectors
- **Re-Ranker:** Cohere Rerank API or a cross-encoder model
- **Evaluation:** RAGAS (retrieval metrics) + DeepEval (answer quality) + custom LLM-as-judge
- **Metrics:** Prometheus client library (python) → Grafana dashboards
- **Logging:** Structlog with correlation IDs tying query → retrieved chunks → generated answer
- **Alerting:** Slack webhooks or email via SMTP
- **API:** FastAPI for the query endpoint and ingestion triggers
- **Scheduling:** APScheduler or Celery Beat for periodic evaluation jobs

### Evaluation Metrics Tracked

| Metric | What it measures | How |
|--------|------------------|-----|
| **Context Precision** | Are the retrieved chunks relevant? | RAGAS |
| **Context Recall** | Did we retrieve all the relevant chunks? | RAGAS (needs ground truth) |
| **Faithfulness** | Is the answer grounded in the retrieved context? | LLM-as-judge |
| **Answer Relevancy** | Does the answer address the question? | LLM-as-judge |
| **MRR@k** | Rank of first relevant result | Custom (needs labeled data) |
| **Latency (p50/p95/p99)** | End-to-end and per-stage latency | Prometheus histograms |
| **Embedding Drift** | Are new documents' embeddings shifting distribution? | Cosine similarity of centroid over time |
| **Retrieval Empty Rate** | % of queries that return 0 relevant chunks | Custom counter |
| **Chunk Utilization** | % of stored chunks that are never retrieved | Custom (periodic scan) |

### Drift Detection Approach

1. **Embedding Centroid Tracking:** On each ingestion batch, compute the centroid of new embeddings. Compare to the running centroid. If cosine distance exceeds threshold → alert.
2. **Query-Result Quality Decay:** Run a fixed evaluation dataset (golden questions + expected answers) on a schedule (daily/weekly). Plot quality scores over time. If scores drop below threshold → alert.
3. **Distribution Shift:** Track the distribution of similarity scores returned by queries. A shift in the distribution (e.g., scores getting lower on average) indicates the corpus or embeddings are drifting.

### Detailed Phase Plan

#### Phase 1: Multi-Source Ingestion Pipeline (Days 1-7)
- [ ] Set up project structure, Docker Compose (Qdrant, Prometheus, Grafana)
- [ ] Implement document loaders:
  - PDF (LangChain PyPDFLoader)
  - Web pages (LangChain WebBaseLoader + BeautifulSoup)
  - SQL databases (LangChain SQLDatabaseLoader or custom)
  - Markdown / text files
  - JSON / API responses
- [ ] Implement chunking strategies:
  - Recursive character splitting (baseline)
  - Semantic chunking (split on topic boundaries)
  - Parent-child chunking (store small chunks, retrieve parent for context)
- [ ] Embed and store in Qdrant with metadata (source, timestamp, chunk_method)
- [ ] FastAPI endpoint: `POST /ingest` (accepts file upload or URL)
- [ ] Structured logging for entire ingestion pipeline

#### Phase 2: Hybrid Retrieval Chain (Days 8-14)
- [ ] Dense retrieval via Qdrant vector search
- [ ] Sparse retrieval via BM25 (rank_bm25 or Qdrant sparse vectors)
- [ ] Reciprocal Rank Fusion to merge dense + sparse results
- [ ] Re-ranking step (Cohere Rerank or cross-encoder)
- [ ] LangChain RAG chain with citation tracking (each claim maps to source chunk)
- [ ] FastAPI endpoint: `POST /query` (returns answer + citations + metadata)
- [ ] Prometheus instrumentation: query latency histogram, retrieval count, empty result counter
- [ ] Correlation ID: tie each query to its retrieved chunks and generated answer in logs

#### Phase 3: Evaluation Loop (Days 15-21)
- [ ] Create a golden evaluation dataset (20-30 question/answer/context triples)
- [ ] Integrate RAGAS: context_precision, context_recall, faithfulness, answer_relevancy
- [ ] Build custom LLM-as-judge evaluator for edge cases RAGAS doesn't cover
- [ ] Store evaluation results in PostgreSQL with timestamps
- [ ] Scheduled evaluation job: runs golden dataset through the pipeline daily, stores scores
- [ ] Prometheus metrics for eval scores (gauges updated after each eval run)
- [ ] API endpoint: `GET /eval/history` — returns quality scores over time

#### Phase 4: Drift Detection & Alerting (Days 22-30)
- [ ] Embedding drift detector:
  - On each ingestion, compute batch centroid
  - Compare to running centroid, log cosine distance
  - Prometheus gauge for drift score
- [ ] Query quality decay detector:
  - Compare latest eval run scores to 7-day rolling average
  - Alert if any metric drops >10% below rolling average
- [ ] Retrieval score distribution tracker:
  - Log similarity scores for every query
  - Detect distribution shift via simple statistical test (KS test or mean comparison)
- [ ] Alerting:
  - Slack webhook integration for critical alerts
  - Email digest for weekly quality summary
- [ ] Grafana dashboard:
  - Panel 1: Eval scores over time (line chart)
  - Panel 2: Query latency percentiles (histogram)
  - Panel 3: Embedding drift score (gauge + time series)
  - Panel 4: Retrieval empty rate (counter)
  - Panel 5: Ingestion volume over time

#### Phase 5: Polish & Demo (Days 31-35)
- [ ] End-to-end demo scenario:
  - Ingest a corpus (e.g., company documentation)
  - Run queries, show citations
  - Inject "drift" (add documents from a different domain)
  - Show drift detection firing, quality scores dropping, alert triggered
- [ ] Write README with architecture diagram, setup instructions
- [ ] Record demo walkthrough
- [ ] Clean up code, add docstrings to public APIs

### Key Files / Directory Structure
```
rag-eval-platform/
├── README.md
├── docker-compose.yml              # Qdrant, Prometheus, Grafana, Postgres
├── grafana/
│   └── dashboards/
│       └── rag-quality.json        # Pre-built Grafana dashboard
├── prometheus/
│   └── prometheus.yml              # Scrape config
├── pyproject.toml
├── .env.example
├── app/
│   ├── main.py                     # FastAPI app
│   ├── config.py                   # Settings via pydantic-settings
│   ├── ingestion/
│   │   ├── loaders.py              # Multi-source document loaders
│   │   ├── chunkers.py             # Chunking strategies
│   │   └── pipeline.py             # Ingestion orchestrator
│   ├── retrieval/
│   │   ├── dense.py                # Vector search
│   │   ├── sparse.py               # BM25 search
│   │   ├── hybrid.py               # Reciprocal Rank Fusion
│   │   ├── reranker.py             # Re-ranking step
│   │   └── chain.py                # Full RAG chain with citations
│   ├── evaluation/
│   │   ├── ragas_eval.py           # RAGAS integration
│   │   ├── llm_judge.py            # Custom LLM-as-judge
│   │   ├── golden_dataset.json     # Eval question/answer pairs
│   │   └── scheduler.py            # Periodic evaluation jobs
│   ├── monitoring/
│   │   ├── metrics.py              # Prometheus metrics definitions
│   │   ├── drift.py                # Embedding drift detection
│   │   ├── alerts.py               # Slack/email alerting
│   │   └── quality_tracker.py      # Quality score storage + trends
│   └── observability/
│       └── logging.py              # Structlog config, correlation IDs
└── tests/
    ├── test_ingestion.py
    ├── test_retrieval.py
    ├── test_evaluation.py
    └── test_drift.py
```

### Success Criteria
- [ ] Ingest documents from ≥3 different source types
- [ ] Hybrid retrieval (dense + sparse + rerank) outperforms dense-only on eval dataset
- [ ] Evaluation pipeline runs on schedule and stores historical scores
- [ ] Grafana dashboard shows live quality metrics
- [ ] Drift detection fires when you inject out-of-domain documents
- [ ] Slack alert received when quality drops below threshold

---
---

## Plan: #5 — Distributed Agent Mesh with Observability Console

### Vision
Agents run as **independent microservices** that communicate via message queues. Each agent has its own health endpoint, publishes structured events, and can be scaled independently. The centerpiece is a **real-time observability console** that visualizes agent collaboration: which agents are active, message flow between them, latency per agent, token usage, error rates, and full conversation replay with decision traces.

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         Message Bus                               │
│                    (Redis Streams / RabbitMQ)                      │
│                                                                   │
│   ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐   │
│   │  Agent A  │    │  Agent B  │    │  Agent C  │    │  Agent D  │  │
│   │ (FastAPI) │    │ (FastAPI) │    │ (FastAPI) │    │ (FastAPI) │  │
│   │           │    │           │    │           │    │           │  │
│   │ /health   │    │ /health   │    │ /health   │    │ /health   │  │
│   │ /invoke   │    │ /invoke   │    │ /invoke   │    │ /invoke   │  │
│   └─────┬─────┘    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘ │
│         │                │                │                │       │
│         └────────────────┴────────┬───────┴────────────────┘       │
│                                   │                                │
│                        ┌──────────▼──────────┐                     │
│                        │   Event Collector   │                     │
│                        │  (consumes events   │                     │
│                        │   from all agents)  │                     │
│                        └──────────┬──────────┘                     │
└───────────────────────────────────┼────────────────────────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │     Observability Console      │
                    │        (React + WebSocket)     │
                    │                                │
                    │  ┌──────────────────────────┐  │
                    │  │  Agent Status (live)     │  │
                    │  │  Message Flow Graph      │  │
                    │  │  Latency Heatmap         │  │
                    │  │  Token Usage Counters    │  │
                    │  │  Error Rate Panels       │  │
                    │  │  Conversation Replay     │  │
                    │  └──────────────────────────┘  │
                    └────────────────────────────────┘
```

### Tech Stack
- **Agent Runtime:** Each agent is a FastAPI service with LangGraph internally
- **Message Bus:** Redis Streams (lightweight, ordered, consumer groups) — RabbitMQ as alternative
- **Agent Protocol:** Standardized JSON message envelope (see below)
- **Event Collection:** Dedicated service consuming the event stream, writing to PostgreSQL + pushing to WebSocket
- **Console Frontend:** React (Vite) with WebSocket for real-time updates, D3.js or React Flow for the message flow graph
- **Tracing:** OpenTelemetry (distributed traces across agents via trace propagation in message headers)
- **Metrics:** Prometheus (per-agent metrics) → Grafana (operational dashboards)
- **Logging:** Structlog, JSON format, correlation via session_id + trace_id
- **Containerization:** Docker Compose for local dev, each agent is its own container

### Message Protocol

Every message between agents follows this envelope:

```json
{
  "message_id": "uuid-v4",
  "session_id": "uuid-v4",
  "trace_id": "otel-trace-id",
  "span_id": "otel-span-id",
  "from_agent": "researcher-agent",
  "to_agent": "analyst-agent",
  "message_type": "task_request",
  "payload": {
    "task": "analyze_findings",
    "data": { ... }
  },
  "metadata": {
    "timestamp": "2026-03-25T10:30:00Z",
    "priority": "normal",
    "ttl_seconds": 300,
    "retry_count": 0
  }
}
```

**Message Types:**
- `task_request` — ask an agent to do something
- `task_response` — agent returns results
- `event` — agent publishes an observation (for console)
- `heartbeat` — periodic health signal
- `error` — agent reports a failure

### Agent Event Schema (for Console)

Each agent emits structured events to a dedicated `events` stream:

```json
{
  "event_type": "llm_call | tool_use | decision | error | status_change",
  "agent_id": "researcher-agent",
  "session_id": "uuid",
  "timestamp": "2026-03-25T10:30:01Z",
  "data": {
    "model": "gpt-4o",
    "prompt_tokens": 1200,
    "completion_tokens": 350,
    "latency_ms": 2100,
    "tool_name": "web_search",
    "decision": "Need more data on competitor pricing, routing to analyst",
    "error_message": null
  }
}
```

### Agent Definitions

| Agent | Service Port | Role | Scales? |
|-------|-------------|------|---------|
| **Coordinator** | 8000 | Receives user query, decomposes, routes to specialists, aggregates results | Single instance |
| **Researcher** | 8001 | Web search, document retrieval, data gathering | Horizontally (multiple instances) |
| **Analyst** | 8002 | Data analysis, pattern recognition, comparison | Horizontally |
| **Writer** | 8003 | Produces final structured output from analyzed data | Single instance |
| **Event Collector** | 8010 | Consumes all events, stores in Postgres, pushes to WebSocket | Single instance |

### Detailed Phase Plan

#### Phase 1: Agent Infrastructure & Message Bus (Days 1-7)
- [ ] Set up project monorepo structure
- [ ] Docker Compose: Redis, PostgreSQL, Prometheus, Grafana
- [ ] Define message envelope schema (Pydantic models)
- [ ] Build `AgentBase` class:
  - FastAPI app with `/health`, `/invoke`, `/status` endpoints
  - Redis Streams consumer (listens on agent-specific stream)
  - Redis Streams producer (sends to target agent's stream)
  - Event emitter (publishes to `events` stream)
  - OpenTelemetry instrumentation (trace context propagation in messages)
  - Prometheus metrics (messages_processed, latency_histogram, error_counter)
- [ ] Implement message routing: Coordinator publishes to specific agent streams
- [ ] Health check aggregator: polls all agent `/health` endpoints
- [ ] Unit tests for AgentBase, message serialization, routing

#### Phase 2: Implement Agent Services (Days 8-14)
- [ ] **Coordinator Agent:**
  - Receives user query via HTTP `POST /query`
  - Uses LLM to decompose query into sub-tasks
  - Routes sub-tasks to appropriate specialist agents via message bus
  - Collects responses, determines if follow-up routing is needed
  - Returns final aggregated result
- [ ] **Researcher Agent:**
  - Consumes `task_request` messages
  - Has tools: web search (SerpAPI), URL scraper, Wikipedia
  - Emits events: every LLM call, every tool use
  - Returns findings as `task_response`
- [ ] **Analyst Agent:**
  - Consumes findings from researcher
  - Structures data, identifies patterns, produces analysis
  - Emits decision events ("comparing 3 sources", "found contradiction")
- [ ] **Writer Agent:**
  - Takes analysis, produces formatted output
  - Handles different output formats (report, bullet points, table)
- [ ] Integration test: full query flow through all 4 agents via message bus

#### Phase 3: OpenTelemetry & Observability Backend (Days 15-21)
- [ ] OpenTelemetry setup:
  - Each agent creates spans for: message receipt, LLM call, tool use, message send
  - Trace context propagated in message headers (`trace_id`, `span_id`)
  - Traces exported to Jaeger (Docker) for backend trace visualization
- [ ] **Event Collector Service:**
  - Consumes from `events` Redis stream (consumer group)
  - Writes events to PostgreSQL (time-series friendly schema)
  - Maintains WebSocket connections to console clients
  - Broadcasts events in real-time to connected consoles
- [ ] Prometheus metrics per agent:
  - `agent_messages_processed_total` (counter)
  - `agent_message_latency_seconds` (histogram)
  - `agent_llm_tokens_total` (counter, labels: prompt/completion)
  - `agent_llm_latency_seconds` (histogram)
  - `agent_errors_total` (counter)
  - `agent_status` (gauge: 0=down, 1=healthy)
- [ ] Grafana dashboard:
  - Agent health status panel
  - Message throughput over time
  - LLM token usage by agent
  - Error rates by agent
  - Latency percentiles by agent

#### Phase 4: Real-Time Observability Console (Days 22-30)
- [ ] **React app (Vite + TypeScript):**
  - WebSocket connection to Event Collector
  - Real-time event stream display
- [ ] **Agent Status Panel:**
  - Cards for each agent showing: status (healthy/unhealthy/busy), current task, uptime
  - Live updates via heartbeat events
- [ ] **Message Flow Graph:**
  - React Flow or D3.js directed graph
  - Nodes = agents, edges = messages
  - Edges animate when messages flow
  - Edge labels show message type and latency
  - Click on edge to see message payload
- [ ] **Session Replay:**
  - Select a session_id from dropdown
  - Timeline view showing every event in chronological order
  - Expandable cards: see LLM prompts/responses, tool inputs/outputs, agent decisions
  - "Why did it do that?" — click any decision to see the full context
- [ ] **Metrics Panels:**
  - Token usage (bar chart by agent, cumulative line chart)
  - Latency heatmap (agents × time)
  - Error log (filterable table)

#### Phase 5: Polish, Resilience & Demo (Days 31-36)
- [ ] Resilience patterns:
  - Message TTL: expired messages are dead-lettered, not processed
  - Retry with backoff: if agent fails, message re-queued with incremented retry_count
  - Circuit breaker: if agent error rate >50%, Coordinator stops routing to it, uses fallback
- [ ] Graceful degradation demo:
  - Kill an agent mid-session
  - Console shows agent going red
  - Coordinator detects failure, re-routes or produces partial result
  - Show the full trace in Jaeger + the event replay in console
- [ ] Demo scenario:
  - Query: "What are the latest developments in quantum computing and how might they affect cybersecurity?"
  - Show console in real-time: agents lighting up, messages flowing, decisions being made
  - Show Jaeger trace: distributed trace across 4 services
  - Show Grafana: operational metrics during the query
- [ ] Record demo video
- [ ] Write comprehensive README

### Key Files / Directory Structure
```
agent-mesh/
├── README.md
├── docker-compose.yml
├── proto/
│   └── messages.py                 # Pydantic message schemas (shared)
├── agent-base/
│   ├── base.py                     # AgentBase class
│   ├── messaging.py                # Redis Streams producer/consumer
│   ├── events.py                   # Event emitter
│   ├── tracing.py                  # OpenTelemetry setup
│   └── metrics.py                  # Prometheus metrics
├── agents/
│   ├── coordinator/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── logic.py
│   ├── researcher/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── tools.py
│   ├── analyst/
│   │   ├── Dockerfile
│   │   ├── main.py
│   │   └── logic.py
│   └── writer/
│       ├── Dockerfile
│       ├── main.py
│       └── logic.py
├── event-collector/
│   ├── Dockerfile
│   ├── main.py                     # FastAPI + WebSocket
│   ├── consumer.py                 # Redis stream consumer
│   └── models.py                   # PostgreSQL models
├── console/
│   ├── package.json
│   ├── src/
│   │   ├── App.tsx
│   │   ├── components/
│   │   │   ├── AgentStatusPanel.tsx
│   │   │   ├── MessageFlowGraph.tsx
│   │   │   ├── SessionReplay.tsx
│   │   │   ├── MetricsPanels.tsx
│   │   │   └── EventStream.tsx
│   │   ├── hooks/
│   │   │   └── useWebSocket.ts
│   │   └── types/
│   │       └── events.ts
├── prometheus/
│   └── prometheus.yml
├── grafana/
│   └── dashboards/
│       └── agent-mesh.json
└── tests/
    ├── test_agent_base.py
    ├── test_messaging.py
    ├── test_coordinator.py
    └── test_integration.py
```

### Success Criteria
- [ ] 4 agents running as independent Docker containers, communicating via Redis Streams
- [ ] Full distributed trace visible in Jaeger spanning all agents
- [ ] Console shows real-time agent status, message flow graph, and session replay
- [ ] Killing an agent mid-session triggers graceful degradation (visible in console)
- [ ] Grafana shows per-agent operational metrics
- [ ] End-to-end query completes in <90 seconds with full observability
