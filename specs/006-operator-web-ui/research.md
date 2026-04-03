# Research: Operator Web UI

**Feature**: `006-operator-web-ui` | **Date**: 2026-04-03

## R-001: Frontend Framework Selection

**Decision**: Vite 6 + React 18 + TypeScript 5

**Rationale**: User-specified stack. Vite provides fast HMR and optimised production builds with zero-config TypeScript support. React 18 is the dominant UI library with the largest ecosystem for markdown rendering, testing, and routing. TypeScript adds type safety that pairs well with typed API contracts.

**Alternatives considered**:
- **Vue 3 + Vite**: Viable (user mentioned as option), but React has broader community momentum and more mature testing/markdown libraries.
- **Svelte + SvelteKit**: Lighter runtime, but smaller ecosystem for the specific needs (markdown, complex forms). User mentioned as option but didn't express preference.
- **Next.js**: SSR overkill for a thin client that consumes existing APIs. Adds unnecessary server complexity.

## R-002: CSS Strategy

**Decision**: Tailwind CSS 4 + CSS custom properties for design tokens

**Rationale**: User-specified. Tailwind's utility-first approach reduces custom CSS and enforces consistency. CSS custom properties provide a token layer (`--color-surface`, `--color-primary`, `--radius-md`, `--space-4`) that makes dark mode theming straightforward and allows future light-mode addition with a single class toggle on `<html>`.

**Alternatives considered**:
- **CSS Modules**: Good scoping but more verbose; harder to maintain consistency across components without a separate token system.
- **styled-components / Emotion**: CSS-in-JS adds runtime cost and doesn't integrate as naturally with Tailwind's utility ecosystem.
- **Vanilla CSS with BEM**: More control but no design-time guardrails; higher risk of inconsistency.

## R-003: Markdown Rendering

**Decision**: `react-markdown` + `remark-gfm` plugin

**Rationale**: `react-markdown` is the standard React markdown renderer (~3M weekly npm downloads). It uses a plugin architecture (remark/rehype) that allows GFM support (tables, task lists, strikethrough) via `remark-gfm`. It renders to React elements (not `dangerouslySetInnerHTML`), making it safe by default. Code blocks can be styled with Tailwind's `prose` typography plugin.

**Alternatives considered**:
- **marked + DOMPurify**: String-based; requires `dangerouslySetInnerHTML` and manual sanitisation. Unnecessary complexity.
- **MDX**: Allows embedded JSX in markdown — overkill for rendering assistant responses.
- **Custom parser**: No justification when a battle-tested library exists.

## R-004: Routing

**Decision**: React Router v6 (client-side routing)

**Rationale**: Three routes (`/`, `/tools`, `/stats`) with one nested route (`/tools/:toolId`). React Router v6 is the standard for React SPAs, lightweight, and supports lazy-loaded routes for code splitting. No SSR or file-system routing needed.

**Alternatives considered**:
- **TanStack Router**: Type-safe routing but adds unfamiliar API surface for a simple 3-route app.
- **No router (conditional rendering)**: Would work but loses URL-based navigation, browser back/forward, and deep linking.

## R-005: HTTP Client Strategy

**Decision**: Native `fetch` with typed wrapper functions in `lib/api/`

**Rationale**: The browser's built-in `fetch` API is sufficient for this client. A thin wrapper adds: (1) automatic `Authorization: Bearer <principal_id>` header, (2) `X-Trace-ID` UUID generation per request, (3) `X-Session-ID` header, (4) response type parsing and error mapping, (5) centralised error handling. No need for axios — it adds a dependency for features we don't use (interceptors, progress events, cancellation beyond AbortController).

**Alternatives considered**:
- **axios**: Adds ~15KB gzipped for no measurable benefit in this use case.
- **ky**: Lighter than axios but still an unnecessary dependency when fetch + a 50-line wrapper covers all requirements.
- **TanStack Query (React Query)**: Considered for caching and refetching — would be valuable if the app grew, but for v1 the data flows are simple enough that React state + custom hooks suffice. Can be added later without architectural changes.

## R-006: State Management

**Decision**: React `useState` + `useContext` (no external library)

**Rationale**: The app has minimal shared state: (1) session context (session_id, principal_id) — provided via React Context, (2) turn history — local state in ChatPage, (3) tool data — local state per page, fetched on mount. No cross-page state sharing beyond session identity. Adding Redux, Zustand, or Jotai would be over-engineering.

**Alternatives considered**:
- **Zustand**: Clean API, but the state surface is too small to justify a dependency.
- **Redux Toolkit**: Heavyweight for 2-3 pieces of shared state.
- **Jotai**: Atomic model is elegant but unnecessary for this scope.

## R-007: Testing Strategy

**Decision**: Vitest + @testing-library/react (unit/component); Playwright optional for e2e

**Rationale**: Vitest is Vite-native (shared config, fast HMR-aware test runner). @testing-library/react encourages testing from the user's perspective (render → query → assert). Contract tests verify that API client functions handle response shapes correctly. Playwright is recommended for e2e but not mandatory for v1 — the API layer is already tested server-side.

**Alternatives considered**:
- **Jest + RTL**: Would work but requires separate Babel/TS config that duplicates Vite's. Vitest is the natural pairing.
- **Cypress**: E2E focused but heavier to set up and slower in CI than Playwright.

## R-008: CORS Backend Change

**Decision**: Add `CORSMiddleware` to `registry/app.py` with configurable `CORS_ORIGINS` environment variable

**Rationale**: The Vite dev server runs on `localhost:5173` while the API runs on `localhost:8000`. Without CORS, all browser fetch calls are blocked. FastAPI's `CORSMiddleware` is a single `add_middleware` call. The allowed origins should be configurable via environment variable (`CORS_ORIGINS`) with a sensible default (`http://localhost:5173`) for local development. Production deployments set the actual origin.

**Alternatives considered**:
- **Vite proxy**: Would forward `/api/*` through Vite's dev server. Avoids CORS in development but doesn't solve production deployment and masks the actual request origin. The CORS approach works for both dev and prod.
- **Same-origin deployment**: Serve the built frontend from FastAPI's static files. Possible but couples the frontend build to the backend deployment pipeline, violating layered independence.

## R-009: Session / Principal ID Management

**Decision**: Generate a UUID v4 as `principal_id` on first visit; store alongside `session_id` in localStorage. Use `principal_id` as the Bearer token.

**Rationale**: The server's session API requires `Authorization: Bearer <principal_id>`. The Bearer value is not a JWT — it's an opaque string used as the session owner's identity. Generating a UUID on first visit and persisting it creates a stable "device identity" without any login flow. The same principal_id is reused across sessions so the server can associate all sessions from this browser (though the UI only exposes one at a time).

**Alternatives considered**:
- **Use session_id as principal_id**: Would break the server's ownership model (principal_id is the owner, session_id is the conversation).
- **Prompt the operator for an identifier**: Adds friction for zero security benefit in a no-auth system.
- **Random per-session**: Loses the ability to trace all activity from one browser instance. The persistent UUID is more useful for observability.

## R-010: localStorage Fallback

**Decision**: Wrap localStorage access in a `SessionStore` abstraction; fall back to an in-memory `Map` if localStorage throws.

**Rationale**: Some browsers in private/incognito mode throw on `localStorage.setItem`. The UI should still work for the current tab — just without cross-session persistence. The abstraction also makes testing trivial (inject a mock store).

**Alternatives considered**:
- **sessionStorage**: Persists per-tab but not across tabs or restarts. Doesn't meet FR-002 for normal browsers.
- **IndexedDB**: Overkill for storing 2-3 string values.
- **Crash on localStorage failure**: Poor UX; violates the accessibility and resilience intent.

## R-011: Component Architecture

**Decision**: Three-tier component structure: `ui/` (primitives), feature modules (`chat/`, `tools/`, `stats/`), `pages/` (route entry points)

**Rationale**: User-specified component discipline. Primitives (`Button`, `Card`, `Input`, `Layout`, `EmptyState`, `ErrorBanner`, `Skeleton`, `Badge`) are styled with Tailwind + design tokens and reused across features. Feature modules compose primitives into domain-specific UI. Pages are thin route wrappers that compose feature modules and manage data fetching.

**Alternatives considered**:
- **Flat component directory**: Doesn't scale and makes dependency direction unclear.
- **Feature-first (co-located routes + components)**: Viable for larger apps but overkill for 3 routes; the current split is clear enough.
