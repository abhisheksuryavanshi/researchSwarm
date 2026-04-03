# Tasks: Operator Web UI

**Input**: Design documents from `/specs/006-operator-web-ui/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/frontend-api.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4)
- Include exact file paths in descriptions

## Path Conventions

- **Frontend**: `web/src/`, `web/tests/`
- **Backend** (CORS patch only): `registry/`, `tests/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the frontend project and apply the single backend change

- [X] T001 Scaffold Vite + React + TypeScript project in `web/` — run `npm create vite@latest` with React-TS template, creating `web/package.json`, `web/tsconfig.json`, `web/tsconfig.node.json`, `web/vite.config.ts`, `web/index.html`, `web/src/main.tsx`
- [X] T002 Install runtime dependencies — `react-router-dom`, `react-markdown`, `remark-gfm` in `web/package.json`
- [X] T003 [P] Configure Tailwind CSS 4 — install `tailwindcss`, `@tailwindcss/typography`, `postcss`, `autoprefixer`; create `web/tailwind.config.ts` and `web/postcss.config.js`; add Tailwind directives and design tokens (CSS custom properties for colors, radius, spacing, typography) to `web/src/index.css` with dark-mode-first defaults
- [X] T004 [P] Configure Vitest + Testing Library — install `vitest`, `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event`, `jsdom`; add `test` config to `web/vite.config.ts`; create `web/tests/setup.ts` with jest-dom matchers
- [X] T005 [P] Add CORSMiddleware to backend — add `CORSMiddleware` to `registry/app.py` reading `CORS_ORIGINS` env var (default `http://localhost:5173`), allowing headers `Authorization, Content-Type, X-Trace-ID, X-Session-ID, Idempotency-Key`; add `CORS_ORIGINS` to `.env.example`
- [X] T006 [P] Update `.gitignore` — add `web/node_modules/`, `web/dist/`, `web/.env`, `web/coverage/`

**Checkpoint**: Frontend project scaffolded, backend CORS-enabled, tooling configured

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T007 Define all TypeScript API types in `web/src/lib/api/types.ts` — interfaces for `CreateSessionResponse`, `TurnRequest`, `TurnResult`, `ToolSearchResult`, `ToolSearchResponse`, `ToolBindResponse`, `ToolHealthResponse`, `ToolStatsItem`, `ToolStatsResponse`, `ApiError`, `StoredSession` matching server Pydantic schemas (see data-model.md and contracts/frontend-api.md for exact fields and camelCase mappings)
- [X] T008 [P] Implement session store abstraction in `web/src/lib/session-store.ts` — `SessionStore` class wrapping localStorage with `get()`, `set()`, `clear()` methods for `StoredSession` under key `researchswarm:session`; generate `principalId` (UUID v4) on first access; in-memory `Map` fallback when localStorage throws; export `isStoragePersistent()` helper
- [X] T009 Implement base API client in `web/src/lib/api/client.ts` — `apiFetch<T>()` wrapper over native `fetch`; read `VITE_API_BASE_URL` from env; auto-inject `X-Trace-ID` (UUID v4 per request), `Authorization: Bearer <principalId>` (from session store), `X-Session-ID` (when session active); snake_case ↔ camelCase response key mapping; error normalisation to `ApiError` type per error mapping table in contracts/frontend-api.md
- [X] T010 [P] Create UI primitives — `Button` in `web/src/components/ui/Button.tsx` (variants: primary, secondary, ghost, danger; sizes: sm, md, lg; disabled state; focus ring); `Input` in `web/src/components/ui/Input.tsx` (text input with label, error state, disabled state); `Card` in `web/src/components/ui/Card.tsx` (container with design-token border, padding, radius)
- [X] T011 [P] Create UI primitives — `Badge` in `web/src/components/ui/Badge.tsx` (status colours: green, yellow, red, grey, blue); `Skeleton` in `web/src/components/ui/Skeleton.tsx` (pulsing placeholder for loading states); `EmptyState` in `web/src/components/ui/EmptyState.tsx` (icon, title, description, optional action button); `ErrorBanner` in `web/src/components/ui/ErrorBanner.tsx` (dismissible banner with `ApiError` display, retry action)
- [X] T012 [P] Create Layout shell and PageHeader in `web/src/components/ui/Layout.tsx` and `web/src/components/ui/PageHeader.tsx` — Layout: sidebar navigation (links to `/`, `/tools`, `/stats`) + main content area with `<Outlet/>`; PageHeader: title + optional subtitle + optional action slot; use semantic `<nav>`, `<main>`, `<header>` elements; dark-mode styling via design tokens
- [X] T013 Set up React Router + App shell in `web/src/App.tsx` — `BrowserRouter` with routes: `/` → `ChatPage`, `/tools` → `ToolsPage`, `/tools/:toolId` → `ToolsPage` (detail), `/stats` → `StatsPage`; wrap in `Layout`; lazy-load page components for code splitting
- [X] T014 Implement `useSession` hook in `web/src/lib/hooks/useSession.tsx` — provides `sessionId`, `principalId`, `isReady`, `error`, `createNewSession()`, `recoverSession()`; on mount: read from `SessionStore`, if no session call `createSession()` API; expose via `SessionContext` provider wrapping the app in `web/src/App.tsx`
- [X] T015 Implement `useApi` hook in `web/src/lib/hooks/useApi.ts` — generic data-fetching hook returning `{ data, loading, error, refetch }`; accepts fetch function + deps array; manages loading/error/data states; integrates with `ApiError` type

**Checkpoint**: Foundation ready — typed API layer, session management, UI primitives, routing all in place. User story implementation can begin.

---

## Phase 3: User Story 1 — Conversational Session (Priority: P1) 🎯 MVP

**Goal**: Operator can open the UI, auto-create a session, send messages, see markdown-rendered responses with full metadata, maintain turn history, and start new sessions.

**Independent Test**: Open the UI → session auto-creates → send a message → response appears with markdown rendering + metadata (intent, confidence, trace_id, degraded_mode) → send another message → both turns visible → click "New Session" → chat clears and new session ID appears.

### Implementation for User Story 1

- [X] T016 [US1] Implement session API functions in `web/src/lib/api/sessions.ts` — `createSession(principalId): Promise<CreateSessionResponse>` calling `POST /v1/sessions`; `postTurn(sessionId, principalId, message): Promise<TurnResult>` calling `POST /v1/sessions/{sessionId}/turns`; both use `apiFetch` from `client.ts`
- [X] T017 [P] [US1] Implement `SessionHeader` component in `web/src/components/chat/SessionHeader.tsx` — displays session ID (truncated with copy-to-clipboard), session status badge, "New Session" button (calls `createNewSession()` from `useSession`); shows skeleton while session is loading
- [X] T018 [P] [US1] Implement `ChatInput` component in `web/src/components/chat/ChatInput.tsx` — multiline text area with send button; disable send when input is empty/whitespace-only (FR-018); disable entire input while request is in-flight (FR-019); submit on Enter (Shift+Enter for newline); focus management with keyboard accessibility
- [X] T019 [P] [US1] Implement `TurnMetadata` component in `web/src/components/chat/TurnMetadata.tsx` — inline display of intent label, confidence percentage, trace_id (monospace, truncated), degraded_mode badge (yellow if true), route_mode and engine_entry when non-null; collapsible or compact by default
- [X] T020 [US1] Implement `MessageBubble` component in `web/src/components/chat/MessageBubble.tsx` — two variants: operator (right-aligned, muted background) and assistant (left-aligned, surface background); assistant messages rendered via `react-markdown` with `remark-gfm` plugin and Tailwind `prose` classes; includes `TurnMetadata` below assistant messages; timestamp display
- [X] T021 [US1] Implement `ChatView` component in `web/src/components/chat/ChatView.tsx` — composes `SessionHeader` + scrollable turn list (`MessageBubble` per turn) + `ChatInput`; manages `turns: Turn[]` state; on send: optimistically add user message, call `postTurn()`, append assistant response on success; auto-scroll to bottom on new turn; clear turns on "New Session"
- [X] T022 [US1] Implement `ChatPage` in `web/src/pages/ChatPage.tsx` — route entry at `/`; wraps `ChatView`; reads session from `useSession()` context; shows full-page loading skeleton while session initialises; shows `ErrorBanner` if session creation fails

**Checkpoint**: User Story 1 complete — operator can hold a full conversation with markdown rendering, metadata display, and session management. This is the MVP.

---

## Phase 4: User Story 2 — Tool Catalog Browsing (Priority: P2)

**Goal**: Operator can browse registered tools, search by capability keyword, and view detailed tool metadata including schemas.

**Independent Test**: Navigate to `/tools` → tool list loads → search by capability → results filter → click a tool → detail view shows schemas, endpoint, version → clear search → full list returns → empty search shows empty state.

### Implementation for User Story 2

- [X] T023 [US2] Implement tool registry API functions in `web/src/lib/api/tools.ts` — `searchTools(capability?, limit?): Promise<ToolSearchResponse>` calling `GET /tools/search`; `getToolBind(toolId): Promise<ToolBindResponse>` calling `GET /tools/{toolId}/bind`; `getToolHealth(toolId): Promise<ToolHealthResponse>` calling `GET /tools/{toolId}/health`; `getToolStats(toolId?, since?): Promise<ToolStatsResponse>` calling `GET /tools/stats`
- [X] T024 [P] [US2] Implement `ToolSearch` component in `web/src/components/tools/ToolSearch.tsx` — text input for capability keyword with debounced onChange (~300ms); clear button; result count display; uses `Input` primitive
- [X] T025 [P] [US2] Implement `ToolCard` component in `web/src/components/tools/ToolCard.tsx` — card displaying tool name, description (truncated), capabilities as `Badge` list, version, status badge (active/degraded/deprecated with colour coding), avg latency; clickable to navigate to detail; uses `Card` primitive
- [X] T026 [US2] Implement `ToolCatalog` component in `web/src/components/tools/ToolCatalog.tsx` — composes `ToolSearch` + grid of `ToolCard` components; fetches tools via `searchTools()` on mount and on search change; shows `Skeleton` grid while loading; shows `EmptyState` when no results
- [X] T027 [US2] Implement `ToolDetail` component in `web/src/components/tools/ToolDetail.tsx` — fetches tool via `getToolBind(toolId)` on mount; displays description, capabilities, endpoint, method, version; renders `args_schema` and `return_schema` as formatted JSON in `<pre>` blocks with syntax colouring; back navigation link; shows `Skeleton` while loading; shows `ErrorBanner` on 404
- [X] T028 [US2] Implement `ToolsPage` in `web/src/pages/ToolsPage.tsx` — route entry at `/tools` and `/tools/:toolId`; conditionally renders `ToolCatalog` (list mode) or `ToolDetail` (detail mode) based on presence of `toolId` param; wraps with `PageHeader`

**Checkpoint**: User Story 2 complete — operator can browse and search the full tool catalog with detail views. Works independently of chat.

---

## Phase 5: User Story 3 — Tool Statistics & Health Monitoring (Priority: P3)

**Goal**: Operator can view aggregated tool usage statistics and trigger real-time health checks on individual tools.

**Independent Test**: Navigate to `/stats` → aggregate summary loads (total tools, total invocations) → per-tool table loads with latency percentiles → filter by tool → stats update → navigate to tool detail → click "Check Health" → status badge shows result with latency.

### Implementation for User Story 3

- [X] T029 [P] [US3] Implement `StatsOverview` component in `web/src/components/stats/StatsOverview.tsx` — summary cards showing total tools, total invocations; uses `Card` primitive; shows `Skeleton` while loading
- [X] T030 [P] [US3] Implement `ToolStatsTable` component in `web/src/components/stats/ToolStatsTable.tsx` — sortable table with columns: tool name, invocations, success/error counts, error rate (colour-coded), avg/p50/p95 latency, last invoked, status badge; uses semantic `<table>` with `<thead>`/`<tbody>`; shows `Skeleton` rows while loading; shows `EmptyState` if no stats
- [X] T031 [P] [US3] Implement `HealthCheck` component in `web/src/components/stats/HealthCheck.tsx` — "Check Health" button; on click calls `getToolHealth(toolId)` and displays status badge (green healthy / yellow degraded / red unhealthy / grey unknown), latency, checked_at timestamp, error message if present; shows loading spinner during probe
- [X] T032 [US3] Implement `StatsPage` in `web/src/pages/StatsPage.tsx` — route entry at `/stats`; composes `StatsOverview` + `ToolStatsTable`; fetches stats via `getToolStats()` on mount; tool filter input and optional `since` date filter; re-fetches on filter change; wraps with `PageHeader`
- [X] T033 [US3] Add health check trigger to `ToolDetail` — integrate `HealthCheck` component into `web/src/components/tools/ToolDetail.tsx` below the tool metadata section

**Checkpoint**: User Story 3 complete — operator can view stats dashboard and health-check tools. Works independently of chat and catalog browsing.

---

## Phase 6: User Story 4 — Error Resilience & Session Recovery (Priority: P4)

**Goal**: All error paths produce friendly messages; stale sessions trigger recovery; degraded mode is clearly indicated; the UI never crashes or shows blank screens.

**Independent Test**: Stop the backend → all pages show `ErrorBanner` with friendly message → start backend with a fabricated session_id in localStorage → send a turn → "Session expired" message with "Start New Session" button appears → click it → new session created → send a turn → works.

### Implementation for User Story 4

- [X] T034 [US4] Enhance `useSession` with session recovery in `web/src/lib/hooks/useSession.tsx` — on `session_not_found` error from `postTurn()`: clear stored session, set error state with recovery action; expose `recoverSession()` that creates a new session and clears error; surface `isStoragePersistent` flag from session store so the UI can warn when localStorage is unavailable
- [X] T035 [US4] Add session recovery UI to `ChatView` in `web/src/components/chat/ChatView.tsx` — when `useSession` reports a `session_not_found` error: overlay the chat with an `ErrorBanner` showing "Your session has expired" with a prominent "Start New Session" button wired to `recoverSession()`; when `isStoragePersistent` is false: show a subtle info banner ("Session won't persist across visits")
- [X] T036 [P] [US4] Add global error boundary in `web/src/App.tsx` — React error boundary wrapping all routes that catches render-time exceptions and displays a full-page error state ("Something went wrong") with a "Reload" button; prevents blank screen on uncaught errors
- [X] T037 [P] [US4] Add network error handling to `ToolsPage` and `StatsPage` — ensure `ErrorBanner` is displayed on fetch failures in `web/src/pages/ToolsPage.tsx` and `web/src/pages/StatsPage.tsx` with retry action via `refetch()` from `useApi`
- [X] T038 [US4] Add degraded-mode indicator to turn display — in `web/src/components/chat/TurnMetadata.tsx` and `web/src/components/chat/ChatView.tsx`: when a turn has `degradedMode: true`, show a yellow warning badge and a brief explanation ("Response generated in degraded mode")

**Checkpoint**: User Story 4 complete — all error paths tested, session recovery works, degraded mode visible, no blank screens possible.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Accessibility, loading states, final validation

- [X] T039 [P] Verify keyboard navigation across all interactive elements — tab order through sidebar nav, chat input, send button, tool cards, tool search, stats table rows, health check buttons; visible focus rings on all focusable elements; Enter activates buttons/links; test in `web/src/App.tsx` and all page components
- [X] T040 [P] Verify loading/skeleton states on all pages — confirm `Skeleton` components appear during data fetches in `ChatPage` (session init), `ToolsPage` (tool list + detail), `StatsPage` (stats load); confirm `EmptyState` appears when data is empty
- [X] T041 [P] Write CORS contract test in `tests/contract/test_cors_contract.py` — verify `Access-Control-Allow-Origin`, `Access-Control-Allow-Headers` (including `X-Trace-ID`, `X-Session-ID`), and `Access-Control-Allow-Methods` headers on preflight `OPTIONS` and actual `GET`/`POST` requests
- [X] T042 Validate quickstart.md flow end-to-end — follow `specs/006-operator-web-ui/quickstart.md` from scratch: `npm install` → `npm run dev` → verify UI loads at `localhost:5173` → verify backend CORS works → send a chat message → browse tools → view stats
- [X] T043 Production build verification — run `npm run build` in `web/` and confirm `web/dist/` output serves correctly via `npm run preview`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — BLOCKS all user stories
- **User Stories (Phase 3–6)**: All depend on Phase 2 completion
  - US1 (P1) can start immediately after Phase 2
  - US2 (P2) can start after Phase 2 — independent of US1
  - US3 (P3) can start after Phase 2 — independent of US1/US2; T033 depends on T027 (ToolDetail from US2)
  - US4 (P4) depends on US1 (session recovery integrates into ChatView), but T036/T037 can be parallel
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **US1 (P1)**: Can start after Phase 2 — no dependencies on other stories
- **US2 (P2)**: Can start after Phase 2 — independent of US1
- **US3 (P3)**: Can start after Phase 2 — T033 (health check in ToolDetail) requires T027 from US2
- **US4 (P4)**: T034/T035 extend US1's session hook and ChatView; T036/T037 are independent

### Within Each User Story

- API functions before components that use them
- Leaf components (presentational) before composite components
- Composite components before page components

### Parallel Opportunities

- **Phase 1**: T003, T004, T005, T006 are all parallel after T001+T002
- **Phase 2**: T007+T008 parallel; T009+T010+T011+T012 parallel (all UI primitives); T014+T015 parallel after T009
- **Phase 3 (US1)**: T017, T018, T019 parallel (leaf components); then T020 → T021 → T022 sequential
- **Phase 4 (US2)**: T024, T025 parallel (leaf components); then T026 → T027 → T028 sequential
- **Phase 5 (US3)**: T029, T030, T031 parallel (leaf components); then T032, T033 sequential
- **Phase 6 (US4)**: T036, T037 parallel with T034/T035
- **Phase 7**: T039, T040, T041 all parallel

---

## Parallel Example: User Story 1

```text
# After Phase 2 foundation is complete:

# Step 1 — API layer (must be first):
Task T016: Implement session API functions in web/src/lib/api/sessions.ts

# Step 2 — Leaf components (all parallel):
Task T017: Implement SessionHeader in web/src/components/chat/SessionHeader.tsx
Task T018: Implement ChatInput in web/src/components/chat/ChatInput.tsx
Task T019: Implement TurnMetadata in web/src/components/chat/TurnMetadata.tsx

# Step 3 — Composite (depends on T017-T019):
Task T020: Implement MessageBubble in web/src/components/chat/MessageBubble.tsx

# Step 4 — Container (depends on T017, T018, T020):
Task T021: Implement ChatView in web/src/components/chat/ChatView.tsx

# Step 5 — Page entry (depends on T021):
Task T022: Implement ChatPage in web/src/pages/ChatPage.tsx
```

---

## Parallel Example: User Story 2

```text
# After Phase 2 foundation is complete:

# Step 1 — API layer (must be first):
Task T023: Implement tool registry API functions in web/src/lib/api/tools.ts

# Step 2 — Leaf components (parallel):
Task T024: Implement ToolSearch in web/src/components/tools/ToolSearch.tsx
Task T025: Implement ToolCard in web/src/components/tools/ToolCard.tsx

# Step 3 — Composite (depends on T024, T025):
Task T026: Implement ToolCatalog in web/src/components/tools/ToolCatalog.tsx

# Step 4 — Detail view (depends on T023):
Task T027: Implement ToolDetail in web/src/components/tools/ToolDetail.tsx

# Step 5 — Page entry (depends on T026, T027):
Task T028: Implement ToolsPage in web/src/pages/ToolsPage.tsx
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001–T006)
2. Complete Phase 2: Foundational (T007–T015)
3. Complete Phase 3: User Story 1 (T016–T022)
4. **STOP and VALIDATE**: Open UI → session auto-creates → send message → response renders with markdown + metadata → multiple turns accumulate → "New Session" works
5. Deploy/demo if ready — this is a fully usable research assistant interface

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → **MVP** — usable chat interface
3. Add US2 → Chat + tool browsing
4. Add US3 → Chat + tools + stats monitoring
5. Add US4 → Full error resilience hardening
6. Polish → Accessibility verification, build validation

### Parallel Team Strategy

With multiple developers after Phase 2 completes:

- **Developer A**: US1 (chat) — T016–T022
- **Developer B**: US2 (tools) — T023–T028
- **Developer C**: US3 (stats, starting T029–T032; T033 after B finishes T027)

US4 integrates after US1 is done (T034/T035 touch ChatView); T036/T037 are independent.

---

## Notes

- [P] tasks = different files, no dependencies on incomplete tasks
- [Story] label maps task to specific user story for traceability
- Each user story is independently completable and testable after Phase 2
- All file paths are relative to the repository root
- The only backend change is T005 (CORS middleware) — everything else is frontend
- T023 (tool API functions) serves both US2 and US3; placed in US2 since it's higher priority
- Total tasks: 43 across 7 phases
