# Quickstart: Operator Web UI

**Feature**: `006-operator-web-ui` | **Date**: 2026-04-03

## Prerequisites

- **Node.js** 18+ (LTS recommended)
- **npm** 9+ (bundled with Node.js 18+)
- **Backend running** on `http://localhost:8000` (see main project README / SETUP.md)

## 1. Install Dependencies

```bash
cd web
npm install
```

## 2. Configure Environment

Create `web/.env` (optional — defaults work for local dev):

```env
VITE_API_BASE_URL=http://localhost:8000
```

If the backend runs on a different host or port, update accordingly.

## 3. Start Development Server

```bash
cd web
npm run dev
```

The UI will be available at `http://localhost:5173`.

## 4. Backend CORS

The backend must allow cross-origin requests from the Vite dev server. Set the environment variable in the project root `.env`:

```env
CORS_ORIGINS=http://localhost:5173
```

Then restart the backend. Without this, all browser requests will be blocked.

## 5. Run Tests

```bash
cd web
npm test           # Run Vitest in watch mode
npm run test:ci    # Run once with coverage (CI mode)
```

## 6. Build for Production

```bash
cd web
npm run build
```

Output is in `web/dist/`. Serve with any static file server. Point the backend's `CORS_ORIGINS` to the production URL.

## 7. Lint & Format

```bash
cd web
npm run lint       # ESLint
npm run format     # Prettier (if configured)
```

## Key Development Notes

- **API types** are in `src/lib/api/types.ts` — these mirror the server's Pydantic schemas. If the server schemas change, update these types.
- **Design tokens** are CSS custom properties in `src/index.css`. Change colours, spacing, or radii there — components reference tokens via Tailwind's `theme()` or direct `var(--token)`.
- **Dark mode** is the default. The `<html>` element has `class="dark"` by default. To add a light mode toggle later, conditionally remove this class.
- **Session state** is managed by `useSession` hook. It handles auto-creation, localStorage persistence, and error recovery. Don't call the session API directly from components.
- **No proxy** — the UI calls the backend directly via CORS. There's no Vite proxy or BFF layer.

## Project Scripts (package.json)

| Script | Command | Purpose |
|--------|---------|---------|
| `dev` | `vite` | Start dev server with HMR |
| `build` | `tsc && vite build` | Type-check + production build |
| `preview` | `vite preview` | Preview production build locally |
| `test` | `vitest` | Run tests in watch mode |
| `test:ci` | `vitest run --coverage` | Single run with coverage |
| `lint` | `eslint src/` | Lint source files |
