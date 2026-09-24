# P1 + E1 — Identity, Authentication, Authorization & Platform Foundation

Capstone implementation story. This phase replaced the transitional development
identity with a durable, secure account foundation and laid the minimum platform
foundations (roles, entitlements, workspace-role contract, audit, privacy lifecycle)
that later phases depend on — **without** rebuilding the product or removing any
existing capability.

Base: `main` @ `29a7730` (P0/E0 merged, PR #73). Branch:
`feature/capstone-p1-e1-identity-platform`. No historical tag moved.

---

## 1. The problem P1 solved

Before P1, identity was a **transitional** boundary: the backend trusted an
`X-User-Subject` header (`src/api/dependencies.py`), which a trusted gateway or a test
supplied, and resolved it to an internal `users.id` via `get_or_create_user`. There
were **no accounts**: no registration, no passwords, no email verification, no
recovery, no sessions, no social login, no platform roles, no product entitlements,
no audit log, and no account lifecycle. The frontend "identity" was an environment
variable (`NEXT_PUBLIC_DEV_USER_SUBJECT`) sent as that header.

That is fine for a single-tenant demo but unacceptable for a real product: a header
is user-controlled, so production identity cannot rest on it. P1 makes identity
**app-owned and trustworthy** while preserving every existing user-scoped record.

## 2. Why the previous X-User-Subject approach was insufficient

* **User-controlled.** A header can be set by any client; it is an identity *claim*,
  not proof. Production must derive identity from something the server issued.
* **No authentication.** There was nothing to prove a person owns an identity — no
  password, no verification, no session to revoke.
* **No platform concepts.** Roles, entitlements, workspaces, audit and account
  lifecycle did not exist, so nothing downstream (admin, teams, billing-ready tiers,
  privacy self-service) could be built.

## 3. What was implemented

### Data model (migration `0007_identity_platform`, single head)
The existing `users` table **remains the owner/principal** — every candidate resource
(`interviews`, `preparation_memories`, `user_feedback`, `interview_sessions`, agent
checkpoints) already references `users.id`, so **no owned row was re-keyed**. Added:

* `users.platform_role` / `users.status` / `users.email_verified` (safe defaults).
* `account_identities` — a login method (password / google / legacy) linked to a user;
  `(provider, provider_subject)` unique. Backfilled 1:1 from existing users.
* `password_credentials` — bcrypt hash, one row per user (never plaintext).
* `auth_sessions` — server-side sessions; PK is the **hash** of the opaque token.
* `auth_tokens` — single-use, expiring email-verification / password-reset tokens (hash only).
* `product_entitlements` — tier (`basic`/`premium`); backfilled `basic` for every user.
* `audit_events` — bounded security/privacy audit log (no secrets/content).

### Backend
* `src/authsec/passwords.py` (bcrypt, SHA-256 pre-hash removes the 72-byte limit),
  `src/authsec/tokens.py` (opaque tokens + at-rest SHA-256 hash).
* `src/auth_repository.py` — `AccountRepository`, `SessionRepository`, `TokenRepository`,
  `AuditRepository` (all `user_id`-scoped; foreign rows resolve to `None`).
* `src/application/auth_service.py` — `AuthenticationService`: register / login / logout /
  verify-email / forgot-password / reset-password / resolve-session / oidc-login.
* `src/application/authorization.py` — `Principal`, capability model, `is_platform_admin`,
  `has_capability`, `flag_enabled`; the workspace-role vocabulary (contract only).
* `src/application/oidc.py` — bounded Google OIDC provider + `is_safe_redirect`.
* `src/mail/` — `EmailSender` protocol with `Memory`/`Console`/`Brevo` adapters.
* `src/api/routes/auth.py` + `src/api/schemas/auth.py` — the `/auth/*` API.
* `src/api/dependencies.py` — session-cookie resolution, `get_current_principal`,
  `require_platform_admin`, `require_capability`.
* `scripts/bootstrap_admin.py` — controlled, audited platform-admin promotion.

### Frontend
* `components/auth/*` — `AuthProvider` (session context), `RouteGuard` (public/auth
  boundary), `AccountMenu` (header), and forms for sign-in / register / forgot / reset /
  verify / account.
* Pages: `/sign-in`, `/register`, `/forgot-password`, `/reset-password`, `/verify-email`,
  `/account`; API client sends the session cookie (`credentials: "include"`).

## 4. Why this architecture

* **`users` stays the principal.** The single most important legacy-preservation
  decision: because ownership everywhere is already `users.id`, keeping it as the owner
  means the migration adds tables/columns and backfills — it never moves candidate data.
* **Orthogonal concepts, never one overloaded `role`.** Identity (a login method),
  authentication (credential + session), platform role (`user`/`platform_admin`), product
  entitlement (tier → capabilities), workspace role (membership; contract only), feature
  flag, ownership and sharing are separate. This is what lets admin, teams and billing be
  added later without a rewrite.
* **Server-side sessions in an HttpOnly cookie.** No token in `localStorage`; only the
  token **hash** is stored, so a DB read yields no usable credential; logout/expiry/reset
  are enforced server-side.

## 5. How authentication works

1. **Register** → creates the user + password identity + credential + basic entitlement,
   emails a verification link, and returns a **uniform** message (no enumeration). It does
   not auto-sign-in.
2. **Login** → verifies the bcrypt hash (constant-time; a hash comparison always runs to
   keep timing uniform), opens a session, sets an HttpOnly/SameSite (Secure in prod) cookie.
3. **Session resolution** (`get_current_user_id`): a valid cookie is the trusted identity
   in every environment and always wins over the dev header; a present-but-invalid cookie
   is a 401 (never a silent downgrade).
4. **Verify / reset** use single-use, expiring, hash-stored tokens; reset revokes all
   sessions. **Logout** revokes the current session.

## 6. How authorization works

`get_current_principal` resolves the authenticated user to a `Principal`
(role + tier + status). `require_platform_admin` and `require_capability(...)` gate
role/entitlement-protected routes **server-side**. Object-level **ownership** stays
enforced in the data layer (every repository query is `user_id`-scoped), so a platform
admin is **not** a data superuser. Frontend `RouteGuard` is UX only — it never replaces
the server checks.

## 7. Roles vs entitlements vs workspace roles

* **Platform role** (`user` / `platform_admin`) — access to the future admin control
  plane. Not self-service; only `scripts/bootstrap_admin.py` grants it (audited).
* **Product entitlement** (`basic` / `premium`) — a capability set resolved server-side.
  BASIC keeps **every** capability that is free today (nothing is taken away in P1);
  PREMIUM is a strict superset with a single demonstration capability (`premium_preview`).
* **Workspace role** (`workspace_owner` / `workspace_member`) — membership-scoped, defined
  as a contract only; no workspace tables in P1 (Teams phase builds them).

## 8. How ownership is enforced

Unchanged and central: every read/write is scoped by `user_id` in the repository layer;
a foreign id resolves to not-found. Agent runs are owned via the LangGraph checkpoint's
stored `user_id`. P1 adds authentication in front of this; it does not weaken it.

## 9. How existing Sprint 4 data was preserved

Migration `0007` adds columns/tables and **backfills** one `account_identities` row per
existing user (copying its transitional `provider`/`subject`) and a `basic`
`product_entitlements` row — with **no** UPDATE/DELETE of candidate rows. Verified by
`tests/test_migration_0007_identity.py` (backfill preserves interviews/memory ownership;
upgrade → downgrade → re-upgrade is clean) and `scripts/eval_identity_platform.py`
(`legacy_data_preservation = 1.0`).

## 10. How development compatibility works

The transitional `X-User-Subject` header remains **development/test only**: honoured in
dev, **rejected in production** (only a session cookie authenticates there), and it can
never override a valid session. The anonymous dev fallback is unchanged for local work.
This keeps local development and the entire existing test suite friction-free while
production fails closed.

## 11. Security controls

bcrypt password hashing; opaque session tokens stored only as hashes; HttpOnly/SameSite
(Secure in prod) cookies; single-use expiring verification/reset tokens (replay-proof);
generic login errors and uniform register/forgot responses (no enumeration); server-side
role & entitlement enforcement; OIDC state (CSRF) validation + redirect allowlisting +
verified-email-only account linking; an audit log that stores no secret, token, hash,
prompt, chain-of-thought or candidate content; production dev-header rejection.

## 12. How it was evaluated

`scripts/eval_identity_platform.py` reports per-capability rates and **fails** if any
safety invariant is below 1.0. Latest run: authentication_flow 5/5, verification_recovery
6/6, cross_user_isolation 3/3, unauthenticated_rejection 2/2, production_dev_header_rejection
2/2, admin_rejection 1/1, entitlement_bypass_prevention 2/2, audit_safety 1/1,
secret_leakage_prevention 1/1, legacy_data_preservation 1/1 → **all safety invariants =
1.0**, paid/live calls = 0. Backed by the pytest security matrix
(`tests/test_auth_*.py`, `tests/test_migration_0007_identity.py`) and frontend/e2e
(`tests/auth.test.tsx`, `e2e/auth.spec.ts`).

## 13. What is intentionally deferred

Admin Console UI, Teams/workspace tables & UI, billing/payments, CV/document upload, OCR,
evidence/story bank, speech, multi-agent changes, the marketing website, and production
hosting. The **foundations** they need (roles, entitlements, workspace-role contract,
audit, account lifecycle) exist; the features do not. Full account hard-delete cascade
(including agent checkpoints) is a deletion-**request** boundary in P1 → classified
**PARTIAL** (see below).

## 14. What was learned / key decisions

* Keeping `users` as the principal turned a risky data migration into an additive one.
* Wiring auth dependencies through `Depends(get_repository)` made the whole stack
  override-friendly with the existing test seam — no bespoke test infrastructure.
* Live Google OIDC needs external configuration, so per the phase brief the provider
  abstraction + deterministic tests ship now and live Google is **UNVALIDATED**.
* `src/security` already existed (prompt-injection); the new package is `src/authsec`.

## 15. Known limitations (honest)

* **Full account deletion is PARTIAL** — P1 ships a deletion request (status flip + session
  revocation + audit); a complete cascade across all stores (incl. LangGraph checkpoints)
  is a later phase.
* **Live Google OIDC is UNVALIDATED** — exchanged only via a fake provider in tests.
* **Live email is not exercised** — the Brevo adapter exists but is never called without
  credentials + authorization; dev/test use the in-memory/console adapters.
* **No rate limiting yet** on auth endpoints (documented for the hardening phase).
* **Cross-site cookie note** — SameSite=Lax suits a same-site deployment; a truly
  cross-site frontend/API split needs SameSite=None+Secure (documented for hosting, P8).
