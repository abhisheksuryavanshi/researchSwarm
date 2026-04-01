from __future__ import annotations

from typing import TYPE_CHECKING, NotRequired, TypedDict

from langchain_core.language_models import BaseChatModel

from agents.config import AgentConfig
from agents.tools.registry_client import RegistryClient

if TYPE_CHECKING:
    from agents.tools.discovery import ToolDiscoveryTool


class GraphContext(TypedDict):
    llm: BaseChatModel
    registry: RegistryClient
    agent_config: AgentConfig
    tool_discovery: NotRequired["ToolDiscoveryTool"]
