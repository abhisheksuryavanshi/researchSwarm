# Implementation Plan: Operator Web UI

**Branch**: `006-operator-web-ui` | **Date**: 2026-04-03 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/006-operator-web-ui/spec.md` — Thin operator-facing web client over existing HTTP APIs (sessions + tool registry). No authentication; session_id as the work key. Single active session with localStorage persistence. Markdown-rendered chat, read-only tool catalog + stats, dark mode default, CORS enablement on backend.

## Summary

Add a **web UI** (`web/`) as a new **presentation layer** on top of the existing backend APIs. The UI is a thin React + TypeScript client built with Vite. It consumes **two existing API surfaces**: the **session API** (`POST /v1/sessions`, `POST /v1/sessions/{id}/turns`) for conversational Q&A, and the **tool registry API** (`GET /tools/search`, `GET /tools/{id}/bind`, `GET /tools/{id}/health`, `GET /tools/stats`) for read-only tool browsing and monitoring. A single, small **backend change** adds `CORSMiddleware` to the FastAPI app so the browser can reach the API without a proxy.

The UI generates a stable **principal identifier** (UUID stored in localStorage) used as the Bearer token for the session API — effectively a device key, not an auth credential. One active session at a time; "New Session" replaces it. Turn history is accumulated client-side. Assistant responses are rendered as **markdown**. Dark mode is the default theme.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend), Python 3.9+ (backend CORS patch)
**Primary Dependencies**: Vite 6, React 18, React Router 6, Tailwind CSS 4, react-markdown + remark-gfm, Vitest + @testing-library/react (frontend); FastAPI CORSMiddleware (backend)
**Storage**: Browser localStorage (session_id, principal_id, turn history); no new server-side storage
**Testing**: Vitest + @testing-library/react (unit/component), Playwright (optional e2e); pytest for backend CORS contract test
**Target Platform**: Modern evergreen browsers (Chrome, Firefox, Safari, Edge — latest 2 versions); desktop-first
**Project Type**: Single-page web application (thin client)
**Performance Goals**: First meaningful paint < 2s; chat round-trip latency dominated by server (UI adds < 100ms overhead); tool catalog renders < 3s
**Constraints**: No tool business logic in browser (FR-020); read-only registry consumer; single active session (FR-022); dark mode default (FR-015)
**Scale/Scope**: Single-operator use; ~5 views (chat, tools list, tool detail, stats, error states)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| # | Principle | Status | Evidence |
|---|-----------|--------|----------|
| I | Dynamic Tool Architecture | **PASS** | UI reads tools from registry via `GET /tools/search` and `/tools/{id}/bind`; no hardcoded tool lists. Registry remains sole source of truth. |
| II | Layered Independence | **PASS** | `web/` is a new **presentation layer** with a strict dependency direction: `web/` → existing HTTP APIs. No backend imports from `web/`. The frontend is independently testable (Vitest), independently deployable (static build), and independently versioned (`web/package.json`). |
| III | Agent Autonomy with Bounded Scope | **PASS** | No agent logic in the browser. The UI sends user text to the Conversation Coordinator; all research/analysis/synthesis stays server-side. |
| IV | Test-First with Contract Testing | **PASS** | Typed API response interfaces in `lib/api/types.ts` serve as contract definitions. Component tests validate rendering against these types. Backend CORS change gets a contract test in `tests/contract/`. |
| V | Observability as Infrastructure | **PASS** | Every request carries `X-Trace-ID` (UUID generated per request) and `X-Session-ID`. The backend's existing structlog/Langfuse pipeline picks these up unchanged. No silent failures: all fetch errors surface via `ErrorBanner`. |
| VI | Performance Under Budget | **PASS** | UI is a thin rendering layer; latency budget is dominated by server. Registry search (< 100ms server-side) + render overhead stays well under the 3s catalog target. |
| VII | Session Continuity & Research Accumulation | **PASS** | UI persists `session_id` in localStorage and passes it on every turn. Server-side session continuity (snapshots, accumulated context) works unchanged. Client-side turn history is an additive display concern only. |

**Gate result**: **ALL PASS** — proceed.

## Project Structure

### Documentation (this feature)

```text
specs/006-operator-web-ui/
├── plan.md              # This file
├── research.md          # Phase 0
├── data-model.md        # Phase 1
├── quickstart.md        # Phase 1
├── contracts/
│   └── frontend-api.md  # Consumed API surface (typed)
└── tasks.md             # Phase 2 (/speckit.tasks — not created here)
```

### Source Code (repository root)

```text
web/
├── index.html
├── package.json
├── tsconfig.json
├── tsconfig.node.json
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.js
├── src/
│   ├── main.tsx                    # React DOM entry
│   ├── App.tsx                     # Router + Layout shell
│   ├── index.css                   # Tailwind directives + CSS custom properties (design tokens)
│   ├── lib/
│   │   ├── api/
│   │   │   ├── client.ts           # Base fetch wrapper: X-Trace-ID, X-Session-ID, Bearer, error mapping
│   │   │   ├── sessions.ts         # createSession(), postTurn() — typed
│   │   │   ├── tools.ts            # searchTools(), getToolBind(), getToolHealth(), getToolStats() — typed
│   │   │   └── types.ts            # TypeScript interfaces mirroring server Pydantic models
│   │   ├── session-store.ts        # localStorage abstraction with in-memory fallback
│   │   └── hooks/
│   │       ├── useSession.ts       # Session lifecycle hook (auto-create, recover, new session)
│   │       └── useApi.ts           # Generic fetch-with-state hook (loading, error, data)
│   ├── components/
│   │   ├── ui/                     # Reusable primitives (design-token-aware)
│   │   │   ├── Button.tsx
│   │   │   ├── Input.tsx
│   │   │   ├── Card.tsx
│   │   │   ├── Layout.tsx          # App shell: sidebar nav + main content area
│   │   │   ├── PageHeader.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   ├── ErrorBanner.tsx
│   │   │   ├── Skeleton.tsx
│   │   │   └── Badge.tsx
│   │   ├── chat/
│   │   │   ├── ChatView.tsx        # Turn list + input + session header
│   │   │   ├── MessageBubble.tsx   # Operator / assistant message with markdown
│   │   │   ├── ChatInput.tsx       # Text input + send button + disabled states
│   │   │   ├── TurnMetadata.tsx    # Intent, confidence, trace_id, degraded badge
│   │   │   └── SessionHeader.tsx   # Session ID display + "New Session" button
│   │   ├── tools/
│   │   │   ├── ToolCatalog.tsx     # Search + grid/list of ToolCards
│   │   │   ├── ToolCard.tsx        # Summary card (name, description, capabilities, status)
│   │   │   ├── ToolDetail.tsx      # Full metadata + schemas + health check trigger
│   │   │   └── ToolSearch.tsx      # Capability keyword input
│   │   └── stats/
│   │       ├── StatsOverview.tsx   # Aggregate numbers (total tools, invocations)
│   │       ├── ToolStatsTable.tsx  # Per-tool metrics table
│   │       └── HealthCheck.tsx     # Single-tool health probe UI
│   └── pages/
│       ├── ChatPage.tsx            # Route: / (default)
│       ├── ToolsPage.tsx           # Route: /tools, /tools/:toolId
│       └── StatsPage.tsx           # Route: /stats
└── tests/
    ├── setup.ts                    # Vitest global setup
    ├── lib/
    │   ├── client.test.ts          # API client header injection, error mapping
    │   └── session-store.test.ts   # localStorage + fallback behavior
    └── components/
        ├── ChatInput.test.tsx      # Empty-message prevention, disabled-while-sending
        ├── MessageBubble.test.tsx   # Markdown rendering, metadata display
        ├── ErrorBanner.test.tsx     # Error message rendering
        └── ToolCatalog.test.tsx     # Search filtering, empty state

registry/
└── app.py                          # PATCH: add CORSMiddleware (FR-021)

tests/
└── contract/
    └── test_cors_contract.py       # Verify CORS headers on responses
```

**Structure Decision**: Add **`web/`** as the presentation layer root at the repository top level, peer to `agents/`, `conversation/`, and `registry/`. The frontend is a completely independent project with its own `package.json`, build pipeline, and test suite. The only backend change is a one-line CORS middleware addition to `registry/app.py`.

## Complexity Tracking

No constitution violations. The web UI is an additive, independently deployable layer.

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| — | — | — |

## Phase 0 & Phase 1 Outputs

| Artifact | Path |
|----------|------|
| Research decisions | [research.md](./research.md) |
| Frontend data model | [data-model.md](./data-model.md) |
| Consumed API contract | [contracts/frontend-api.md](./contracts/frontend-api.md) |
| Developer quickstart | [quickstart.md](./quickstart.md) |

**Agent context**: Updated via `.specify/scripts/bash/update-agent-context.sh cursor-agent` after this plan.
