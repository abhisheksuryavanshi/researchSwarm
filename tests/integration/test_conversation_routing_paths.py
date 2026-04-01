import uuid
from unittest.mock import MagicMock

import pytest

from agents.context import GraphContext
from conversation.config import ConversationSettings
from conversation.coordinator import ConversationCoordinator
from conversation.models import IntentResult


@pytest.mark.asyncio
async def test_reformat_uses_light_graph(monkeypatch, mock_registry_client):
    settings = ConversationSettings.model_validate(
        {
            "database_url": "mysql+aiomysql://x",
            "redis_url": "redis://x",
        }
    )

    class MemMysql:
        def __init__(self):
            self.sessions = {}
            self.turns = []
            self.snaps = []

        async def create_session(self, owner):
            sid = str(uuid.uuid4())
            row = MagicMock(id=sid, owner_principal_id=owner)
            self.sessions[sid] = row
            return row

        async def get_session_for_owner(self, sid, owner):
            r = self.sessions.get(sid)
            if not r or r.owner_principal_id != owner:
                return None
            return r

        async def latest_snapshot(self, sid):
            s = MagicMock()
            s.state_blob = {"synthesis": "prior", "constraints": {}}
            s.after_turn_index = 0
            return s

        async def next_turn_index(self, sid):
            return 0

        async def append_turn(self, *a, **k):
            t = MagicMock()
            self.turns.append(t)
            return t

        async def find_turn_by_idempotency(self, *a):
            return None

        async def get_turn(self, *a):
            return None

        async def save_snapshot(self, *a, **k):
            self.snaps.append(a)
            return MagicMock()

        async def dispose(self):
            pass

    class MemRedis:
        def __init__(self):
            self._locks: dict[str, str] = {}

        async def ping(self):
            return True

        async def acquire_turn_lock(self, sid):
            if sid in self._locks:
                return None
            self._locks[sid] = "t"
            return "t"

        async def release_turn_lock(self, sid, tok):
            if self._locks.get(sid) == tok:
                del self._locks[sid]

        async def get_working_doc(self, sid):
            return {"state_blob": {"synthesis": "prior"}}

        async def set_working_doc(self, *a):
            pass

    light_called = []

    async def fake_light(compiled, inp, ctx):
        light_called.append(True)
        return {
            "query": inp["query"],
            "constraints": inp.get("constraints") or {},
            "accumulated_context": list(inp.get("accumulated_context") or []),
            "messages": list(inp.get("messages") or []),
            "synthesis": "light-out",
            "raw_findings": [],
            "sources": [],
            "analysis": "",
            "critique": "",
            "critique_pass": True,
            "gaps": [],
            "iteration_count": 0,
            "token_usage": {},
            "errors": [],
        }

    async def fake_full(*a, **k):
        raise AssertionError("full graph should not run for reformat")

    monkeypatch.setattr(
        "conversation.coordinator.invoke_light_synthesizer_graph",
        fake_light,
    )
    monkeypatch.setattr(
        "conversation.coordinator.invoke_research_graph_continuation",
        fake_full,
    )

    class FixedIntent:
        async def classify(self, user_message, has_prior_synthesis=False):
            return IntentResult.model_validate(
                {"intent": "reformat", "confidence": 0.99},
            )

    cfg = __import__("agents.config", fromlist=["AgentConfig"]).AgentConfig.model_validate(
        {"langfuse_enabled": False}
    )
    ctx: GraphContext = {
        "llm": MagicMock(),
        "registry": mock_registry_client,
        "agent_config": cfg,
    }

    coord = ConversationCoordinator(
        settings,
        MemMysql(),  # type: ignore[arg-type]
        MemRedis(),  # type: ignore[arg-type]
        ctx,
        full_graph_compiled=object(),
        light_graph_compiled=object(),
        intent_classifier=FixedIntent(),
    )
    sid = await coord.create_session_row("o")
    await coord.run_turn(
        owner_principal_id="o",
        session_id=sid,
        message="Shorter bullets please",
        trace_id=str(uuid.uuid4()),
    )
    assert light_called == [True]
