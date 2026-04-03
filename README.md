# researchSwarm

A multi-agent research system where specialized AI agents collaborate to answer complex research questions through dynamic tool discovery and conversational multi-turn sessions.

Agents don't carry a hardcoded tool list. At runtime, an agent queries a centralized **tool registry**, discovers the right capability, binds it dynamically, and uses it — all within a single research execution.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Operator Web UI  (React · Vite · Tailwind)             │
│  Chat  ·  Tool Catalog  ·  Stats / Health               │
└────────────────────────┬────────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼────────────────────────────────┐
│  Conversation Coordinator                                │
│  Intent classification · Query rewriting · Session state │
│  Redis (locks, cache)  ·  MySQL (sessions, snapshots)    │
└────────────────────────┬────────────────────────────────┘
                         │
┌────────────────────────▼────────────────────────────────┐
│  Research Engine  (LangGraph StateGraph)                  │
│                                                          │
│  Researcher → Analyst → Critic ─┬→ Synthesizer           │
│                                 └→ Researcher (loop)     │
│                                                          │
│  Tool Registry (FastAPI + MySQL)                         │
│  Search · Bind · Invoke · Usage Logging                  │
└──────────────────────┬──────────────────────────────────┘
                       │
              ┌────────▼────────┐
              │    Langfuse     │
              │   (Tracing)    │
              └────────────────┘
```

| Layer              | Technology                                                 |
|--------------------|------------------------------------------------------------|
| Orchestration      | LangGraph (state machine, conditional routing)             |
| LLM                | Groq / Google Gemini / Ollama via LangChain                |
| Tool Registry      | FastAPI + MySQL                                            |
| Session Store      | Redis (locks, working-set cache) + MySQL (durable state)   |
| Tracing            | Langfuse + Structlog (JSON, correlation IDs)               |
| Frontend           | React 18, Vite, Tailwind CSS 4                            |
| Language           | Python 3.9+                                                |

For a detailed breakdown of every component, see [Overview.md](Overview.md).

---

## Prerequisites

| Requirement         | Minimum                                                     |
|---------------------|-------------------------------------------------------------|
| **Python**          | 3.9+                                                        |
| **Docker**          | Recent version with Docker Compose V2 (`docker compose`)    |
| **Node.js / npm**   | Required only for the operator web UI                       |
| **Package manager** | [uv](https://github.com/astral-sh/uv) (recommended) or pip |

**LLM API key (at least one):**

| Provider  | Env Variable     | Model Example               |
|-----------|------------------|-----------------------------|
| Groq      | `GROQ_API_KEY`   | `llama-3.1-8b-instant`      |
| Google    | `GOOGLE_API_KEY` | `gemini-2.0-flash`          |
| Ollama    | *(local, no key)* | `llama3.1:8b`              |

Set the provider with `LLM_PROVIDER` in `.env` (`groq`, `google`, or `ollama`).

---

## How to Run

### Quick Start (setup.sh)

The `setup.sh` script handles everything: dependency checks, Docker services, Python packages, database migrations, seeding, and optionally starts the backend API and frontend dev server.

```bash
git clone <your-remote-url> researchSwarm
cd researchSwarm
chmod +x setup.sh
./setup.sh
```

**What `setup.sh` does:**
1. Verifies Docker, Docker Compose V2, and Python 3.9+ are installed
2. Creates `.env` from `.env.example` if it doesn't exist
3. Installs Python dependencies (`uv sync --extra dev` or `pip install -e ".[dev]"`)
4. Starts MySQL and Langfuse via Docker Compose
5. Starts a Redis container (`redis:7-alpine` on port 6379)
6. Runs Alembic database migrations (lenient mode for re-runs)
7. Seeds the tool registry with 7 tools
8. Starts the FastAPI backend on `http://127.0.0.1:8000` (Uvicorn, background)
9. Installs npm packages and starts the web UI on `http://127.0.0.1:5173` (Vite, background)

After setup completes:

| Service   | URL                                       |
|-----------|-------------------------------------------|
| API Docs  | http://127.0.0.1:8000/docs                |
| Web UI    | http://127.0.0.1:5173                     |
| Langfuse  | http://localhost:3000 (`admin@local.dev` / `localdev12`) |

**Important:** Edit `.env` to add your LLM API key before running research queries:
```bash
# For Groq (default provider):
GROQ_API_KEY=your-key-here

# Or for Google Gemini:
LLM_PROVIDER=google
GOOGLE_API_KEY=your-key-here
```

### Teardown (teardown.sh)

The `teardown.sh` script cleanly shuts down all services started by `setup.sh`.

```bash
./teardown.sh
```

This stops: Uvicorn (backend), Vite (frontend), Redis container, and Docker Compose services (MySQL, Langfuse).

**Options:**
```bash
./teardown.sh --volumes       # Also wipe MySQL data volume
./teardown.sh --remove-redis  # Also remove the Redis container
```

Your `.venv`, `.env`, and `logs/` directory are preserved across teardowns.

### Manual Setup (step-by-step)

If you prefer to run services individually:

```bash
# 1. Infrastructure
docker compose up -d mysql langfuse
docker run -d --name researchswarm-redis -p 6379:6379 redis:7-alpine

# 2. Python dependencies
uv sync --extra dev          # or: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

# 3. Environment
cp .env.example .env         # then edit .env with your API keys

# 4. Database
uv run python scripts/alembic_upgrade_lenient.py
uv run python -m registry.seed

# 5. Backend
uv run uvicorn registry.app:app --host 0.0.0.0 --port 8000 --reload

# 6. Frontend (separate terminal)
cd web && npm install && npm run dev -- --host 0.0.0.0 --port 5173
```

### Running Tests

```bash
uv run pytest                # or: .venv/bin/pytest
```

Integration tests require MySQL on `localhost:3306`. Override with `TEST_DATABASE_URL` if needed.

### Linting

```bash
uv run ruff check .
```
