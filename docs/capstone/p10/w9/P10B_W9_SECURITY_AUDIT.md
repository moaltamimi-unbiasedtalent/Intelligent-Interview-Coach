# P10B-W9 — Security / Menu Audit

Audit phase. No runtime code changed. Pilot finding #5: one participant reported
*"Security Lapse on certain menu items."* This audits menu/route/API authorization across roles and
classifies the report.

---

## 1. Bottom line

The pilot's "security lapse on certain menu items" reproduces as a **route-visibility /
information-disclosure (UX) issue, NOT an authorization vulnerability.** Server-side authorization is
enforced and holds. The one concrete finding is that the **"Review & Diagnostics" (`/review`) menu
item is shown to every authenticated user**, and its two diagnostic sub-pages read **ungated aggregate
engineering endpoints** (KB counts, offline pass rates). No candidate-private data, no secrets, and no
admin data are exposed. Admin menu + all admin/reviewer APIs are correctly role-gated.

Deterministic corroboration (this session, all PASS, 0 paid/live): `eval_platform_admin`,
`eval_workspace_security`, `eval_multi_agent`, `eval_security` (prompt-injection detection).

## 2. Authorization matrix

### 2a. Navigation visibility (client)
| Menu | Component | Gate | Leaks privileged link? |
|---|---|---|---|
| Primary (opportunities, prepare, practice, progress, history) | `PrimaryNavigation.tsx:15`, `MobileNavigation.tsx:22` | logged-in | no (all BASIC owner-scoped) |
| More / secondary (company, documents, workspaces, sources, help, **review**) | `MoreMenu.tsx:103` maps `SECONDARY_NAV` unconditionally (`nav-items.ts:15-22`) | logged-in only | **yes — `/review` (dev/reviewer surface) shown to all** |
| Admin | `MoreMenu.tsx:27-28,124-136` | `platform_role === "platform_admin"` (server-provided; no flash) | no (correctly gated) |
| Account (settings, sign out) | `AccountMenu.tsx` | per-user | no |

### 2b. Client route protection
- No `frontend/middleware.ts`. Single component `RouteGuard` (`AppShell.tsx:80`) gates **auth vs
  unauth only** (`RouteGuard.tsx:25,36-52`) — not role-aware **by design** (documented `:6-9`);
  authorization is server-side. Unauthenticated → redirect to `/sign-in?next=…`.
- `/admin` renders then shows a 403-style UI for non-admins with **no admin API calls issued**
  (`AdminConsole.tsx:20-44`; covered by `frontend/e2e/admin.spec.ts`).
- `/review/*` renders for any authenticated user; data comes from the API (see 2d).

### 2c. Backend authorization (the real boundary — `src/api/dependencies.py`)
- `get_current_user_id` (`:573-632`): session cookie → dev-only `X-User-Subject` → anon dev fallback →
  else **401**. Production is **fail-closed** (`:631-632`); invalid cookie → 401, never downgrade.
- `require_platform_admin` (`:696-702`): 403 unless platform admin. `require_capability` (`:705-716`):
  403 unless entitlement present. Principal defaults to least privilege on lookup failure (`:668-675`).
- **`X-User-Subject` is dev-only** (`:31` `DEV_ENVS`, `:599`, `:611-619`), never overrides a valid
  session, rejected in production.

| Router | File | Gate | Cross-user |
|---|---|---|---|
| admin | `routes/admin.py:30-31` | **router-level** `require_platform_admin` | n/a |
| reviewer | `routes/reviewer.py:16` | **router-level** `require_platform_admin` | n/a |
| workspaces / shares | `routes/workspaces.py` | per-route id/principal; service enforces membership+ownership | 403/404 |
| opportunity | `routes/opportunity.py` | `get_current_user_id` | **404** on foreign |
| company | `routes/company.py:44-48` | id + `require_capability` + pause + cost | foreign JD → no text |
| documents/stories/reports | `routes/documents.py` | `get_current_user_id` | **404** on foreign |
| memory | `routes/memory.py` | `get_current_user_id` | **404** on foreign |
| feedback | `routes/feedback.py` | id + exact-target ownership verifiers | **404** |
| agent runs | `routes/agent.py` | id; ownership from checkpoint | **404** on foreign |

Owner-scoped resources return **404 (not 403)** on cross-user access (non-disclosure); role-gated ops
return **403**. Correct distinction.

### 2d. The two ungated diagnostics (the actual finding)
- `/review/evaluation` → `api.evaluation.latest()` → `routes/evaluation.py:20-31` — **no auth
  dependency**; returns aggregate offline RAGAS metrics.
- `/review/rag` → `api.knowledge.diagnostics()` → `routes/knowledge.py:20,56-59` — **no auth
  dependency**; returns KB counts + offline retrieval pass rates. Clients note no secrets/embeddings
  returned (`RagDiagnosticsClient.tsx:123-126`).
- `/review/agent` (Agent Inspector) is **owner-scoped** (`routes/agent.py:125-137`) — legitimately
  available.

`/review` and `/admin` are both in `frontend/app/robots.ts:24-25` disallow.

## 3. Attempted reproduction of the pilot concern

Reproduced deterministically at the code level: a normal authenticated candidate both **sees** the
"Review & Diagnostics" item in the More menu and can **load** engineering diagnostics (KB counts,
retrieval/RAGAS pass rates). This is aggregate, non-sensitive **system metadata** — no candidate-private
content, no secrets, no other user's data, no admin/`reviewer/*` content (those stay 403-gated and are
not linked from `/review`). This UX exposure is the most probable trigger of the pilot's report.

## 4. Classification

| Finding | Classification | Severity |
|---|---|---|
| F1 — `/review` menu item visible to all authenticated users | **route-visibility / UX** | Low |
| F2 — `/knowledge/diagnostics` + `/evaluation/latest` unauthenticated, reachable via `/review` | **information disclosure** (aggregate engineering metadata; no private data/secrets) | Low |
| F3 — Admin menu + `/admin` console | not a vulnerability (correctly gated) | — |
| F4 — Client `RouteGuard` auth-only, not role-aware | by-design / false-positive-as-vuln (server-side is the boundary) | informational |
| F5 — Owner-scoped routers | not a vulnerability (404-on-foreign) | — |

## 5. Release impact & remediation (W9.3)

- **No P0/P1 security defect.** Server-side authorization is enforced and fail-closed in production;
  the dev header cannot override a real session and is rejected outside dev/test.
- **Remediation (Low, do in W9.3):** gate the `/review` menu entry and the `/review/rag` +
  `/review/evaluation` pages (and ideally the `knowledge/diagnostics` + `evaluation/latest` endpoints)
  behind `platform_role`/a reviewer capability, mirroring the Admin item. Add a test asserting a normal
  user neither sees the `/review` menu item nor loads those two endpoints (401/403), and an E2E
  asserting no privileged nav item renders for a BASIC user.
- **Acceptance gate:** "security concern either fixed or conclusively classified" — classified here as
  route-visibility/info-disclosure (Low); W9.3 will additionally fix it. "No unauthorized menu/API
  access" — server-side already holds; W9.3 removes the residual dev-surface visibility.

Authorization must remain server-side enforced — it currently is, and W9.3 must not relax it.
