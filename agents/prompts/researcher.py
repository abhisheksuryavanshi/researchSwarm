SYSTEM_PROMPT = """You are the Researcher agent. Your job is to pick the best external tools \
from the registry search results (by tool_id) to answer the user's question. Select 1–3 tools. \
Do not analyze or synthesize — only choose tools. Respond using the structured schema."""

USER_PROMPT = """Research query: {query}
Constraints (JSON): {constraints}
Registry search results (tool_id, name, description, capabilities):
{search_summary}

Choose 1–3 tool_ids most likely to gather relevant raw data."""

REFINEMENT_PROMPT = """This is iteration {iteration_count} (>0). Address these gaps from the Critic:
{gaps}

Original query: {query}
Constraints: {constraints}
Registry search results:
{search_summary}

Select 1–3 tools (can differ from prior pass) to close the gaps."""
