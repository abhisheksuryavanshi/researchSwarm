from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator, Optional

import structlog
import structlog.contextvars

from agents.context import GraphContext
from agents.graph import (
    invoke_light_synthesizer_graph,
    invoke_research_graph_continuation,
    invoke_research_graph_continuation_with_progress,
)
from conversation.authz import body_fingerprint
from conversation.config import ConversationSettings
from conversation.intent import IntentClassifier
from conversation.merge import (
    build_engine_input,
    merge_constraint_dicts,
    state_blob_from_graph_result,
)
from conversation.models import TurnResult
from conversation.persistence.mysql_store import MysqlSessionStore
from conversation.persistence.redis_store import RedisSessionStore
from conversation.rewrite import rewrite_with_context
from conversation.routing import plan_route


class StorageDegradedError(Exception):
    """FR-012: cannot process mutating turn (e.g. Redis lock tier down)."""


class IdempotencyConflictError(Exception):
    """Same Idempotency-Key with different body."""


class CoordinatorLockTimeoutError(Exception):
    """Could not acquire per-session lock in time."""


class SessionAccessDenied(Exception):
    """Unknown session or wrong owner (do not leak to client)."""


_CLARIFY_MESSAGE = (
    "Could you clarify whether you want a shorter summary, new sources, "
    "or a deeper refinement on the same topic?"
)


def _content_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        return str(content.get("text", ""))
    return str(content)


class ConversationCoordinator:
    def __init__(
        self,
        settings: ConversationSettings,
        mysql: MysqlSessionStore,
        redis: RedisSessionStore,
        graph_context: GraphContext,
        *,
        full_graph_compiled: Any,
        light_graph_compiled: Optional[Any] = None,
        intent_classifier: Optional[IntentClassifier] = None,
    ) -> None:
        self._settings = settings
        self._mysql = mysql
        self._redis = redis
        self._ctx = graph_context
        self._full = full_graph_compiled
        self._light = light_graph_compiled
        self._classifier = intent_classifier or IntentClassifier(
            None,
            confidence_threshold=settings.intent_confidence_threshold,
        )

    async def run_turn(
        self,
        *,
        owner_principal_id: str,
        session_id: str,
        message: str,
        trace_id: str,
        client_session_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> TurnResult:
        log = structlog.get_logger()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            session_id=session_id,
            trace_id=trace_id,
            agent_id="conversation_coordinator",
            client_session_id=client_session_id,
        )

        if not await self._redis.ping():
            await log.awarning("redis_unavailable", session_id=session_id)
            raise StorageDegradedError("redis unavailable for turn lock / working set")

        session = await self._mysql.get_session_for_owner(session_id, owner_principal_id)
        if session is None:
            structlog.contextvars.clear_contextvars()
            raise SessionAccessDenied("session not found")

        fp = body_fingerprint(message, client_session_id)

        token: Optional[str] = None
        try:
            for _ in range(200):
                token = await self._redis.acquire_turn_lock(session_id)
                if token:
                    break
                await asyncio.sleep(0.02)
            if not token:
                raise CoordinatorLockTimeoutError("turn lock busy")

            if idempotency_key:
                prior_user = await self._mysql.find_turn_by_idempotency(
                    session_id, idempotency_key
                )
                if prior_user is not None:
                    prior_fp = (
                        prior_user.content.get("body_hash")
                        if isinstance(prior_user.content, dict)
                        else None
                    )
                    if prior_fp != fp:
                        raise IdempotencyConflictError("idempotency mismatch")
                    asst = await self._mysql.get_turn(session_id, prior_user.turn_index + 1)
                    if asst and asst.role == "assistant":
                        return TurnResult(
                            turn_index=prior_user.turn_index,
                            assistant_message=_content_text(asst.content),
                            intent=str(asst.intent or "new_query"),
                            intent_confidence=float(asst.intent_confidence or 1.0),
                            degraded_mode=False,
                            trace_id=str(asst.trace_id or trace_id),
                        )

            snap_row = await self._mysql.latest_snapshot(session_id)
            snapshot_blob = dict(snap_row.state_blob) if snap_row else {}
            has_snapshot = bool(snap_row)

            doc = await self._redis.get_working_doc(session_id)
            if doc is None and snapshot_blob:
                await self._redis.set_working_doc(
                    session_id,
                    {"state_blob": snapshot_blob, "source": "mysql_reload"},
                )

            ti = await self._mysql.next_turn_index(session_id)
            await self._mysql.append_turn(
                session_id,
                ti,
                "user",
                {"text": message, "body_hash": fp},
                trace_id=trace_id,
                idempotency_key=idempotency_key,
            )

            prior_synthesis = str(snapshot_blob.get("synthesis") or "")
            rewritten, was_rewritten = await rewrite_with_context(
                self._ctx["llm"], message, prior_synthesis,
            )
            if was_rewritten:
                await log.ainfo(
                    "query_rewritten", original=message, rewritten=rewritten,
                )

            intent = await self._classifier.classify(
                rewritten,
                has_prior_synthesis=bool(prior_synthesis),
                prior_summary=prior_synthesis[:500],
            )
            plan = plan_route(
                intent.intent,
                intent.confidence,
                session_has_snapshot=has_snapshot,
                confidence_threshold=self._settings.intent_confidence_threshold,
            )

            constraints_patch: dict[str, Any] = dict(intent.constraints_suggested or {})
            engine_input = build_engine_input(
                snapshot_blob,
                message,
                trace_id,
                session_id,
                client_session_id=client_session_id,
                constraints_patch=constraints_patch,
                conversation_intent=intent.intent,
                rewritten_query=rewritten if was_rewritten else None,
            )

            if plan.mode == "clarify_only":
                assistant_text = _CLARIFY_MESSAGE
                await self._mysql.append_turn(
                    session_id,
                    ti + 1,
                    "assistant",
                    {"text": assistant_text},
                    intent="needs_clarification",
                    intent_confidence=intent.confidence,
                    trace_id=trace_id,
                )
                await self._redis.set_working_doc(
                    session_id,
                    {"state_blob": snapshot_blob, "last_turn_index": ti + 1},
                )
                return TurnResult(
                    turn_index=ti,
                    assistant_message=assistant_text,
                    intent="needs_clarification",
                    intent_confidence=intent.confidence,
                    degraded_mode=False,
                    trace_id=trace_id,
                    route_mode=plan.mode,
                    engine_entry=plan.engine_entry,
                )

            if plan.engine_entry == "synthesizer_only" and self._light is not None:
                result = await invoke_light_synthesizer_graph(
                    self._light, engine_input, self._ctx
                )
                engine_label = "synthesizer_only"
            else:
                result = await invoke_research_graph_continuation(
                    self._full, engine_input, self._ctx
                )
                engine_label = "research_graph"

            assistant_text = str(result.get("synthesis") or "")
            blob = state_blob_from_graph_result(result)
            blob["constraints"] = merge_constraint_dicts(
                dict(snapshot_blob.get("constraints") or {}),
                constraints_patch,
            )

            await self._mysql.append_turn(
                session_id,
                ti + 1,
                "assistant",
                {"text": assistant_text},
                intent=intent.intent,
                intent_confidence=intent.confidence,
                trace_id=trace_id,
            )
            await self._mysql.save_snapshot(session_id, ti + 1, blob)
            await self._redis.set_working_doc(
                session_id,
                {"state_blob": blob, "last_turn_index": ti + 1},
            )

            await log.ainfo(
                "coordinator_turn_complete",
                turn_index=ti,
                route_mode=plan.mode,
                engine_entry=engine_label,
            )

            return TurnResult(
                turn_index=ti,
                assistant_message=assistant_text,
                intent=intent.intent,
                intent_confidence=intent.confidence,
                degraded_mode=False,
                trace_id=trace_id,
                route_mode=plan.mode,
                engine_entry=engine_label,
            )
        finally:
            structlog.contextvars.clear_contextvars()
            if token:
                await self._redis.release_turn_lock(session_id, token)

    async def run_turn_streaming(
        self,
        *,
        owner_principal_id: str,
        session_id: str,
        message: str,
        trace_id: str,
        client_session_id: Optional[str] = None,
        idempotency_key: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """SSE streaming variant of :meth:`run_turn`.

        Yields ``event: status`` frames as graph nodes execute and a final
        ``event: result`` frame with the :class:`TurnResult` payload.
        """
        log = structlog.get_logger()
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            session_id=session_id,
            trace_id=trace_id,
            agent_id="conversation_coordinator",
            client_session_id=client_session_id,
        )

        if not await self._redis.ping():
            await log.awarning("redis_unavailable", session_id=session_id)
            raise StorageDegradedError("redis unavailable for turn lock / working set")

        session = await self._mysql.get_session_for_owner(session_id, owner_principal_id)
        if session is None:
            structlog.contextvars.clear_contextvars()
            raise SessionAccessDenied("session not found")

        fp = body_fingerprint(message, client_session_id)

        token: Optional[str] = None
        try:
            for _ in range(200):
                token = await self._redis.acquire_turn_lock(session_id)
                if token:
                    break
                await asyncio.sleep(0.02)
            if not token:
                raise CoordinatorLockTimeoutError("turn lock busy")

            if idempotency_key:
                prior_user = await self._mysql.find_turn_by_idempotency(
                    session_id, idempotency_key
                )
                if prior_user is not None:
                    prior_fp = (
                        prior_user.content.get("body_hash")
                        if isinstance(prior_user.content, dict)
                        else None
                    )
                    if prior_fp != fp:
                        raise IdempotencyConflictError("idempotency mismatch")
                    asst = await self._mysql.get_turn(session_id, prior_user.turn_index + 1)
                    if asst and asst.role == "assistant":
                        cached = TurnResult(
                            turn_index=prior_user.turn_index,
                            assistant_message=_content_text(asst.content),
                            intent=str(asst.intent or "new_query"),
                            intent_confidence=float(asst.intent_confidence or 1.0),
                            degraded_mode=False,
                            trace_id=str(asst.trace_id or trace_id),
                        )
                        yield f"event: result\ndata: {cached.model_dump_json()}\n\n"
                        return

            snap_row = await self._mysql.latest_snapshot(session_id)
            snapshot_blob = dict(snap_row.state_blob) if snap_row else {}
            has_snapshot = bool(snap_row)

            doc = await self._redis.get_working_doc(session_id)
            if doc is None and snapshot_blob:
                await self._redis.set_working_doc(
                    session_id,
                    {"state_blob": snapshot_blob, "source": "mysql_reload"},
                )

            ti = await self._mysql.next_turn_index(session_id)
            await self._mysql.append_turn(
                session_id,
                ti,
                "user",
                {"text": message, "body_hash": fp},
                trace_id=trace_id,
                idempotency_key=idempotency_key,
            )

            prior_synthesis = str(snapshot_blob.get("synthesis") or "")
            rewritten, was_rewritten = await rewrite_with_context(
                self._ctx["llm"], message, prior_synthesis,
            )
            if was_rewritten:
                await log.ainfo(
                    "query_rewritten", original=message, rewritten=rewritten,
                )

            intent = await self._classifier.classify(
                rewritten,
                has_prior_synthesis=bool(prior_synthesis),
                prior_summary=prior_synthesis[:500],
            )
            plan = plan_route(
                intent.intent,
                intent.confidence,
                session_has_snapshot=has_snapshot,
                confidence_threshold=self._settings.intent_confidence_threshold,
            )

            constraints_patch: dict[str, Any] = dict(intent.constraints_suggested or {})
            engine_input = build_engine_input(
                snapshot_blob,
                message,
                trace_id,
                session_id,
                client_session_id=client_session_id,
                constraints_patch=constraints_patch,
                conversation_intent=intent.intent,
                rewritten_query=rewritten if was_rewritten else None,
            )

            if plan.mode == "clarify_only":
                assistant_text = _CLARIFY_MESSAGE
                await self._mysql.append_turn(
                    session_id,
                    ti + 1,
                    "assistant",
                    {"text": assistant_text},
                    intent="needs_clarification",
                    intent_confidence=intent.confidence,
                    trace_id=trace_id,
                )
                await self._redis.set_working_doc(
                    session_id,
                    {"state_blob": snapshot_blob, "last_turn_index": ti + 1},
                )
                result_obj = TurnResult(
                    turn_index=ti,
                    assistant_message=assistant_text,
                    intent="needs_clarification",
                    intent_confidence=intent.confidence,
                    degraded_mode=False,
                    trace_id=trace_id,
                    route_mode=plan.mode,
                    engine_entry=plan.engine_entry,
                )
                yield f"event: result\ndata: {result_obj.model_dump_json()}\n\n"
                return

            progress_queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()

            if plan.engine_entry == "synthesizer_only" and self._light is not None:
                graph_coro = invoke_research_graph_continuation_with_progress(
                    self._light, engine_input, self._ctx, progress_queue,
                )
                engine_label = "synthesizer_only"
            else:
                graph_coro = invoke_research_graph_continuation_with_progress(
                    self._full, engine_input, self._ctx, progress_queue,
                )
                engine_label = "research_graph"

            graph_task = asyncio.create_task(graph_coro)

            while not graph_task.done():
                try:
                    evt = await asyncio.wait_for(progress_queue.get(), timeout=1.0)
                    yield f"event: status\ndata: {json.dumps(evt)}\n\n"
                except asyncio.TimeoutError:
                    continue

            while not progress_queue.empty():
                evt = progress_queue.get_nowait()
                yield f"event: status\ndata: {json.dumps(evt)}\n\n"

            result = await graph_task

            assistant_text = str(result.get("synthesis") or "")
            blob = state_blob_from_graph_result(result)
            blob["constraints"] = merge_constraint_dicts(
                dict(snapshot_blob.get("constraints") or {}),
                constraints_patch,
            )

            await self._mysql.append_turn(
                session_id,
                ti + 1,
                "assistant",
                {"text": assistant_text},
                intent=intent.intent,
                intent_confidence=intent.confidence,
                trace_id=trace_id,
            )
            await self._mysql.save_snapshot(session_id, ti + 1, blob)
            await self._redis.set_working_doc(
                session_id,
                {"state_blob": blob, "last_turn_index": ti + 1},
            )

            await log.ainfo(
                "coordinator_turn_complete",
                turn_index=ti,
                route_mode=plan.mode,
                engine_entry=engine_label,
            )

            turn_result = TurnResult(
                turn_index=ti,
                assistant_message=assistant_text,
                intent=intent.intent,
                intent_confidence=intent.confidence,
                degraded_mode=False,
                trace_id=trace_id,
                route_mode=plan.mode,
                engine_entry=engine_label,
            )
            yield f"event: result\ndata: {turn_result.model_dump_json()}\n\n"
        finally:
            structlog.contextvars.clear_contextvars()
            if token:
                await self._redis.release_turn_lock(session_id, token)

    async def create_session_row(self, owner_principal_id: str) -> str:
        row = await self._mysql.create_session(owner_principal_id)
        await self._redis.set_working_doc(row.id, {"state_blob": {}, "last_turn_index": -1})
        return row.id
