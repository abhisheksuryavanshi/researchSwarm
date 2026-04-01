# Quickstart: Dynamic Tool Binding

## Prerequisites

- Python 3.9+
- Running Tool Registry Service (see registry quickstart)
- Agent Layer installed (see `specs/002-agent-layer/quickstart.md`)
- Google GenAI API key (`GOOGLE_API_KEY` env var)

## 1. Install Dependencies

No new dependencies required. The Dynamic Tool Binding feature uses existing packages:
- `langchain-core` (StructuredTool, BaseTool)
- `httpx` (via RegistryClient)
- `pydantic` (create_model for dynamic schemas)

```bash
cd /path/to/researchSwarm
pip install -e ".[dev]"
```

## 2. Configure Environment

Add or update these variables in `.env`:

```env
# Tool Discovery Config (new)
TOOL_INVOCATION_TIMEOUT_SECONDS=30    # Per-tool HTTP call timeout
MAX_TOOL_FALLBACK_ATTEMPTS=3          # Max tools to try (primary + fallbacks)

# Existing (unchanged)
GOOGLE_API_KEY=your-google-genai-api-key
REGISTRY_BASE_URL=http://localhost:8000
```

## 3. Using ToolDiscoveryTool Directly

```python
import asyncio

from agents.config import AgentConfig
from agents.graph import create_default_llm
from agents.tools.discovery import ToolDiscoveryTool
from agents.tools.registry_client import RegistryClient


async def main():
    config = AgentConfig()
    registry = RegistryClient(config)
    llm = create_default_llm(config)

    tool = ToolDiscoveryTool(registry=registry, llm=llm, config=config)

    try:
        result = await tool.ainvoke({
            "capability": "web_search",
            "query": "latest advances in transformer architectures",
            "constraints": {"sources": ["arxiv"]},
            "gaps": [],
            "agent_id": "researcher",
            "session_id": "demo-session-1",
        })
        print(result)  # JSON string of ToolDiscoveryResult
    finally:
        await registry.aclose()


asyncio.run(main())
```

## 4. Using via the Research Graph (Recommended)

The Researcher node automatically uses the ToolDiscoveryTool internally. No changes to graph invocation:

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
                "query": "Compare AI strategies of Microsoft and Google based on 10-K filings",
                "constraints": {"sources": ["sec_filings"]},
                "trace_id": str(uuid.uuid4()),
                "session_id": "quickstart-session",
            },
            context,
        )
    finally:
        await context["registry"].aclose()

    print(f"Synthesis: {result['synthesis'][:200]}...")
    print(f"Sources: {len(result['sources'])}")
    print(f"Errors: {result['errors']}")


asyncio.run(main())
```

## 5. Run Tests

```bash
# Unit tests for ToolDiscoveryTool
pytest tests/unit/test_tool_discovery.py -v

# Unit tests for DynamicTool builder
pytest tests/unit/test_dynamic_tool_builder.py -v

# Contract tests
pytest tests/contract/test_tool_discovery_contract.py -v

# Integration test for full search→select→bind→invoke flow
pytest tests/integration/test_tool_discovery_flow.py -v

# Verify existing tests still pass after Researcher refactoring
pytest tests/unit/test_researcher_node.py -v
pytest tests/integration/test_research_graph_flow.py -v

# All tests
pytest -v
```

## Project Structure (new files)

```text
agents/tools/
├── __init__.py              # Existing
├── registry_client.py       # Existing — unchanged
└── discovery.py             # NEW: ToolDiscoveryTool, build_dynamic_tool, build_tool_payload

tests/
├── unit/
│   ├── test_tool_discovery.py       # NEW
│   └── test_dynamic_tool_builder.py # NEW
├── contract/
│   └── test_tool_discovery_contract.py  # NEW
└── integration/
    └── test_tool_discovery_flow.py       # NEW
```
