# Quickstart: Agent Layer (LangGraph State Machine)

## Prerequisites

- Python 3.9+
- Running Tool Registry Service (see registry quickstart)
- Google GenAI API key (`GOOGLE_API_KEY` env var)
- Optional: Langfuse instance for tracing

## 1. Install Dependencies

```bash
cd /path/to/researchSwarm
pip install -e ".[dev]"
```

The `pyproject.toml` includes the agent layer dependencies:
- `langgraph>=0.6.10,<0.7` (LangGraph 1.1+ when published on PyPI)
- `langchain-core>=0.3`
- `langchain-google-genai>=2.0`
- `langfuse>=2.0`

## 2. Configure Environment

```bash
cp .env.example .env
```

Add or update these variables in `.env`:

```env
# LLM Provider
GOOGLE_API_KEY=your-google-genai-api-key
LLM_MODEL=gemini-3.1-flash-live-preview
LLM_TEMPERATURE=0.1
LLM_TIMEOUT_SECONDS=30
LLM_MAX_RETRIES=3

# Agent Config
MAX_ITERATIONS=3
GRAPH_TIMEOUT_SECONDS=60

# Tool Registry
REGISTRY_BASE_URL=http://localhost:8000

# Langfuse (optional)
LANGFUSE_ENABLED=true
LANGFUSE_HOST=http://localhost:3000
LANGFUSE_PUBLIC_KEY=your-public-key
LANGFUSE_SECRET_KEY=your-secret-key
```

## 3. Start the Tool Registry

```bash
docker compose up -d
python -m registry
```

Seed tools if not already done:

```bash
python -c "import asyncio; from registry.seed import seed_tools; asyncio.run(seed_tools())"
```

## 4. Run a Research Query

```python
import asyncio
import uuid

from agents.graph import build_research_graph, default_graph_context, invoke_research_graph


async def main():
    graph = build_research_graph()
    context = default_graph_context()
    try:
        result = await invoke_research_graph(
            graph,
            {
                "query": "What are the latest advances in transformer architectures for NLP?",
                "constraints": {"sources": ["arxiv"], "date_range": "2024-2026"},
                "accumulated_context": [],
                "trace_id": str(uuid.uuid4()),
                "session_id": "quickstart-session-1",
                "max_iterations": 3,
            },
            context,
        )
    finally:
        await context["registry"].aclose()

    print("=== Synthesis ===")
    print(result["synthesis"])
    print(f"\n=== Stats ===")
    print(f"Iterations: {result['iteration_count']}")
    print(f"Sources: {len(result['sources'])}")
    print(f"Critique passed: {result['critique_pass']}")
    print(f"Token usage: {result['token_usage']}")


asyncio.run(main())
```

## 5. Run Tests

```bash
# Unit tests for agent nodes
pytest tests/unit/test_researcher_node.py tests/unit/test_analyst_node.py \
       tests/unit/test_critic_node.py tests/unit/test_synthesizer_node.py -v

# Contract tests for state schema and node contracts
pytest tests/contract/test_state_schema_contract.py \
       tests/contract/test_researcher_contract.py \
       tests/contract/test_analyst_contract.py \
       tests/contract/test_critic_contract.py \
       tests/contract/test_synthesizer_contract.py -v

# Integration test for full graph flow
pytest tests/integration/test_research_graph_flow.py -v

# All tests
pytest -v
```

## 6. Graph Visualization

```python
from agents.graph import build_research_graph

graph = build_research_graph()
# Optional dependency: pip install grandalf
print(graph.get_graph().draw_ascii())
```

Expected output:

```text
        +-----------+
        |  START    |
        +-----------+
              |
              v
       +------------+
       | Researcher |<--------+
       +------------+         |
              |                |
              v                |
        +-----------+          |
        |  Analyst  |          |
        +-----------+          |
              |                |
              v                |
        +-----------+          |
        |  Critic   |----------+
        +-----------+   (loop-back if
              |          critique fails)
              v
       +-------------+
       | Synthesizer |
       +-------------+
              |
              v
        +-----------+
        |    END    |
        +-----------+
```

## Project Structure

```text
agents/
├── __init__.py
├── state.py             # ResearchState TypedDict
├── graph.py             # build_research_graph() → compiled StateGraph
├── config.py            # AgentConfig (pydantic-settings)
├── tracing.py           # Langfuse + structlog setup
├── response_models.py   # Pydantic models for with_structured_output()
├── nodes/
│   ├── __init__.py
│   ├── researcher.py
│   ├── analyst.py
│   ├── critic.py
│   └── synthesizer.py
├── tools/
│   ├── __init__.py
│   └── registry_client.py
└── prompts/
    ├── __init__.py
    ├── researcher.py
    ├── analyst.py
    ├── critic.py
    └── synthesizer.py
```
