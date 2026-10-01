# P10B-W9.3 — Security / Menu Exposure Closure

Implementation record. Tightly bounded security/visibility remediation closing the Pilot finding
"Security Lapse on certain menu items." No migration, no new role model, no RC, 0 paid/live calls.

- **Baseline:** branch `fix/p10b-w9-2-recovery-ux` @ `c9cdff5` (W9.2). New branch
  `fix/p10b-w9-3-security-menu` from it. Ancestry intact (c9cdff5 ← 5984953 ← 334ffbd ← 80354f3).
  Alembic head `0014_opportunities` (unchanged). RC-P10-002 immutable; no RC-P10-003.

## 1. Original Pilot report

"Security Lapse on certain menu items." W9 audit classified it **LOW** — route visibility / limited
engineering information disclosure, **not** a demonstrated candidate-data authorization bypass.
Server-side ownership/admin authorization already passed the deterministic evaluators.

## 2. Pre-change surface inventory

**Internal/review frontend routes:** `/review` (index), `/review/agent` (Agent Inspector),
`/review/rag` (Knowledge & RAG), `/review/evaluation` (Evaluation). No other `/review/*`. Prompt Lab
is NOT exposed through candidate navigation (admin-only `/admin` + `/api/v1/reviewer/*`, already
gated).

**Navigation:** `SECONDARY_NAV` (`components/layout/nav-items.ts`) contained a `/review` item;
`MoreMenu` rendered `SECONDARY_NAV` unconditionally (so every authenticated candidate saw "Review &
Diagnostics") and already gated a hardcoded **Admin** link by `platform_role === "platform_admin"`.
Mobile bottom bar never showed these (primary-only). `robots.ts` already disallowed `/review`.

**Backend diagnostic endpoints (pre-change authorization):**
- `GET /api/v1/knowledge/diagnostics` — **no auth** (internal runtime counts + offline retrieval
  metrics). ← audit finding.
- `GET /api/v1/evaluation/latest|runs|runs/{id}|ragas/configuration` — **no auth** (offline
  evaluation diagnostics). ← audit finding.
- `GET /api/v1/knowledge/sources` + `/snapshot` — **no auth**, but **candidate-facing** (the Career
  evidence / Sources page). Correctly open.
- `GET /api/v1/agent/runs/{id}` — **owner-scoped** (`get_current_user_id`; 404 on foreign). Correct.
- `/api/v1/reviewer/*`, `/api/v1/admin/*` — already **router-level `require_platform_admin`**.

## 3. Authorization architecture used (and why)

Reused the **existing** server-authoritative `require_platform_admin` dependency
(`src/api/dependencies.py` → `src/application/authorization.is_platform_admin`) and the existing
`platform_role` on the account. No bounded "reviewer" capability exists in the model, and the sibling
reviewer router (`/api/v1/reviewer/*`) is already platform-admin-only, so platform-admin is the
smallest existing truthful boundary for internal diagnostics. **No new role, no capability, no
migration** (decision order D1→D3: no existing reviewer capability → no entitlement that fits without
schema change → use `platform_admin`). It is acceptable for internal Review/Diagnostics to be
platform-admin-only for the current candidate product.

## 4. Frontend navigation changes

- `nav-items.ts`: removed `/review` from `SECONDARY_NAV`; added `INTERNAL_NAV` = [Review &
  Diagnostics, Admin], a central platform-admin-only list.
- `MoreMenu.tsx`: renders `SECONDARY_NAV` for everyone and `INTERNAL_NAV` **only when**
  `platform_role === "platform_admin"` (one central predicate; replaces the hardcoded Admin block).
  Keyboard/aria menu semantics unchanged; no empty section/broken separators; desktop+mobile parity
  (both use the same `MoreMenu`). Candidate-facing items (Company, Documents, Workspaces, Sources,
  Help) unchanged.

## 5. Direct frontend route changes

New client guard `components/auth/RequirePlatformAdmin.tsx` (defense-in-depth): renders a neutral
loading state while the session resolves (no flash), a safe localized **"Access denied"** (403
semantics — not a network/server/"Something went wrong" error) for non-admins, and the children only
for a platform admin (so the gated client components never mount / never fetch for a candidate). It is
wrapped around `/review` (index), `/review/rag`, `/review/evaluation`. **`/review/agent` is
deliberately NOT gated** — it is the candidate's own owner-scoped Agent Inspector, reached from the
Coach's "View run details" (`AgentRunLink` in `AgentPrepareWorkspace`). Each gated page also sets
`robots: { index:false, follow:false }`.

## 6. Backend endpoint changes

- `src/api/routes/evaluation.py`: router-level `dependencies=[Depends(require_platform_admin)]` — all
  `/evaluation/*` now platform-admin-only.
- `src/api/routes/knowledge.py`: `/diagnostics` gains `dependencies=[Depends(require_platform_admin)]`.
  `/sources` and `/snapshot` **unchanged** (candidate-facing Career evidence).
- No change to `/agent/runs/{id}` (stays owner-scoped — platform admin does NOT become a private-data
  superuser).

## 7. Access matrix (proven)

| Surface | Anonymous | BASIC candidate | Platform admin |
|---|---|---|---|
| "Review & Diagnostics" nav item | absent | absent | visible |
| `/review` (index) | blocked (auth redirect / access-denied) | **access denied** | allowed |
| `/review/rag` | blocked | **access denied** | allowed |
| `/review/evaluation` | blocked | **access denied** | allowed |
| `/review/agent` (own trace) | auth redirect | **allowed (owner-scoped)** | allowed (owner-scoped) |
| `GET /knowledge/diagnostics` | **401/403** | **403** | **200** |
| `GET /evaluation/latest` | **401/403** | **403** | **200** |
| `GET /evaluation/runs` | **401/403** | **403** | **200** |
| `GET /evaluation/ragas/configuration` | **401/403** | **403** | **200** |
| `GET /knowledge/sources` + `/snapshot` (candidate) | open | **200** | 200 |

(Anonymous is 401 in production fail-closed; in dev/test the anonymous fallback resolves a non-admin
identity → 403. Both are "denied"; tests accept 401/403 for the unauthenticated case, as the existing
reviewer-API suite does.)

## 8. Agent-trace / privacy findings

`/review/agent` → `AgentInspector` → `GET /agent/runs/{id}` is owner-scoped (checkpoint ownership; 404
on foreign). It exposes only the caller's own **safe, observable** execution (tool calls + safe usage),
never other users' runs, checkpoints, graph state, prompts, hidden reasoning or raw provider content.
W9.3 **preserves** ownership and does **not** broaden admin access to private candidate data — a
platform admin requesting a run they do not own still gets 404 (test: `test_platform_admin_does_not_
bypass_owner_scoping_for_agent_runs`). Platform admin is not a private-data superuser.

## 9. Tests added

Backend `tests/test_review_diagnostics_authz_w9_3.py` (7): internal diagnostics reject
unauthenticated (401/403) and normal candidate (403); allow platform admin (200) + response shape;
candidate `knowledge/sources` + `/snapshot` remain 200; **no self-elevation** via forged
header/query; **workspace membership** does not grant diagnostics; **platform admin does not bypass
owner-scoping** for agent runs. (`test_api.py` evaluation data-shape check migrated here under the real
auth harness — `_FakeRepo` cannot resolve a principal.)

Frontend `tests/nav-security.test.tsx` (6): More menu shows Sources but not Review/Admin for a
candidate; shows Review + Admin for an admin; nothing for an unresolved account; `RequirePlatformAdmin`
blocks a candidate (access denied, children absent), renders children for an admin, and shows a neutral
loading state (no flash). `tests/shell.test.tsx` updated (candidate no longer sees Review).

## 10. E2E evidence

`e2e/review-access.spec.ts` (2): BASIC candidate — no Review/Admin nav item, direct `/review`,
`/review/rag`, `/review/evaluation` are access-denied, **but `/review/agent` stays accessible** (own
Agent Inspector); platform admin — Review nav item present, `/review` hub opens, child link present.
`e2e/navigation.spec.ts` Flow 3 (candidate does NOT see Review) + Flow 4 (admin: More → hub → Agent
Inspector) updated. `e2e/product-surfaces.spec.ts` review/rag + review/evaluation run as admin.

## 11. Evaluator results

All PASS, 0 paid/live: `eval_security` (prompt-injection attacks detected), `eval_platform_admin`
(GATE PASS), `eval_workspace_security` (GATE PASS), `eval_identity_platform` (safety invariants = 1.0),
`eval_multi_agent` (GATE PASS), `eval_release_candidate` (27/27), `eval_i18n_l10n` (PASS).

## 12. Test counts

- Backend: `tests/test_review_diagnostics_authz_w9_3.py` 7/7; full suite 13 failed / rest passed —
  the 13 are exactly the pre-existing `.env` `OPENROUTER_MODEL_*` artifact (5 files; isolated 0), **no
  W9.3 regression** (`test_api` returned to green after migrating the obsolete evaluation data-shape
  check). `ruff` clean.
- Frontend: typecheck clean, lint clean, **vitest 326 passed** (56 files; +6 nav-security), build 37
  pages.
- E2E: full Playwright **126 passed, 1 failed** — the single failure is a **pre-existing, unrelated
  flake** in `nextjs.spec.ts` ("home primary CTA navigates to Prepare"; home/Prepare hydration timing
  under batch load), which **passes 7/7 in isolation** and is untouched by W9.3. All W9.3 specs pass.

## 13. Security / privacy impact

- Internal engineering diagnostics are now server-authorized (platform-admin); the frontend hiding is
  defense-in-depth only. No authz/ownership/HITL/provenance weakening. Owner-scoping intact; admin is
  not a private-data superuser. No self-elevation via header/body/query/localStorage (server reads
  `platform_role` only). Dev-only `X-User-Subject` remains rejected in production. Candidate-facing
  Sources / Career Intelligence unaffected. The one new candidate-facing string (the "Access denied"
  title) was added to the i18n catalogue across all 7 locales — no new hardcoded-English debt.

## 14. Known limitations

- Internal Review/Diagnostics is platform-admin-only (no separate "reviewer" role) — acceptable for
  the current product; a bounded reviewer capability would be a future, migration-bearing change
  (deliberately out of W9.3 scope).
- `RequirePlatformAdmin` is a client guard (defense-in-depth); the authoritative boundary is the
  backend dependency, which is independently tested.
- Chrome strings on the gated pages remain English (full localization is W9.6); only the new access
  copy entered the catalogue.

## 15. Confirmations

- No migration. No new durable role model (reused existing `platform_role`/`require_platform_admin`).
- 0 paid/live provider calls. No RC created. RC-P10-002 immutable. W9.4 not started.

## 16. W9.4 handoff — Opportunity Discoverability

Next wave (per PILOT_FINDINGS PF-10 / UX_REMEDIATION §1): make Opportunity discoverable without
moderator instruction — add an Opportunity-first CTA on `/app` (`app/app/page.tsx`), add
`/opportunities` to the returning-user card (`components/home/ReturnJourney.tsx`), and give the
primary nav item real salience (darker default than `text-muted`, an icon; `PrimaryNavigation` +
`MobileNavigation`). No backend/schema change expected; reuse the existing Opportunities list/empty
state (already good). Keep `eval_opportunity_journey` green; add a discoverability E2E.
