# Ask4Mo Capstone — Target Architecture

Extends the Sprint 4 architecture; does not replace it. Preserve: one coherent candidate
experience, bounded agent, deterministic-where-deterministic, local-first governed knowledge,
explicit provenance, HITL for side effects, user-scoped data, server-side enforcement, safe failure.

## Layered view (target)
```
Public marketing routes (unauth)        ── Next.js (same app; route groups)
        │  Sign in / Register / Verify / Recover
Authenticated product routes  ──────────── Next.js App Router
        │                                    (candidate journey + Settings + Review)
Admin routes (PLATFORM_ADMIN) ──────────── Next.js (guarded)
        ▼
FastAPI /api/v1  ── auth middleware → identity → authorization (ownership + role + entitlement)
        ▼
Application services (src/application/*)  ── Streamlit-free boundary, reused by both UIs
        ▼
Domain: LangGraph agent (bounded) · deterministic Practice state machine ·
        Career Intelligence/RAG · research · memory · feedback-intelligence (offline)
        ▼
Persistence: SQLAlchemy (SQLite dev / Postgres prod, Alembic) · LangGraph checkpoints ·
        object storage (documents/audio) · knowledge stores (SQLite + Chroma)
        ▼
Providers (bounded, optional, fail-safe): OpenRouter (LLM) · STT/TTS · email · social IdP ·
        Adzuna · object storage · Langfuse (optional)
```

## Orthogonal concepts (never collapse into one `role` field)
| Concept | Question | Where enforced |
|---|---|---|
| Identity | Who is this person? | `users` + `account_identities` |
| Authentication | How was identity established? | auth middleware / session |
| Authorization | May they access this resource? | service layer (ownership + role + entitlement) |
| Platform role | Ordinary user or platform admin? | `users.platform_role` (USER / PLATFORM_ADMIN) |
| Workspace role | What may they do in a shared workspace? | `workspace_memberships.role` (OWNER / MEMBER) |
| Product entitlement | Which capabilities/limits? | `product_entitlements` (BASIC / PREMIUM) |
| Feature flag | Is a capability operationally enabled? | `feature_flags` (platform/env) |
| Consent | Authorised a specific data op? | `consent_records` |
| Ownership | Who owns this resource? | `owner_user_id` on every candidate resource |
| Sharing | Explicit grant of a private resource? | `share_grants` |

Authorization decision = ownership OR valid share, AND role permits, AND entitlement permits, AND
feature enabled. All checked server-side; frontend hiding is never the control.

## Frontend
Next.js 15 App Router, single deployment. Route groups: `(marketing)` public, `(app)` authenticated,
`(admin)` PLATFORM_ADMIN, existing `/review` reviewer/diagnostics. Preserve the Precision Coach
design system, the guided tutorial and Help. New surfaces: Register/SignIn/Verify/Recover,
onboarding/profile, Documents, Evidence/Stories, Workspaces, Sharing, Privacy/Data controls,
Premium presentation, Admin Console. Every surface must have a real data source.

## Backend
FastAPI thin layer over `src/application/*`. Add auth/session middleware, an authorization
dependency composing ownership+role+entitlement+flag, and route classes: PUBLIC, USER, WORKSPACE,
ADMIN, REVIEWER. Preserve `/api/v1` contracts and the OpenAPI contract test; extend, don't rename.

## Agent / orchestration
Keep the single bounded ReAct agent as the default. Introduce a **bounded orchestrator/specialist**
pattern only where an independent goal justifies it (see multi-agent assessment in the requirements
matrix / product model): Mo (supervisor) delegating to Research, Candidate, Preparation and
Evaluation specialists with typed hand-offs, per-run budgets, and deterministic Practice retaining
session authority. Specialists never own auth, permissions, migrations, billing or self-modification.

## Data
Preserve Sprint 4 tables; add account/identity/role/entitlement/workspace/share/document/evidence/
consent/audit tables (see `capstone_data_architecture.md`). Avoid duplicate persistence models.
Object storage for documents and audio (not the relational DB).

## Knowledge / RAG
Preserve the governed local-first RAG and deterministic router. Add K1–K4 datasets behind source
governance (lineage, review date, schema/version, rollback). Compare a new extension suite
separately from the frozen historical suite.

## Providers
See `capstone_provider_decisions.md`. Reuse OpenRouter; add STT/TTS, email, social IdP, object
storage, hosting — each optional, fail-safe, EU-aware, with local-dev + mock paths.

## Security
Server-side object-level authorization everywhere; extend the threat model to uploads, OCR/document
injection, cross-workspace access, entitlement/admin escalation, share revocation, deleted-data
resurrection, audio/transcript exposure (see `capstone_security_privacy_architecture.md`).

## Deployment
Single Next.js+FastAPI deployment with private staging first, then authorized public release with
HTTPS, verified-email registration, private storage, backups, health checks, per-user/global limits,
rollback and a costly-feature pause switch. No public launch without explicit owner authorization.
