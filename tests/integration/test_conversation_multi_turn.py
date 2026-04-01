import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from agents.context import GraphContext
from conversation.config import ConversationSettings
from conversation.coordinator import ConversationCoordinator
from conversation.intent import IntentClassifier


@pytest.mark.asyncio
async def test_coordinator_two_turns_persist_snapshot(monkeypatch, mock_registry_client):
    """Two turns: second invocation receives merged snapshot constraints (MySQL + merge)."""
    settings = ConversationSettings.model_validate(
        {
            "database_url": "mysql+aiomysql://root:root@localhost:3306/researchswarm_test",
            "redis_url": "redis://localhost:6379/15",
        }
    )

    class MemMysql:
        def __init__(self):
            self.sessions: dict = {}
            self.turns: list = []
            self.snaps: list = []

        async def create_session(self, owner):
            sid = str(uuid.uuid4())
            row = MagicMock()
            row.id = sid
            row.owner_principal_id = owner
            self.sessions[sid] = row
            return row

        async def get_session_for_owner(self, sid, owner):
            r = self.sessions.get(sid)
            if r is None or r.owner_principal_id != owner:
                return None
            return r

        async def latest_snapshot(self, sid):
            snaps = [x for x in self.snaps if x.session_id == sid]
            if not snaps:
                return None
            return max(snaps, key=lambda x: x.after_turn_index)

        async def next_turn_index(self, sid):
            idx = [t.turn_index for t in self.turns if t.session_id == sid]
            return (max(idx) + 1) if idx else 0

        async def append_turn(self, session_id, turn_index, role, content, **kw):
            t = MagicMock()
            t.session_id = session_id
            t.turn_index = turn_index
            t.role = role
            t.content = content
            t.intent = kw.get("intent")
            t.intent_confidence = kw.get("intent_confidence")
            t.trace_id = kw.get("trace_id")
            t.idempotency_key = kw.get("idempotency_key")
            self.turns.append(t)
            return t

        async def find_turn_by_idempotency(self, session_id, key):
            for t in self.turns:
                if t.session_id == session_id and t.idempotency_key == key:
                    return t
            return None

        async def get_turn(self, session_id, turn_index):
            for t in self.turns:
                if t.session_id == session_id and t.turn_index == turn_index:
                    return t
            return None

        async def save_snapshot(self, session_id, after_turn_index, state_blob):
            s = MagicMock()
            s.session_id = session_id
            s.after_turn_index = after_turn_index
            s.state_blob = state_blob
            self.snaps.append(s)
            return s

        async def dispose(self):
            pass

    class MemRedis:
        def __init__(self):
            self._client = True
            self._locks = {}
            self._docs = {}

        async def ping(self):
            return True

        async def connect(self):
            pass

        async def close(self):
            pass

        async def acquire_turn_lock(self, sid):
            if sid in self._locks:
                return None
            tok = "t1"
            self._locks[sid] = tok
            return tok

        async def release_turn_lock(self, sid, tok):
            if self._locks.get(sid) == tok:
                del self._locks[sid]

        async def get_working_doc(self, sid):
            return self._docs.get(sid)

        async def set_working_doc(self, sid, doc):
            self._docs[sid] = doc

    captured: list[dict] = []

    async def fake_full(compiled, inp, ctx):
        captured.append(dict(inp))
        return {
            "query": inp["query"],
            "constraints": inp.get("constraints") or {},
            "accumulated_context": inp.get("accumulated_context") or [],
            "messages": inp.get("messages") or [],
            "synthesis": f"Answer:{inp['query']}",
            "raw_findings": [],
            "sources": [],
            "analysis": "",
            "critique": "",
            "critique_pass": True,
            "gaps": [],
            "iteration_count": 1,
            "token_usage": {},
            "errors": [],
        }

    monkeypatch.setattr(
        "conversation.coordinator.invoke_research_graph_continuation",
        fake_full,
    )
    monkeypatch.setattr(
        "conversation.coordinator.invoke_light_synthesizer_graph",
        AsyncMock(side_effect=AssertionError("light path not used")),
    )

    cfg = __import__("agents.config", fromlist=["AgentConfig"]).AgentConfig.model_validate(
        {"langfuse_enabled": False}
    )
    ctx: GraphContext = {
        "llm": MagicMock(),
        "registry": mock_registry_client,
        "agent_config": cfg,
    }

    mysql = MemMysql()
    redis = MemRedis()
    coord = ConversationCoordinator(
        settings,
        mysql,  # type: ignore[arg-type]
        redis,  # type: ignore[arg-type]
        ctx,
        full_graph_compiled=object(),
        light_graph_compiled=None,
        intent_classifier=IntentClassifier(None),
    )

    sid = await coord.create_session_row("owner-a")
    tid1 = str(uuid.uuid4())
    await coord.run_turn(
        owner_principal_id="owner-a",
        session_id=sid,
        message="First question",
        trace_id=tid1,
    )
    tid2 = str(uuid.uuid4())
    await coord.run_turn(
        owner_principal_id="owner-a",
        session_id=sid,
        message="Follow up",
        trace_id=tid2,
    )

    assert len(captured) == 2
    assert captured[1]["session_id"] == sid
    acc = captured[1].get("accumulated_context") or []
    assert any("Answer:First question" in str(x) for x in acc)
