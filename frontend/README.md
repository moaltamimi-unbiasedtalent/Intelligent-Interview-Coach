# Intelligent Interview Coach — Frontend (Next.js)

Production frontend **foundation** (Sprint 4 Phase 3B) implementing the selected
**Precision Coach** design system (see `docs/design/phase3a/`). It is a typed
client of the FastAPI backend (`/api/v1`). The Streamlit app keeps working
independently; both talk to the same application layer.

> Phase 3B builds the shell, design system, routes and API client foundation. The
> full Career/Preparation migration is **Phase 3C**. No LangGraph yet.

## Stack

Next.js 15 (App Router) · React 19 · TypeScript · Tailwind CSS · Vitest +
Testing Library · Playwright · ESLint.

## Develop

Two terminals — backend then frontend:

```bash
# Terminal 1 — FastAPI backend (repo root)
uvicorn src.api.main:app --reload            # serves http://localhost:8000/api/v1

# Terminal 2 — Next.js frontend
cd frontend
cp .env.example .env.local                   # optional; defaults are fine locally
npm install
npm run dev                                  # http://localhost:3000
```

`NEXT_PUBLIC_API_BASE_URL` (default `http://localhost:8000/api/v1`) points the
client at the backend. Only `NEXT_PUBLIC_*` values are read in the browser — no
server secrets ever reach the frontend.

## Scripts

```bash
npm run dev         # dev server
npm run build       # production build
npm run start       # serve the production build
npm run lint        # ESLint (next lint)
npm run typecheck   # tsc --noEmit
npm test            # Vitest component/unit tests
npm run e2e         # Playwright smoke (builds + starts, then runs)
```

## Structure

```
app/            App Router routes (home, prepare, practice, progress, history,
                sources, review/{agent,rag,evaluation}, settings) + globals.css
components/     layout · ui · coach · preparation · interview · feedback · diagnostics
lib/            api/{client,types,errors} · config · auth · utils · useCapabilities
tests/          Vitest component tests
e2e/            Playwright browser smoke
```

## Design system

Precision Coach tokens live as CSS variables in `app/globals.css` (light + dark)
and are exposed to Tailwind via `tailwind.config.ts` (`bg-background`,
`text-foreground`, `text-accent`, …). Dark mode follows the system preference and
an explicit header toggle (persisted per device); a no-flash inline script applies
the stored theme before paint.

## Notes

- **Auth** is a transitional seam only (`lib/auth.ts`); production OIDC/gateway is
  future work. The optional `NEXT_PUBLIC_DEV_USER_SUBJECT` maps to the backend's
  transitional `X-User-Subject` header for local data scoping.
- **Live** is only offered when the backend reports `live_interview_enabled`; it is
  never hardcoded on and no microphone/camera call is made on load.
