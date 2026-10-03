# P10B-W10.4 - Plans, Subscriptions & Entitlements

**Status:** **COMPLETE: merged to `main` in PR #116 (merge commit 787178d, qualified head abf2dbb; all required CI green).** **W10.5 and W10.6 are NOT STARTED; the next approved implementation wave is W10.6 (Integrations and API connections), not W10.5.**
One additive migration (`0016_plans_entitlements`). No new dependency. 0 paid/live calls. **No billing, no price, no invented quota.**

## 1. Starting point
`main` `c633375b1d5dee539bb64517187a681da3d78682` (W10.3 complete), clean tree, Alembic head `0015_support_ticketing`.

## 2. Branch
`feat/p10b-w10-4-plans-entitlements`.

## 3. W10.0 design alignment
W10.0 (master plan section 10) sketches `SubscriptionPlan -> Entitlements -> Usage Limits -> Billing Price -> User/Workspace Subscription` and a single `EntitlementService.resolve(user|workspace)` replacing the tier-to-capability map. Followed: plan, entitlements, subscription, one resolver. Deliberately deferred (owner brief): price, interval, currency, trial, visibility, support tier and usage limits that need metering, which belong to W10.5/W10.12. Not built: admin overrides and flags inside the resolver (no approved rule). Conflict reported: W10.0 lists plan creation with price and interval; W10.4 ships versioned plans without them.

## 4. Legacy tier audit
Code shows the loose tier logic was small and exact: `authorization.py` mapped tier to a capability set (`basic`: four capabilities that were already free; `premium`: those plus `premium_preview`) and `require_capability` enforced it on exactly two routes.
| Location | Behaviour | Access-affecting? | W10.4 action |
|---|---|---|---|
| `Capability` / `capabilities_for` / `has_capability` | tier to capability map | defaults only now | kept as the code defaults the registry mirrors; no route calls them |
| `POST /research/company` | `require_capability(current_market_research)` | **yes** | now `require_entitlement` |
| `GET /auth/premium/status` | `require_capability(premium_preview)` | **yes** (preview endpoint) | now `require_entitlement` |
| `/auth/me` `capabilities` | list from the tier | display/UX | now the enabled entitlement keys (same identifiers) |
| `AccountResponse.tier`, `Principal.tier`, admin user list `tier` | tier value | compatibility/display | kept; synced by the subscription domain |
| `AccountPanel` plan badge | `tier === "premium"` | display | replaced by a server-fed plan card |
| `POST /admin/users/{id}/tier` | wrote the tier | mutation | replaced by `/plan` (subscription change) |
| marketing pricing copy | static | docs/display | untouched (Premium stays a preview) |
Nothing else in the repository gated a feature by tier.

## 5. Four separate layers
Authorization (ownership, `require_permission`) answers who may do something; technical capability (`/capabilities`, provider flags such as `live_interview_enabled`) answers what the deployment supports and was NOT migrated; entitlement (this wave) answers what a plan grants; billing (W10.5) answers payment state and does not exist. A feature may later require capability AND entitlement AND authorization; each stays independently represented.

## 6. Domain model
`plan_versions` (plan code, version, display name, lifecycle), `plan_entitlements` (typed values per version), `subscriptions` (one subject pinned to one version, with history). Plan families are stable `plan_code`s; there is no separate family table because only the two real codes exist.

## 7. Plan and version lifecycle
`draft` (editable; one per plan code), `active` (immutable, assignable; one per plan code), `retired` (immutable, not assignable; subscribers stay pinned). Activating a draft retires the previous active version and moves nobody. The default plan (`basic`) cannot be retired because new accounts need an active default. Referenced versions are never deleted (FK `RESTRICT`).

## 8. Entitlement registry
Code-defined in `src/entitlements.py`: `current_market_research`, `standard_history`, `standard_progress`, `standard_model_profiles`, `premium_preview`, all boolean, identical to the pre-W10.4 capability identifiers. Admin input cannot add a key (registry validation plus a strict request body).

## 9. Limit semantics
One canonical form: `enabled=false` is disabled; `enabled=true, limit=null` is enabled and unlimited; `enabled=true, limit=N>=1` is a limit. `0` is never used (DB CHECK plus validation), floats and booleans are rejected, a boolean key takes no limit, a disabled key carries no limit. The model supports limit entitlements and the resolver returns them, but no limit key exists.

## 10. No invented quota
No quota, price or plan was invented: all five keys reflect access that already existed; no usage is metered and no remaining-usage counter is shown (broader metering belongs to W10.12).

## 11. Subscription lifecycle
`active` and `ended` only (no payment-like states). A change ends the old row (`ended_at`) and adds a new `active` row; history is kept. Sources: `system_default`, `migration`, `admin`: only those that exist.

## 12. User and workspace subjects
A subscription targets exactly one subject: `(user_id IS NOT NULL) XOR (workspace_id IS NOT NULL)` is a DB CHECK. One ACTIVE subscription per user and per workspace is enforced by partial unique indexes (PostgreSQL and SQLite) plus the service (the old row is ended before the new is added). Tested for both subject types and the duplicate cases.

## 13. Workspace scope
Workspace plans apply only to explicitly workspace-scoped resolution (`resolve(user, workspace_id=...)`). Membership never raises personal access and plans never combine ("highest plan wins" is not a rule). No current product route uses workspace scope, so workspace subscriptions are persisted and administrable without changing any candidate behaviour.

## 14. Effective entitlement resolver
`EntitlementService.resolve` / `resolve_all` / `enabled_keys` / `plan_summary` is the sole product-access authority; `require_entitlement(key)` is the route dependency (key validated at import). Output: `enabled`, `limit` (null with enabled means unlimited), plan code, version, source. A key a version does not list resolves disabled (deny by default).

## 15. Default and fallback semantics
No active subscription falls back to the Basic plan (the active Basic version, or the code default if the database has none). It never fails open to Premium: tested with a user whose legacy tier says premium but who has no subscription (resolves Basic).

## 16. Account-creation integration
Password and OIDC creation, and dev/legacy principals created by `get_or_create_user`, add the default Basic subscription in the same transaction as the account, so there is no half-created access state. If the default plan has no active version, creation fails closed (tested: no account row remains).

## 17. Legacy-user backfill
The migration seeds `basic` v1 and `premium` v1 and creates one active `migration` subscription per user from the current tier (premium to premium v1; basic or no tier row to basic v1). The entitlements equal the old map, so no user gains or loses anything. Tested from a populated 0015 database (premium, basic and no-tier users). Access equivalence is pinned by test: after the migration each user's enabled entitlement keys equal exactly what the pre-W10.4 tier map (`capabilities_for(tier)`) granted (premium user: five keys; basic and no-tier users: four).

## 18. Workspace backfill decision
No rows are created for existing workspaces: a workspace subscription is optional until used (documented section 13). Resolution for a workspace without one is the Basic fallback.

## 19. Legacy `tier` compatibility and deprecation
The `product_entitlements.tier` column is kept and unchanged by the migration. It is display/compatibility only and is written solely by the subscription domain (`PlanRepository.assign`); `AccountRepository.set_tier` is now a thin bridge to it, so there is one mutation path. No access decision reads it. Deprecation path: remove the column and DTO field once no client reads `tier` (a later wave).

## 20. Plan-assignment transaction
`POST /admin/users/{id}/plan` and `/admin/workspaces/{id}/plan`: validate, end the old subscription, add the new one, update the compatibility tier (users) and write the audit row in one transaction. An audit failure rolls back everything (tested for assign, create draft, edit, activate and retire).

## 21. Subscription history
Old rows are never overwritten: `ended_at` is set and a new row added. The detail pages and the candidate export show the history (plan, version, source, start, end); no payment fields exist.

## 22. Admin plan catalogue
`/admin/plans` (`platform.plans.read`): every version with lifecycle, enabled-entitlement count, subscriber counts and timestamps; detail with the typed entitlement table. Only the existing plan families can receive new versions (an unknown family is 422). Draft edit, activate and retire need `platform.plans.manage`; activation and retirement have confirmation dialogs (Cancel focused) and say nobody is moved or charged.

## 23. Admin user and workspace plan controls
User detail and workspace detail show the current plan, source, start and history, and (with `platform.subscriptions.manage`) a governed Change plan from the assignable active versions. Wording states that it is an access assignment, not a payment, and that a workspace plan never raises a member's personal plan.

## 24. Candidate plan display
Account shows "Your plan" from `GET /auth/plan` (server-resolved): the plan name and which features are included. Premium is labelled a preview with the notice "Premium is a preview. Ask4Mo does not currently offer purchases..." and "There are no payments, prices or invoices in your account." There is no button or link to buy or upgrade. 16 new keys plus one Data & Privacy line, in all 8 locales.

## 25. No candidate mutation
`/auth/plan` is GET-only (POST/PUT/PATCH/DELETE are 405); every subscription mutation is an Admin route behind a canonical permission. A candidate, a support operator and a preference-like payload cannot change a plan (tested).

## 26. Billing boundary
No provider, checkout, invoice, payment method, refund, webhook, tax, currency or billing-portal code exists. The evaluator scans the plan code, schemas and migration (comments and docstrings stripped) for those terms.

## 27. Pricing decision
No price is stored or shown (no price column, field or copy); the existing public pricing page is untouched. `platform.plans.price.change` stays unused until W10.5.

## 28. Export and privacy
The self-service export gains `plan` (current plan and own subscription history) and the scope line says "access assignments only; Ask4Mo has no payment records". Admin audit and plan configuration are not exported. PRIV-W9-01 and PRIV-W9-02 stay OPEN.

## 29. Account-deletion semantics
The user's own subscription rows are deleted with the account; plan definitions stay; a workspace the user merely belonged to keeps its subscription; a workspace deleted because its sole owner left has its subscription deleted with it. No FK failure (tested).

## 30. Audit events
`admin.plan_version_created`, `admin.plan_version_updated`, `admin.plan_version_activated`, `admin.plan_version_retired`, `admin.subscription_assigned` (replaces emitting `admin.entitlement_change`; the old constant stays for history). Payloads: plan code, version numbers, subject type and id, entitlement key names, assignment source, request id, actor. No payment data exists to record.

## 31. Permissions and routes
Existing canonical permissions only (registry unchanged at 43): `platform.plans.read` (catalogue, detail), `platform.plans.manage` (create draft, edit, activate, retire), `platform.subscriptions.manage` (assign user/workspace plan, assignable list). `platform_admin` gained plans.read/manage; `billing_admin` already held them. New privileged routes: 8 (seven plan routes and the workspace plan route; the user `/tier` route was replaced by `/plan`). **Current total 49 privileged routes, 49 permission-covered, 0 uncovered.**

## 32. Migration
`0016_plans_entitlements` (chains from 0015, reversible): three tables, CHECKs (lifecycle, source, XOR subject, limit form), unique `(plan_code, version)`, unique `(plan_version_id, entitlement_key)`, partial unique indexes (one active and one draft version per plan; one active subscription per user and per workspace), FKs (`RESTRICT` to plan versions, `CASCADE` from users, workspaces and versions). Seeds the two real plans and backfills subscriptions. The `tier` column is untouched. Tested fresh, from 0015 with backfill, every constraint, downgrade and round trip. SQLite and PostgreSQL both support the partial indexes used.

## 33. Backend tests
**2689 passed, 3 skipped, 0 failed, 0 errors** (`python -m pytest`, 241 s; baseline 2659/3). The 3 skips are unchanged (live Adzuna, Streamlit-context render, RAGAS). New `tests/test_plans_entitlements_w10_4.py` (30): registry, value rules, seeds, creation, fallback (never Premium; tier not authoritative), workspace scope, limit/unlimited/disabled/unlisted, catalogue, immutability and pinning, edit validation, retire rules, plan change and history, legacy bridge, audit rollback x5, audit payloads, entitlement gate, candidate views, no self-upgrade, permission matrix, export, deletion, Command Center, structure, migration. Existing guards and tests were updated for head `0016`, the `/plan` route and the replaced tier route.

## 34. Frontend tests
632 unit tests in 79 files (admin catalogue, draft edit, activation and retirement confirmation, read-only states, user and workspace plan control, candidate plan card with no purchase affordance, localized copy x8, no tier or role-name logic). Typecheck, lint, build and the hardcoded-English scanner (0 offenders) clean.

## 35. Playwright
**206 passed** (204 baseline plus the admin plans journey and the candidate account plan view), serial, no retries or timeout changes.

## 36. Evaluators
**31 of 31** pass, including the new `scripts/eval_admin_entitlements.py` (24 checks); `eval_admin_design` and `eval_admin_foundation` were updated for Plans as an operational destination and route.

## 37. Manual QA
Fresh migration from a populated 0015 database (a premium and a basic legacy user plus a dev principal): backfill mapped premium and basic correctly and the dev principal received the default subscription. The catalogue showed both active versions with counts. Operator actions: assign a plan (old row ended, history kept, tier synced), create and edit a draft, an edit of an active version was refused (409), activation retired v1 while both v1 subscribers stayed pinned, and each action wrote an audit row with a request id and no payment data. The candidate Account page showed the Basic plan, included/not included features and the preview notice with nothing to buy. Migration state matched.

## 38. Performance
First Load JS: `/admin/plans` 114 kB, `/admin/plans/[id]` 117 kB, `/admin/users/[id]` 118 kB, `/admin/workspaces/[id]` 117 kB, `/admin` 115 kB, `/account` 401 kB (candidate pages carry the locale catalogues), shared 103 kB (unchanged). The registry is not shipped to candidate pages (the server returns the resolved states). One extra small request on Account (`/auth/plan`) and one assignable-plans request on a user or workspace page for operators with `subscriptions.manage`.

## 39. Dependencies
None.

## 40. Alembic head
`0016_plans_entitlements` (single head).

## 41. Billing handoff (W10.5, later)
The approved order puts W10.6 next; W10.5 (billing, mock adapter) can later attach to stable `plan_versions.id` and `(plan_code, version)`, the canonical entitlement definitions, active subscription rows with history and sources (extend `source`), the Admin plan visibility and the resolver, plus the compatibility tier bridge. It must add price and interval as new tables or columns without changing resolution, keep billing state separate from entitlement, and label MOCK BILLING.

## 42. External calls
0 paid or live provider calls.
