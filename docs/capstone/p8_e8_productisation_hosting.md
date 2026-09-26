# P8 + E8 — Productisation, Public Surfaces & Hosted-Operation Readiness

_Capstone P8. The transition from a working product to a publicly-presentable, staging-
deployable one. Billing/payment stays OUT_OF_SCOPE (pricing PRESENTATION only). Not merged; no
public deployment; no paid/live provider calls. Companions:
[gap audit](p8_productisation_gap_audit.md), [claims audit](p8_public_claims_audit.md),
[hosting runbook](p8_hosting_operations.md)._

Baseline: `main` @ `32d1eeb` (P7.5 merged, PR #83); Alembic head `0011_workspaces_shares`
(no migration this phase); branch `feature/capstone-p8-productisation-hosting`.

## Why productisation
Ask4Mo had no public front door, no policy surfaces, no pricing, and no hosted-operation
controls (no auth rate limiting, no env validation, no security headers, no operator pause, a
soft-only account deletion). P8 adds a credible public site + the safety rails a hosted product
needs — while staying honest: hosting itself (EX-12) is BLOCKED/NOT RUN without an authorized
deployment.

## Public / app routing (§3)
`/` was the authenticated home. P8 makes **`/` the public marketing home** and **`/app` the
authenticated candidate home** (moved verbatim). A single `AppShell` now branches on the path:
marketing routes render `MarketingShell` (own header/footer, no app nav, no RouteGuard);
everything else renders the product chrome + `RouteGuard`. `MARKETING_ROUTES`/`isMarketingRoute`
live in `lib/auth/routes.ts`; the three `/` couplings (Brand link, post-login default,
auth-only fallback) now point to `APP_HOME` (`/app`). Compatibility: an authenticated visitor
on `/` sees a "Go to your workspace" link (no redirect loop); deep links to protected routes
are preserved; the tutorial invite + first step moved to `/app`. E2E: `route-migration.spec.ts`.

## Marketing website (§4/§5)
Public pages: Home, Product, Pricing, Trust, Privacy, Terms, AI transparency, About, plus
Sign in / Get started. Copy follows the [claims audit](p8_public_claims_audit.md): grounded,
private-by-default, "realtime available where configured", "in your language" — no outcome
guarantees, no "100% accurate / bias-free / GDPR certified". Built on the existing i18n + design
tokens + UI primitives.

## Pricing (§6/§7/§8)
Centralized in `lib/pricing.ts`. **Basic €0** (real free registration) and **Premium €19.99/mo
(indicative)** — a **preview request**, never a purchase (no checkout, card fields, or
"Buy now"). Annual price omitted (no owner-approved figure). Privacy/security/data rights are
always free on every plan (server entitlements unchanged; no new paywalls). `BILLING_ENABLED =
false` and a visible "no online payments" note.

## Trust / Privacy / Terms / AI transparency (§9–§12)
Trust lists factual engineering controls (isolation, explicit sharing, source provenance, human
approvals, no hiring decisions, no voice-trait inference, no audio storage, export/delete). The
three policy pages carry a visible **"engineering draft — pending legal review"** banner and are
grounded in the actual data inventory; Privacy explicitly states no audio is stored and that
backups age out per provider retention. No GDPR-compliance/certification claim.

## Data rights (§13/§14/§15)
The Account page is a coherent hub: export, Manage Memory/Documents/Sharing, and **permanent
account deletion**. `AccountDeletionService` (`src/application/account_deletion_service.py`)
removes every application-controlled resource in child→parent order (explicit deletes — SQLite
FK cascades don't fire and several tables aren't ORM-cascaded), purges **private files**
(document store) and **agent checkpoints** (per tracked run id), **anonymizes** audit
(actor→NULL, retained for security), transfers **owned workspaces** to another active member
(else deletes them, revoking co-member shares), and writes a final `account.deleted` audit
event. Authenticated, owner-scoped, idempotent. Endpoint `POST /auth/account/delete`. Eval:
`eval_account_deletion.py` (10 invariants incl. isolation + idempotency).

## Upload security (§16/§17)
`src/documents/file_security.py`: `FileSecurityScanner` seam (Null/Fake/ClamAV), fail-safe
policy in `enforce_scan` — when `MALWARE_SCAN_REQUIRED` and no real scanner is available,
uploads **fail closed (503)**; a flagged file is rejected (422); "clean" is never claimed
unless a real scanner ran. Wired into upload + replace. FakeScanner detects EICAR in CI.

## Auth hardening (§18/§24/§25/§26)
`src/api/rate_limit.py`: a shared limiter (in-memory sliding window) applied to register,
login, verify-resend, forgot, reset and OIDC-start — per-IP + per-account (hashed email,
existence-agnostic → no enumeration signal) + a global ceiling. Cookies stay HttpOnly +
SameSite=Lax + Secure-outside-dev; CORS is an explicit allowlist (never wildcard-with-
credentials); a `SecurityHeadersMiddleware` adds nosniff / Referrer-Policy / frame-ancestors /
Permissions-Policy (and HSTS in production). CSRF beyond SameSite + OIDC-state is documented as
a carried item.

## Cost / provider controls + pause (§19/§20/§21)
Per-user + global cost buckets on agent runs, uploads/OCR and realtime session creation
(`src/api/guards.py`). An **operator pause switch** (`src/application/pause.py`, admin
`GET/POST /admin/pause`) can pause realtime/current-market/OCR/agent/public-registration
without a deploy (audited; surfaced in `/capabilities` + `/admin/providers`). The limiter is
single-process (documented) — production multi-replica needs a shared store or a single replica.

## Environment validation + health/readiness (§31/§32)
`src/api/env_validation.py` differentiates development/test/staging/production and, in
production, **fails fast** (create_app raises) on missing FRONTEND_ORIGINS / non-SQLite
DATABASE_URL / APP_BASE_URL, or open registration without a real email provider. `/ready` now
performs a real DB + config probe (503 when not ready) with no provider calls; `/health` stays
a cheap liveness check.

## Hosting architecture & deployment (§29/§30/§33/§34/§35)
See [`p8_hosting_operations.md`](p8_hosting_operations.md). Single-replica staging: FastAPI +
uvicorn, Next.js, PostgreSQL, a private documents volume, Brevo email, optional realtime, Caddy
TLS edge. Artifacts: `deploy/Dockerfile.api`, `Dockerfile.web`, `docker-compose.staging.yml`,
`.env.staging.example`, `Caddyfile`, and `scripts/{migrate,backup,restore}.sh` (single-head
migration, pg_dump + storage tar backup, guarded restore). Rollback = image rollback +
forward-fix for destructive migrations (never auto-downgrade). Nothing is activated.

## SEO / accessibility / responsive (§43/§44/§45)
Root `metadataBase` + per-page canonical/OG; `app/robots.ts` disallows `/app`, `/admin`,
`/review` and the candidate routes; `app/sitemap.ts` lists marketing only; admin/review/app-home
carry `noindex`. Marketing uses semantic headings, keyboard-reachable controls, a mobile layout
with no horizontal overflow (asserted in `marketing.spec.ts`), and the shared skip link.

## Live providers (§35–§39)
Email, Google OIDC, realtime voice (C1/EX-02), Adzuna (K4), multilingual quality, OCR and RAGAS
all remain **UNVALIDATED** — a cost-gated live checklist is in the hosting runbook. No live call
was made. C1 stays PARTIAL / LIVE NOT RUN.

## EX-12 status
**BLOCKED / NOT RUN.** Per the acceptance rule, hosting cannot be certified from a local build.
Hosting **implementation** is READY (artifacts + env validation + limits + pause + backup/
restore/rollback docs + readiness probe), but EX-12 requires an authorized HTTPS deployment
exercising verified-email registration, private storage, limits, migration, backup/restore,
rollback and the pause switch. Public deployment is NOT AUTHORIZED by this phase.

## Evaluation & quality gates
New evals (all offline, 0 paid calls, in CI): `eval_account_deletion.py`, `eval_rate_limits.py`,
`eval_hosting_readiness.py`. New tests: `tests/test_p8_hardening.py` (12). New E2E:
`marketing.spec.ts` (8), `route-migration.spec.ts` (5). Gates green: backend **2381 passed / 3
skipped**; frontend **242 unit**, **104 e2e**; ruff / compileall / typecheck / build / lint /
secret-scan clean; Alembic single head unchanged.

## Known limitations
EX-12 not run; all live providers UNVALIDATED; rate limiter single-process; CSRF relies on
SameSite; policy/marketing copy is engineering-draft pending legal + human-translation review;
account-deletion checkpoint purge covers *tracked* run ids (untracked-run checkpoints are a
documented residual pending a saver-level/prod purge); DB FK cascade recommendation
(`PRAGMA foreign_keys=ON`) carried rather than applied mid-phase.

## Capstone lessons
Productisation is mostly about **honesty and boundaries**: a public site is only as good as the
claims audit behind it; hosting readiness is worth nothing if it pretends to be hosted; and the
safest deletion, rate-limit and pause designs are the ones that fail closed and are testable
offline. The hardest engineering (deletion cascade, fail-safe scanning, anti-enumeration limits)
is invisible when it works and catastrophic when faked.

---

## Release / legal-review status (§48)

| Surface | Engineering complete | Human copy reviewed | Legal reviewed | Publishable |
|---|---|---|---|---|
| Marketing (Home/Product/Pricing/About) | ✅ | ❌ | n/a | after human review |
| Trust | ✅ | ❌ | ❌ | after review |
| Privacy | ✅ (draft) | ❌ | ❌ | **no — legal review required** |
| Terms | ✅ (draft) | ❌ | ❌ | **no — legal review required** |
| AI transparency | ✅ (draft) | ❌ | ❌ | after review |
| Pricing (presentation) | ✅ | ❌ | ❌ | after review (no billing) |
| German / French / Spanish / Italian / Portuguese / Dutch translations | ✅ engineering draft | ❌ | ❌ | after human/legal review |

No review completion is invented. Human + legal review remain launch gates.

## Presentation evidence (§61)

**A. Product journey**
```
Public site (/)  →  Get started (/register)  →  verify email  →  Sign in  →  /app (candidate product)
```
**B. Trust**
```
Private by default → explicit sharing → governed AI + source evidence → human approvals → export / delete
```
**C. Hosting**
```
HTTPS (Caddy) → frontend + FastAPI → PostgreSQL + private storage → rate limits + pause + provider boundaries → backup → rollback
   (implementation READY; EX-12 hosted operation NOT RUN — needs authorized deployment)
```
**D. Commercial model**
```
Basic (€0, free)        Premium (€19.99/mo indicative, PREVIEW)
                 NO BILLING IMPLEMENTED (no checkout / cards / charging)
```
