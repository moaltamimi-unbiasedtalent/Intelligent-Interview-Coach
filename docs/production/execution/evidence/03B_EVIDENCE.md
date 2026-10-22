# 03B Evidence: Admin Plans, Basic/Premium management (REQ-OWN-02)

Branch `feat/03b-admin-plans`, based on `origin/chore/migration-head-agnostic` (ec14963, the pushed PREP-HEAD branch that makes head-literal checks version-independent). That prep branch is NOT merged to `main` yet, so this PR must merge after it (or be retargeted onto `main` once it lands). Start time: 2026-10-22 01:57 CEST.

## Inventory and gap list (written BEFORE coding)

### What exists (W10.4, W10.5, W12)
- `src/entitlements.py`: code-defined `REGISTRY` of 5 BOOLEAN keys (no limit key, no invented quota), `PLAN_CODES = (basic, premium)`, `EntitlementService` (single resolver: active subscription, else Basic fallback, never fails open to Premium; keys missing from a version are denied), `seed_default_plans`, `ensure_default_subscription`.
- `plan_versions` (draft/active/retired, one active and one draft per plan code by partial unique index), `plan_entitlements`, `subscriptions` (user XOR workspace, one active each, history kept, pinned to a version).
- `src/plans_repository.py`: list, detail, create draft (copies latest), update draft, activate (retires the previous active, moves nobody), retire (default plan cannot be retired), single `assign` (ends old row, adds new, keeps legacy tier in step, audit staged in the same transaction), `subject_plan` (current + 20 history), `stats`.
- `src/api/routes/admin_plans.py`: catalogue, assignable, detail, create draft, patch draft, activate, retire (`plans.read`, `plans.manage`, `subscriptions.manage`); `admin.py`: `POST /admin/users/{id}/plan`, `POST /admin/workspaces/{id}/plan`.
- W10.5 mock billing: commercial terms live in separate tables, price changes use the two-person approval flow (`platform.plans.price.change`); `LIVE_BILLING_ENABLED = False`.
- Frontend: `PlansView` (catalogue + create draft), `PlanDetailView` (edit booleans, activate, retire), `PlanControl` (single-subject change + history).

### Gaps against REQ-OWN-02 P1 to P8 and the 03B brief
| # | Gap | Requirement |
|---|---|---|
| G1 | No entitlement matrix across versions, no side-by-side comparison of two versions | P3 |
| G2 | No code-defined bounds exposed or enforced (no max for limit keys; nothing stops Basic from carrying a Premium-only key, which would break "Basic is the least-privilege fallback") | P1, P2 |
| G3 | No expected-revision protection on any plan mutation (two admins can overwrite each other; activation can race another activation) | P6, brief |
| G4 | No safe rollback (a retired version cannot be restored as a new draft) | P6 |
| G5 | No preview of an assignment's effect (counts of subjects that change, entitlements gained and lost) | P3 |
| G6 | No bulk assignment of users or workspaces to a version; no stale-preview protection | P4 |
| G7 | No assignment history per plan version (only 20 rows per subject) | P4, P6 |
| G8 | No effective-entitlement explanation for a user or workspace (why a key is allowed or refused) | P7, brief |
| G9 | No explicit separation shown between authorization, capability, entitlement and billing state | brief |
| G10 | Existing assignment routes carry no expected revision; PlanControl cannot detect a concurrent change | brief |
| G11 | Frontend: no matrix/compare, preview, bulk assign, history, explanation, rollback or revision handling | brief |
| G12 | Two-person approval: existing rules require it only for price changes (billing, untouched). Plan activation/assignment have no existing two-person rule, so none is added (stated, not silently skipped) | brief |

Migration: none expected. Revisions are derived (hash of version content plus the family's lifecycle state; the active subscription id for a subject), so no schema change is needed. Reserved 0046 is NOT used.
