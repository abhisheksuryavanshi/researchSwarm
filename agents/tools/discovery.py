from __future__ import annotations

import asyncio
import json
import re
import time
from html import unescape
from typing import Any, Optional, Type

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, create_model

from agents.config import AgentConfig
from agents.prompts import researcher as researcher_prompts
from agents.response_models import (
    InvocationAttempt,
    ToolDiscoveryInput,
    ToolDiscoveryResult,
    ToolSelectionResponse,
)
from agents.tools.registry_client import RegistryClient
from agents.tracing import (
    current_trace_excerpt_max,
    get_langfuse_client,
    get_logger,
    is_langfuse_run_enabled,
    langfuse_run_metadata_dict,
    trace_id_for_langfuse,
    truncate_for_trace,
)

_WH_WORD = re.compile(
    r"^\s*(?:what|who|where|when|why|how)\s+"
    r"(?:is|are|was|were|do|does|did|can|could|should|would)\s+",
    re.I,
)
_LEADING_THE = re.compile(r"^the\s+", re.I)


def _simplify_for_wikipedia_search(text: str) -> str:
    """Turn common English questions into a shorter search phrase for on-wiki search."""
    original = (text or "").strip()
    if not original:
        return original
    s = _WH_WORD.sub("", original)
    s = _LEADING_THE.sub("", s)
    s = s.rstrip("?").strip()
    if len(s) < 2:
        return original
    return s


def fallback_for_type(
    type_name: Optional[str], query: str, constraints: dict[str, Any]
) -> Any:
    if type_name == "string":
        return query
    if type_name == "integer":
        return 0
    if type_name == "number":
        return 0.0
    if type_name == "boolean":
        return False
    if type_name == "array":
        return []
    if type_name == "object":
        return constraints
    return query


def build_tool_payload(
    *,
    query: str,
    constraints: dict[str, Any],
    gaps: list[str],
    args_schema: Optional[dict[str, Any]],
) -> dict[str, Any]:
    schema = args_schema if isinstance(args_schema, dict) else {}
    properties = (
        schema.get("properties") if isinstance(schema.get("properties"), dict) else None
    )
    required = schema.get("required") if isinstance(schema.get("required"), list) else []

    if not properties:
        payload: dict[str, Any] = {"query": query}
        if constraints:
            payload["constraints"] = constraints
        if gaps:
            payload["gaps"] = gaps
        return payload

    payload = {}
    lowered_constraints = {str(k).lower(): v for k, v in constraints.items()}

    for key, prop in properties.items():
        key_l = key.lower()
        prop_d = prop if isinstance(prop, dict) else {}

        if key_l in {"gsrsearch", "srsearch"}:
            payload[key] = _simplify_for_wikipedia_search(query)
            continue
        if key_l in {
            "query",
            "q",
            "question",
            "prompt",
            "search_query",
            "search_term",
            "text",
        }:
            payload[key] = query
            continue
        if key_l in {"constraints", "filters"}:
            payload[key] = constraints
            continue
        if key_l in {"gaps", "missing_topics", "follow_up_topics"}:
            payload[key] = gaps
            continue
        if key_l in lowered_constraints:
            payload[key] = lowered_constraints[key_l]
            continue
        if key in constraints:
            payload[key] = constraints[key]
            continue
        if "default" in prop_d:
            payload[key] = prop_d["default"]

    for req in required:
        if req not in payload:
            rprop = properties.get(req, {})
            rtype = rprop.get("type") if isinstance(rprop, dict) else None
            payload[req] = fallback_for_type(rtype, query, constraints)

    return payload


def _field_for_json_property(
    spec: dict[str, Any], required: bool
) -> tuple[Any, Any]:
    jt = spec.get("type") if isinstance(spec.get("type"), str) else "string"
    if jt == "string":
        return (str, ...) if required else (str, "")
    if jt == "integer":
        return (int, ...) if required else (int, 0)
    if jt == "number":
        return (float, ...) if required else (float, 0.0)
    if jt == "boolean":
        return (bool, ...) if required else (bool, False)
    if jt == "array":
        return (list[Any], ...) if required else (list[Any], Field(default_factory=list))  # type: ignore[valid-type]
    if jt == "object":
        return (dict[str, Any], ...) if required else (
            dict[str, Any],
            Field(default_factory=dict),
        )
    return (str, ...) if required else (str, "")


class GenericToolInput(BaseModel):
    query: str
    constraints: dict[str, Any] = Field(default_factory=dict)
    gaps: list[str] = Field(default_factory=list)


def _args_schema_to_model(
    tool_name: str, args_schema: Optional[dict[str, Any]]
) -> Type[BaseModel]:
    if not isinstance(args_schema, dict):
        return GenericToolInput
    props = args_schema.get("properties")
    if not isinstance(props, dict) or not props:
        return GenericToolInput
    required_list = args_schema.get("required")
    required: set[str] = (
        set(required_list) if isinstance(required_list, list) else set()
    )
    safe = re.sub(r"\W+", "_", tool_name).strip("_") or "Tool"
    field_defs: dict[str, Any] = {}
    for fname, spec in props.items():
        if not isinstance(spec, dict):
            continue
        field_defs[fname] = _field_for_json_property(spec, fname in required)
    if not field_defs:
        return GenericToolInput
    return create_model(f"DynamicArgs_{safe}", **field_defs)  # type: ignore[call-overload]


def build_dynamic_tool(
    bind_response: dict[str, Any],
    registry: RegistryClient,
    timeout_seconds: int = 30,
) -> StructuredTool:
    name = str(bind_response.get("name") or "dynamic_tool")
    description = str(bind_response.get("description") or "")
    endpoint = bind_response["endpoint"]
    method = str(bind_response.get("method") or "POST")
    args_schema = bind_response.get("args_schema")
    model_cls = _args_schema_to_model(name, args_schema if isinstance(args_schema, dict) else None)

    async def _invoke(**kwargs: Any) -> dict[str, Any]:
        payload = dict(kwargs)
        return await asyncio.wait_for(
            registry.invoke(endpoint, method, payload),
            timeout=timeout_seconds,
        )

    return StructuredTool.from_function(
        coroutine=_invoke,
        name=name,
        description=description,
        args_schema=model_cls,
        infer_schema=False,
    )


def _search_summary(results: list[dict[str, Any]]) -> str:
    lines = []
    for r in results:
        caps = ", ".join(r.get("capabilities") or [])
        desc = str(r.get("description") or "")
        if len(desc) > 2000:
            desc = desc[:2000] + "…"
        lines.append(
            f"- tool_id={r.get('tool_id')} name={r.get('name')} "
            f"capabilities=[{caps}] avg_latency_ms={r.get('avg_latency_ms')} "
            f"desc={desc}"
        )
    return "\n".join(lines) if lines else "(no tools)"


WIKIPEDIA_LOOKUP_TOOL_ID = "wikipedia-lookup-v1"
_WIKIPEDIA_PARSE_API = "https://en.wikipedia.org/w/api.php"


def _html_to_plaintext(html: str) -> str:
    if not html:
        return ""
    s = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    s = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", s)
    s = re.sub(r"<[^>]+>", " ", s)
    s = unescape(s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _wikipedia_title_rank(title: str) -> tuple:
    """Lower tuple sorts first: prefer main topic articles over season/list pages."""
    tl = title.lower()
    has_season_number = bool(re.search(r"\bseason\s+\d+\b", tl))
    is_list_like = tl.startswith("list of ") or (
        "list" in tl and ("episode" in tl or "episodes" in tl)
    )
    return (has_season_number, is_list_like, len(title))


def _wikipedia_title_from_query_response(data: dict[str, Any]) -> Optional[str]:
    """Pick one Wikipedia page title for enrichment and citations.

    With ``generator=search`` and ``gsrlimit=1``, the API often returns a sub-article
    (e.g. ``Rick and Morty season 6``) ahead of the main ``Rick and Morty`` article for
    broad queries — then the whole graph faithfully summarizes the wrong page. We request
    multiple hits and prefer titles without ``season N`` / list-of patterns when possible.
    """
    q = data.get("query")
    if not isinstance(q, dict):
        return None
    pages = q.get("pages")
    if not isinstance(pages, dict) or not pages:
        return None
    titles: list[str] = []
    for row in pages.values():
        if not isinstance(row, dict) or row.get("missing"):
            continue
        t = row.get("title")
        if isinstance(t, str) and t.strip():
            titles.append(t.strip())
    if not titles:
        return None
    if len(titles) == 1:
        return titles[0]
    titles.sort(key=_wikipedia_title_rank)
    return titles[0]


async def _maybe_enrich_wikipedia_article(
    raw_data: dict[str, Any],
    *,
    tool_id: str,
    registry: RegistryClient,
    config: AgentConfig,
    log: Any,
) -> None:
    if tool_id != WIKIPEDIA_LOOKUP_TOOL_ID:
        return
    if not getattr(config, "wikipedia_enrich_with_parse", True):
        return
    title = _wikipedia_title_from_query_response(raw_data)
    if not title:
        return
    max_chars = int(getattr(config, "wikipedia_max_article_chars", 100_000) or 0)
    timeout_s = float(getattr(config, "tool_invocation_timeout_seconds", 30) or 30)
    try:
        parsed = await asyncio.wait_for(
            registry.invoke(
                _WIKIPEDIA_PARSE_API,
                "GET",
                {
                    "action": "parse",
                    "page": title,
                    "prop": "text",
                    "format": "json",
                    "formatversion": "2",
                },
            ),
            timeout=timeout_s,
        )
    except Exception as exc:
        await log.awarning(
            "wikipedia_parse_enrich_failed",
            title=title,
            error=str(exc),
        )
        return
    if not isinstance(parsed, dict):
        return
    parse_block = parsed.get("parse")
    if not isinstance(parse_block, dict):
        return
    html = parse_block.get("text")
    if not isinstance(html, str) or not html.strip():
        return
    plain = _html_to_plaintext(html)
    if max_chars > 0 and len(plain) > max_chars:
        plain = plain[:max_chars] + "\n\n...[article truncated for size]"
    raw_data["enriched_article_plaintext"] = plain


def _filter_results_by_constraints(
    results: list[dict[str, Any]], constraints: dict[str, Any]
) -> list[dict[str, Any]]:
    sources = constraints.get("sources")
    if not isinstance(sources, list) or not sources:
        return results
    want = {str(s).lower() for s in sources}
    out = []
    for r in results:
        caps = [str(c).lower() for c in (r.get("capabilities") or [])]
        name_l = str(r.get("name") or "").lower()
        desc_l = str(r.get("description") or "").lower()
        if any(w in caps or w in name_l or w in desc_l for w in want):
            out.append(r)
    return out if out else results


def _ordered_candidates(
    results: list[dict[str, Any]],
    selection: Optional[ToolSelectionResponse],
    max_attempts: int,
) -> list[str]:
    """Order tools to invoke: only LLM-selected ids (deduped), capped at max_attempts.

    If the LLM selection is missing or empty (e.g. parse failure), fall back to a single
    lowest-latency tool from search results. We do **not** pad with extra tools the model
    did not choose—later graph iterations can select more or different tools via refinement.
    """
    by_latency = sorted(
        results,
        key=lambda r: float(r.get("avg_latency_ms") or 1e9),
    )
    ordered: list[str] = []
    if selection and selection.selected_tool_ids:
        for tid in selection.selected_tool_ids:
            tid = str(tid).strip()
            if tid and tid not in ordered:
                ordered.append(tid)
    if not ordered and by_latency:
        ordered = [str(by_latency[0]["tool_id"])]
    return ordered[:max_attempts]


def _wrap_tool_data(raw: dict[str, Any], tool_id: str, success: bool) -> dict[str, Any]:
    return {
        "tool_id": tool_id,
        "raw_data": raw,
        "success": success,
    }


def _wikipedia_rest_desktop_url(data: dict[str, Any]) -> str:
    cu = data.get("content_urls")
    if isinstance(cu, dict):
        desk = cu.get("desktop")
        if isinstance(desk, dict):
            page = desk.get("page")
            if isinstance(page, str) and page:
                return page
    return ""


def _mediawiki_api_page_url_title(data: dict[str, Any]) -> tuple[str, str]:
    """URL + title for the same primary page chosen for Wikipedia enrichment."""
    q = data.get("query")
    if not isinstance(q, dict):
        return "", ""
    pages = q.get("pages")
    if not isinstance(pages, dict) or not pages:
        return "", ""
    pick = _wikipedia_title_from_query_response(data)
    if not pick:
        return "", ""
    for row in pages.values():
        if not isinstance(row, dict):
            continue
        if str(row.get("title") or "") != pick:
            continue
        url = str(row.get("fullurl") or row.get("canonicalurl") or "")
        return url, pick
    return "", pick


def _source_from_data(
    data: dict[str, Any], tool_id: str, bind_name: Optional[str]
) -> dict[str, str]:
    mw_url, mw_title = _mediawiki_api_page_url_title(data)
    url = str(
        data.get("url")
        or data.get("link")
        or _wikipedia_rest_desktop_url(data)
        or mw_url
        or f"https://tool/{tool_id}"
    )
    title = str(data.get("title") or mw_title or bind_name or tool_id)
    return {"url": url, "title": title, "tool_id": tool_id}


class ToolDiscoveryTool(BaseTool):
    name: str = "tool_discovery"
    description: str = (
        "Search the tool registry for a capability, select the best tool, and invoke it."
    )
    args_schema: type[BaseModel] = ToolDiscoveryInput

    def __init__(
        self,
        registry: RegistryClient,
        llm: BaseChatModel,
        config: AgentConfig,
        *,
        callbacks: Optional[list[Any]] = None,
    ) -> None:
        super().__init__()
        self._registry = registry
        self._llm = llm
        self._config = config
        self._extra_callbacks = list(callbacks or [])

    def _run(self, *args: Any, **kwargs: Any) -> Any:
        raise NotImplementedError("ToolDiscoveryTool is async-only; use ainvoke.")

    async def _arun(self, **kwargs: Any) -> str:
        inp = ToolDiscoveryInput.model_validate(kwargs)
        log = get_logger(
            inp.trace_id or "-",
            inp.session_id or "-",
            inp.agent_id or "tool_discovery",
            inp.client_session_id,
        )
        cap = inp.capability or None
        attempts: list[InvocationAttempt] = []

        await log.ainfo("tool_discovery_enter", capability=cap or "")

        try:
            search_payload = await self._registry.search(
                capability=cap,
                limit=50,
                constraints=inp.constraints if isinstance(inp.constraints, dict) else None,
            )
        except Exception as exc:
            await log.aerror("tool_discovery_search_failed", error=str(exc), exc_info=True)
            res = ToolDiscoveryResult(
                success=False,
                error=f"registry search failed: {exc}",
                attempts=[],
            )
            return res.model_dump_json()

        raw_results = list(search_payload.get("results") or [])
        results = _filter_results_by_constraints(
            raw_results, inp.constraints if isinstance(inp.constraints, dict) else {}
        )
        if not results:
            res = ToolDiscoveryResult(
                success=False,
                error=(
                    f"no tools found for capability: {cap or '(all)'}"
                    if cap
                    else "no tools matched the search and constraint filters"
                ),
                attempts=[],
            )
            return res.model_dump_json()

        summary = _search_summary(results)
        constraints_s = json.dumps(inp.constraints, default=str)
        if inp.gaps:
            user_content = researcher_prompts.REFINEMENT_PROMPT.format(
                iteration_count=max(1, inp.iteration_count),
                gaps="\n".join(f"- {g}" for g in inp.gaps),
                query=inp.query,
                constraints=constraints_s,
                search_summary=summary,
            )
        else:
            user_content = researcher_prompts.USER_PROMPT.format(
                query=inp.query,
                constraints=constraints_s,
                search_summary=summary,
            )
        cb_cfg: dict[str, Any] = {}
        if self._extra_callbacks:
            cb_cfg["callbacks"] = self._extra_callbacks
            cb_cfg["metadata"] = langfuse_run_metadata_dict(
                session_id=inp.session_id,
                trace_id=inp.trace_id,
                client_session_id=inp.client_session_id,
            )

        selection: Optional[ToolSelectionResponse] = None
        try:
            runnable = self._llm.with_structured_output(
                ToolSelectionResponse, include_raw=True
            )
            out = await runnable.ainvoke(
                [
                    SystemMessage(content=researcher_prompts.SYSTEM_PROMPT),
                    HumanMessage(content=user_content),
                ],
                config=cb_cfg or None,
            )
            if isinstance(out, dict):
                selection = out.get("parsed")
            else:
                selection = out  # type: ignore[assignment]
        except Exception as exc:
            await log.awarning("tool_discovery_llm_select_failed", error=str(exc))

        max_a = self._config.max_tool_fallback_attempts
        candidates = _ordered_candidates(results, selection, max_a)

        if not candidates:
            res = ToolDiscoveryResult(
                success=False,
                error="could not determine a tool candidate",
                attempts=[],
            )
            return res.model_dump_json()

        timeout_s = self._config.tool_invocation_timeout_seconds
        gaps = inp.gaps if isinstance(inp.gaps, list) else []
        constraints_d = inp.constraints if isinstance(inp.constraints, dict) else {}

        for tool_id in candidates:
            bind_info: Optional[dict[str, Any]] = None
            try:
                bind_info = await self._registry.bind(tool_id)
            except Exception as exc:
                await log.aerror(
                    "tool_discovery_bind_failed",
                    tool_id=tool_id,
                    error=str(exc),
                    exc_info=True,
                )
                continue

            start = time.perf_counter()
            success = False
            err_msg: Optional[str] = None
            raw_data: dict[str, Any] = {}
            span_obj: Any = None
            max_c = current_trace_excerpt_max()
            try:
                dyn = build_dynamic_tool(
                    bind_info, self._registry, timeout_seconds=timeout_s
                )
                payload = build_tool_payload(
                    query=inp.query,
                    constraints=constraints_d,
                    gaps=gaps,
                    args_schema=bind_info.get("args_schema"),
                )
                if tool_id == WIKIPEDIA_LOOKUP_TOOL_ID:
                    try:
                        gl = int(payload.get("gsrlimit", 1) or 1)
                    except (TypeError, ValueError):
                        gl = 1
                    if gl < 5:
                        payload["gsrlimit"] = 8
                if is_langfuse_run_enabled():
                    lf = get_langfuse_client()
                    if lf is not None:
                        try:
                            norm_tid = trace_id_for_langfuse(inp.trace_id)
                            trace_ref = lf.trace(id=norm_tid)
                            span_obj = trace_ref.span(
                                name=f"tool:{tool_id}",
                                input=truncate_for_trace(
                                    json.dumps(payload, default=str),
                                    max_c,
                                ),
                                metadata={
                                    **langfuse_run_metadata_dict(
                                        session_id=inp.session_id,
                                        trace_id=inp.trace_id,
                                        client_session_id=inp.client_session_id,
                                    ),
                                    "tool_id": tool_id,
                                    "agent_id": inp.agent_id or "tool_discovery",
                                },
                            )
                        except Exception as exc:
                            await log.aerror(
                                "langfuse_tool_span_failed",
                                tool_id=tool_id,
                                error=str(exc),
                                exc_info=True,
                            )
                            span_obj = None
                out = await asyncio.wait_for(dyn.ainvoke(payload), timeout=timeout_s)
                raw_data = out if isinstance(out, dict) else {"result": out}
                await _maybe_enrich_wikipedia_article(
                    raw_data,
                    tool_id=tool_id,
                    registry=self._registry,
                    config=self._config,
                    log=log,
                )
                success = True
            except Exception as exc:
                err_msg = str(exc)
                await log.aerror(
                    "tool_discovery_invoke_failed",
                    tool_id=tool_id,
                    error=err_msg,
                    exc_info=True,
                )
            finally:
                if span_obj is not None:
                    try:
                        if success:
                            span_obj.update(
                                output=truncate_for_trace(
                                    json.dumps(raw_data, default=str),
                                    max_c,
                                )
                            ).end()
                        else:
                            span_obj.update(
                                level="ERROR",
                                status_message=err_msg or "invoke failed",
                            ).end()
                    except Exception as span_exc:
                        await log.aerror(
                            "langfuse_tool_span_end_failed",
                            tool_id=tool_id,
                            error=str(span_exc),
                        )
                latency_ms = (time.perf_counter() - start) * 1000
                attempts.append(
                    InvocationAttempt(
                        tool_id=tool_id,
                        success=success,
                        latency_ms=latency_ms,
                        error_message=err_msg,
                    )
                )
                await self._registry.log_usage(
                    tool_id=tool_id,
                    agent_id=inp.agent_id or None,
                    session_id=inp.session_id or None,
                    latency_ms=latency_ms,
                    success=success,
                    error_message=err_msg,
                )

            if success:
                wrapped = _wrap_tool_data(raw_data, tool_id, True)
                src = _source_from_data(
                    raw_data, tool_id, bind_info.get("name") if bind_info else None
                )
                res = ToolDiscoveryResult(
                    success=True,
                    tool_id=tool_id,
                    data=wrapped,
                    source=src,
                    attempts=attempts,
                )
                await log.ainfo(
                    "tool_discovery_success",
                    capability=cap or "",
                    tool_id=tool_id,
                    attempts=len(attempts),
                )
                return res.model_dump_json()

        res = ToolDiscoveryResult(
            success=False,
            tool_id=None,
            data={},
            source={},
            attempts=attempts,
            error=f"all {len(attempts)} tool attempt(s) failed",
        )
        await log.awarning(
            "tool_discovery_exhausted",
            capability=cap or "",
            attempts=len(attempts),
        )
        return res.model_dump_json()
