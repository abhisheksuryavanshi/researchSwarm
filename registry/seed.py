"""Idempotent seed script for 7 tools. Run as: python -m registry.seed"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from registry.config import settings
from registry.database import async_session_factory, engine
from registry.models import Tool, ToolCapability

logger = structlog.get_logger()

# MediaWiki Action API: on-wiki search resolves natural language to an article, then returns
# extract + URL. exintro=0 allows TextExtracts to include content beyond the first section
# where supported; the agent layer may also merge a full plain-text parse (see AgentConfig).
WIKIPEDIA_LOOKUP_TOOL: dict = {
    "tool_id": "wikipedia-lookup-v1",
    "name": "Wikipedia Lookup",
    "description": (
        "Searches English Wikipedia for the user question or topic and returns the top "
        "matching article extract, page URL, and (downstream) extended plain text from the "
        "full article when enrichment is enabled."
    ),
    "capabilities": ["general_knowledge", "encyclopedia"],
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "default": "query"},
            "format": {"type": "string", "default": "json"},
            "generator": {"type": "string", "default": "search"},
            "gsrsearch": {
                "type": "string",
                "description": (
                    "Natural language question or keywords (filled from the research query)"
                ),
            },
            "gsrlimit": {"type": "integer", "default": 8},
            "gsrnamespace": {"type": "integer", "default": 0},
            "prop": {"type": "string", "default": "extracts|info"},
            "inprop": {"type": "string", "default": "url"},
            "exintro": {"type": "integer", "default": 0},
            "explaintext": {"type": "integer", "default": 1},
        },
        "required": ["gsrsearch"],
    },
    "output_schema": {
        "type": "object",
        "properties": {
            "batchcomplete": {"type": "string"},
            "continue": {"type": "object"},
            "query": {
                "type": "object",
                "properties": {
                    "pages": {"type": "object"},
                },
            },
        },
    },
    "endpoint": "https://en.wikipedia.org/w/api.php",
    "version": "1.0.0",
    "method": "GET",
}

SEED_TOOLS = [
    {
        "tool_id": "serp-web-search-v1",
        "name": "Web Search",
        "description": (
            "Performs web searches using the DuckDuckGo Instant Answer API, returning "
            "abstracts, related topics, and knowledge snippets from across the web."
        ),
        "capabilities": ["web_search", "general_knowledge"],
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Search query string"},
                "format": {"type": "string", "default": "json"},
                "no_html": {"type": "integer", "default": 1},
                "skip_disambig": {"type": "integer", "default": 1},
            },
            "required": ["q"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "AbstractText": {"type": "string"},
                "AbstractSource": {"type": "string"},
                "AbstractURL": {"type": "string"},
                "Heading": {"type": "string"},
                "Answer": {"type": "string"},
                "RelatedTopics": {"type": "array", "items": {"type": "object"}},
            },
        },
        "endpoint": "https://api.duckduckgo.com/",
        "version": "1.0.0",
        "method": "GET",
    },
    {
        "tool_id": "arxiv-paper-search-v1",
        "name": "Academic Paper Search",
        "description": (
            "Searches academic papers via the Semantic Scholar API by topic, author, or "
            "keyword, returning titles, abstracts, authors, and publication metadata. "
            "Covers ArXiv and major academic publishers."
        ),
        "capabilities": ["academic_papers", "arxiv"],
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for papers"},
                "limit": {"type": "integer", "default": 5},
                "fields": {
                    "type": "string",
                    "default": "title,abstract,url,year,authors",
                },
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "total": {"type": "integer"},
                "data": {"type": "array", "items": {"type": "object"}},
            },
        },
        "endpoint": "https://api.semanticscholar.org/graph/v1/paper/search",
        "version": "1.0.0",
        "method": "GET",
    },
    {
        "tool_id": "github-search-v1",
        "name": "GitHub Repository Search",
        "description": (
            "Searches GitHub repositories via the public GitHub API by name, topic, or "
            "language, returning repository metadata including stars, forks, and descriptions."
        ),
        "capabilities": ["code_search", "github", "repositories"],
        "input_schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string", "description": "Search query"},
                "per_page": {
                    "type": "integer",
                    "description": "Number of results per page",
                    "default": 5,
                },
            },
            "required": ["q"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "total_count": {"type": "integer"},
                "items": {"type": "array", "items": {"type": "object"}},
            },
        },
        "endpoint": "https://api.github.com/search/repositories",
        "version": "1.0.0",
        "method": "GET",
    },
    WIKIPEDIA_LOOKUP_TOOL,
    {
        "tool_id": "calculator-v1",
        "name": "Calculator",
        "description": (
            "Evaluates mathematical expressions using the mathjs API. Supports "
            "arithmetic, algebra, trigonometry, and basic statistics."
        ),
        "capabilities": ["math", "calculation"],
        "input_schema": {
            "type": "object",
            "properties": {
                "expr": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate (e.g. '2+3', 'sqrt(144)')",
                },
            },
            "required": ["expr"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "number"},
            },
        },
        "endpoint": "https://api.mathjs.org/v4/",
        "version": "1.0.0",
        "method": "GET",
    },
    {
        "tool_id": "url-scraper-v1",
        "name": "URL Scraper",
        "description": (
            "Scrapes web pages at specified URLs and extracts clean text content, "
            "removing HTML tags and scripts for content extraction. "
            "Currently inactive — requires a dedicated scraping microservice."
        ),
        "capabilities": ["web_scraping", "content_extraction"],
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "URL to scrape"},
                "extract_links": {"type": "boolean", "default": False},
            },
            "required": ["url"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "content": {"type": "string"},
                "links": {"type": "array", "items": {"type": "string"}},
            },
        },
        "endpoint": "http://tools:8001/scraper",
        "version": "1.0.0",
        "method": "POST",
        "health_check": "/health",
        "status": "inactive",
    },
    {
        "tool_id": "sec-filing-parser-v1",
        "name": "SEC Filing Parser",
        "description": (
            "Parses SEC EDGAR filings and extracts structured financial data including "
            "income statements, balance sheets, and cash flow statements. "
            "Currently inactive — requires a dedicated SEC parsing microservice."
        ),
        "capabilities": ["financial_data", "sec_filings", "document_parsing"],
        "input_schema": {
            "type": "object",
            "properties": {
                "ticker": {"type": "string", "description": "Stock ticker symbol"},
                "filing_type": {"type": "string", "enum": ["10-K", "10-Q", "8-K"]},
            },
            "required": ["ticker"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "sections": {"type": "array", "items": {"type": "object"}},
                "financials": {"type": "object"},
            },
        },
        "endpoint": "http://tools:8001/sec-parser",
        "version": "1.0.0",
        "method": "POST",
        "health_check": "/health",
        "status": "inactive",
    },
]


async def _sync_existing_tools(session: AsyncSession) -> None:
    """Update existing tool rows to match current seed definitions (idempotent).

    Ensures endpoint, method, schemas, description, and status stay in sync
    with the canonical SEED_TOOLS list even for rows that were inserted by an
    earlier version of the seed script.
    """
    now = datetime.now(timezone.utc)
    for tool_data in SEED_TOOLS:
        res = await session.execute(
            select(Tool).where(Tool.tool_id == tool_data["tool_id"])
        )
        row = res.scalar_one_or_none()
        if row is None:
            continue
        row.name = tool_data["name"]
        row.description = tool_data["description"]
        row.endpoint = tool_data["endpoint"]
        row.method = tool_data.get("method", "POST")
        row.input_schema = tool_data["input_schema"]
        row.output_schema = tool_data["output_schema"]
        row.health_check = tool_data.get("health_check")
        if "status" in tool_data:
            row.status = tool_data["status"]
        elif row.status == "inactive":
            row.status = "active"
        row.updated_at = now


async def seed(session: Optional[AsyncSession] = None) -> int:
    """
    Idempotently populate the database with a predefined set of fundamental tools.
    Returns the number of freshly inserted tools.
    """
    own_session = session is None

    if own_session:
        session = async_session_factory()

    try:
        count = 0
        for tool_data in SEED_TOOLS:
            existing = await session.execute(
                select(Tool).where(Tool.tool_id == tool_data["tool_id"])
            )
            if existing.scalar_one_or_none() is not None:
                continue

            now = datetime.now(timezone.utc)

            tool = Tool(
                tool_id=tool_data["tool_id"],
                name=tool_data["name"],
                description=tool_data["description"],
                version=tool_data["version"],
                endpoint=tool_data["endpoint"],
                method=tool_data.get("method", "POST"),
                input_schema=tool_data["input_schema"],
                output_schema=tool_data["output_schema"],
                health_check=tool_data.get("health_check"),
                created_at=now,
                updated_at=now,
            )
            for cap in tool_data["capabilities"]:
                tool.capabilities.append(ToolCapability(capability=cap))

            session.add(tool)
            count += 1

        await _sync_existing_tools(session)
        await session.commit()
        return count
    except Exception:
        await session.rollback()
        raise
    finally:
        if own_session:
            await session.close()


async def main():
    """
    Execute the seed operation defensively via the command line interface.
    Automatically configures logging and orchestrates the database interactions safely.
    """
    from registry.middleware.logging import configure_logging

    configure_logging(settings.log_level, settings.log_directory)
    log = structlog.get_logger()

    await log.ainfo("seed_started")
    count = await seed()
    await log.ainfo("seed_completed", tools_created=count, total_seed_tools=len(SEED_TOOLS))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
