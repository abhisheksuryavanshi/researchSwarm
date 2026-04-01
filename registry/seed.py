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

SEED_TOOLS = [
    {
        "tool_id": "serp-web-search-v1",
        "name": "SerpAPI Web Search",
        "description": (
            "Performs web searches using the SerpAPI service, returning organic results, "
            "knowledge graphs, and answer boxes from major search engines."
        ),
        "capabilities": ["web_search", "general_knowledge"],
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query string"},
                "num_results": {
                    "type": "integer",
                    "description": "Number of results",
                    "default": 10,
                },
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "results": {"type": "array", "items": {"type": "object"}},
                "total_results": {"type": "integer"},
            },
        },
        "endpoint": "http://tools:8001/serp",
        "version": "1.0.0",
        "method": "POST",
        "health_check": "/health",
    },
    {
        "tool_id": "arxiv-paper-search-v1",
        "name": "ArXiv Paper Search",
        "description": (
            "Searches the ArXiv academic paper repository for research papers by topic, "
            "author, or keyword, returning abstracts and metadata."
        ),
        "capabilities": ["academic_papers", "arxiv"],
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for papers"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "papers": {"type": "array", "items": {"type": "object"}},
            },
        },
        "endpoint": "http://tools:8001/arxiv",
        "version": "1.0.0",
        "method": "POST",
        "health_check": "/health",
    },
    {
        "tool_id": "github-search-v1",
        "name": "GitHub Repository Search",
        "description": (
            "Searches GitHub repositories by name, topic, or language, returning "
            "repository metadata including stars, forks, and descriptions."
        ),
        "capabilities": ["code_search", "github", "repositories"],
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query"},
                "language": {"type": "string", "description": "Filter by language"},
            },
            "required": ["query"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "repositories": {"type": "array", "items": {"type": "object"}},
            },
        },
        "endpoint": "http://tools:8001/github",
        "version": "1.0.0",
        "method": "POST",
        "health_check": "/health",
    },
    {
        "tool_id": "wikipedia-lookup-v1",
        "name": "Wikipedia Lookup",
        "description": (
            "Looks up Wikipedia articles by topic and returns article summaries, "
            "sections, and references for general knowledge queries."
        ),
        "capabilities": ["general_knowledge", "encyclopedia"],
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Topic to look up"},
            },
            "required": ["topic"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "url": {"type": "string"},
            },
        },
        "endpoint": "http://tools:8001/wikipedia",
        "version": "1.0.0",
        "method": "POST",
    },
    {
        "tool_id": "calculator-v1",
        "name": "Calculator",
        "description": (
            "Performs mathematical calculations including arithmetic, algebra, and "
            "basic statistical operations on numeric inputs."
        ),
        "capabilities": ["math", "calculation"],
        "input_schema": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Mathematical expression"},
            },
            "required": ["expression"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "number"},
            },
        },
        "endpoint": "http://tools:8001/calculator",
        "version": "1.0.0",
        "method": "POST",
    },
    {
        "tool_id": "url-scraper-v1",
        "name": "URL Scraper",
        "description": (
            "Scrapes web pages at specified URLs and extracts clean text content, "
            "removing HTML tags and scripts for content extraction."
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
    },
    {
        "tool_id": "sec-filing-parser-v1",
        "name": "SEC Filing Parser",
        "description": (
            "Parses SEC EDGAR filings and extracts structured financial data including "
            "income statements, balance sheets, and cash flow statements."
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
    },
]


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

    configure_logging(settings.log_level)
    log = structlog.get_logger()

    await log.ainfo("seed_started")
    count = await seed()
    await log.ainfo("seed_completed", tools_created=count, total_seed_tools=len(SEED_TOOLS))
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
