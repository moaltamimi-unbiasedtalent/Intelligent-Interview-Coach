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

## Requirement mapping (REQ-OWN-02, P1 to P8) and brief items
| ID | Covered | How | NOT covered |
|---|---|---|---|
| P1 edit draft versions, registered features only | Yes | Existing draft edit, now with code-defined bounds (`EntitlementDef.max_limit`, `premium_only`), bounds returned per entitlement and shown in the UI; unknown keys, wrong types and extra fields are 422 | Registry still has only 5 boolean keys: no limit key exists because OD-PLAN-LIMITS (the concrete limits and allowances) is still AWAITING. The limit machinery and its bound are tested with a test-only key |
| P2 enable/disable per plan, limits and allowances | Partly | Enable/disable: yes. Limits: the typed value, validation, bound and UI input exist; no limit key is registered | Any actual quota or allowance (owner decision OD-PLAN-LIMITS) |
| P3 clone/version, compare, preview candidate access | Yes | Create/clone draft (existing), matrix, two-version comparison, assignment preview (counts only: would change, already on, by current plan, entitlements gained/lost/limit changed). Preview-versus-actual parity test | "Candidate-access preview" is a count-level effect preview, never a per-candidate view |
| P4 assign users; Workspace entitlements | Yes | Single assignment (user or workspace) with subject revision, bulk assignment (1 to 100, one transaction, preview revision required), per-version assignment history (paged), per-subject history (50) | |
| P5 activate/retire, subscriber rights preserved | Yes | Unchanged immutability rules plus family-aware revisions; test that activation never moves a subscriber and the old version stays pinned | An "explicit migration decision" tool that moves subscribers between versions is not built (commercial migration tooling is R1.1); bulk assignment to the ACTIVE version is the explicit, previewed, audited mechanism |
| P6 immutable audit, safe rollback | Yes | Same-transaction audit on every mutation (bulk: one row per subject, rolled back with the assignment: tested by forcing an audit failure); rollback = `restore-as-draft` copies any earlier version into a NEW draft (history never edited, nobody moved, still activated through the normal path, `rollback_of` recorded in the audit) | |
| P7 enforced in backend, never frontend | Yes | Every rule is server-side; the UI only reflects. Explanation endpoint labels the real `EntitlementService` answer (parity test) | Enforcement of limits/history/model profiles stays behind the existing disabled code constants (not changed here) |
| P8 no billing path | Yes | `LIVE_BILLING_ENABLED` stays False (asserted); no 03B module imports billing code or reads/writes commercial terms; no price/currency/provider field in any response even when commercial terms exist (test inserts a terms row and sweeps eight responses); billing-word guard test on the new modules | |
| Brief: separation of authorization, capability, entitlement, billing state | Yes | Explanation response carries four labelled layers (only entitlement evaluated), UI shows them; billing never feeds entitlements | |
| Brief: two-person approval where existing rules require it | N/A | The only existing two-person rules are price changes and refunds (billing) and role changes; none governs plan activation, retirement or assignment, so none was added. Activation and assignment are single-actor, revision-protected and audited. If the owner wants a second approver for activation, that is a new rule (decision below) | |
| Brief: expected-revision protection | Yes, with one deliberate exception | Required on rollback, single assignment and bulk assignment (preview revision). Optional-but-enforced-when-supplied on the pre-existing create/patch/activate/retire/user-plan/workspace-plan shapes, because six existing callers (tests, e2e fixtures, evaluators) send none; the Admin UI always sends it | Making it mandatory on the legacy shapes would break those callers: see decision below |

## Changes
- New backend: `src/plan_revision.py` (derived revision tokens), `src/plans_admin.py` (matrix, compare, subject state, version history, explanation, assignment effect, bulk assign), `src/api/routes/admin_plans_ops.py` (9 routes), `src/api/schemas/admin_plans_ops.py` (strict allowlist schemas).
- Modified backend: `src/entitlements.py` (bounds fields, `check_plan_bounds`, `bounds_of`), `src/plans_repository.py` (revision checks, `restore_as_draft`, `assign_in_session` shared by single and bulk assignment, Premium-only guard on edit and activation), `src/api/routes/admin_plans.py` and `admin.py` (optional `expected_revision`), `src/api/schemas/admin.py` (additive `revision`, `family_revision`, `bounds`), `src/api/main.py` (router registered BEFORE `admin_plans`: its `/{version_id}` would otherwise capture the fixed paths).
- New routes (9): `GET /admin/plans/matrix|compare|explain|assignments/preview`, `GET /admin/plans/subjects/{type}/{id}`, `GET /admin/plans/versions/{id}/assignments`, `POST /admin/plans/versions/{id}/restore-as-draft`, `POST /admin/plans/assignments`, `POST /admin/plans/assignments/bulk`. Permissions: `plans.read`, `plans.manage`, `subscriptions.manage` only. The registry stays at 44.
- Frontend (Admin Plans components only): new `PlanMatrixPanel`, `PlanAssignPanel`, `PlanExplainPanel`; edited `PlansView`, `PlanDetailView`, `PlanControl`; `lib/api/client.ts` and `lib/admin/types.ts` additions (plan methods and types only). NOT touched: `AdminShell.tsx`, `capabilities.ts`, `nav-items.ts`, any app route or page.
- Tests: `tests/test_admin_plans_03b.py` (33), `frontend/tests/plans-03b.test.tsx` (14), `frontend/e2e/admin-plans-03b.spec.ts` (6).
- Existing tests/fixtures updated for the new contract (additive fields, strengthened not weakened): route count 9 to 18 in `tests/test_plans_entitlements_w10_4.py` and `scripts/eval_admin_entitlements.py` (same permission-set assertion, same ungated check); `frontend/tests/plans-w10-4.test.tsx` now asserts the revision argument on create/save/activate/retire/assign; `frontend/e2e/admin.spec.ts` plan fixtures gained the new fields and three routes; `frontend/e2e/fixtures/admin-responses.json` hand-patched (+130 lines: revisions and the recorded matrix shape; regenerating the whole file was rejected as too noisy).

## Security and privacy impact
- Every route uses `require_permission` with an existing permission; the 7-persona matrix (user + six presets) is exercised over HTTP for all nine new routes (403 for exactly the personas the preset expectations deny, no plan data in a denial; unauthenticated refused). The generic qualification matrix (`test_admin_qualification_w10_14`) also covers them and passes.
- Responses are strict allowlist schemas (`extra=forbid`), asserted by a schema test. Sentinel and banned-field sweeps: no email, price, currency, amount, provider, interval, token, secret, CV, document, answer, conversation, memory, transcript or prompt key in any plan response; a private memory sentinel and the account's email never appear.
- Preview returns counts only (never which accounts); history and explanation use ids and plan data only. Bulk is capped at 100 and de-duplicated.
- Mutations write their audit row in the same transaction; a forced audit failure rolled the whole bulk assignment back. Audit context carries plan codes, versions, ids, `bulk`, `batch_size`, `rollback_of`: no content.
- Authorization, capability, entitlement and billing state are separate and labelled; billing code is not imported by any 03B module.

## Tests and commands (observed)
| Check | Result |
|---|---|
| `tests/test_admin_plans_03b.py` | 33 passed (.venv) |
| 03B + `test_plans_entitlements_w10_4` + `test_admin_qualification_w10_14` | 86 passed (/tmp/ci_venv), 90 passed with `test_admin_foundation_w10_1` (.venv) |
| `ruff check .` | All checks passed |
| `scripts/ci_test_shards.py verify --shards 4` | OK: 282 test files, each in exactly one of 4 shards |
| All 46 CI evaluators (`scripts/eval_*` from ci.yml, /tmp/ci_venv) | 46 PASS after one fix: `eval_admin_entitlements` asserted exactly 9 plan routes (now 18, same permission set). 0 paid calls |
| Frontend `tsc --noEmit`, `npm run lint` | clean |
| Frontend `vitest run` (full) | 115 files, 1149 passed |
| Playwright (`E2E_PORT=3111`): `admin-plans-03b` (6), `admin` , `w11-visual-a11y`, `admin-navigation-03a` | 48 passed |
| Full backend suite (/tmp/ci_venv, `-n 3 --dist loadfile -qq`, counted from the progress lines) | 5589 passed, 43 skipped, 1 failed. The failure is `test_knowledge_persistence_02a_identity.py::test_no_forbidden_files_were_touched_and_no_migration_in_part_one`: it diffs against the stacked ref `origin/feat/02k-knowledge-contract` and flags `src/agent/{eval,judge,models,policies}.py`. Those four files already differ between that ref and this branch's BASE (`git diff --name-only origin/feat/02k-knowledge-contract origin/chore/migration-head-agnostic` lists exactly them) and this package touches no `src/agent` file (`git diff --name-only origin/chore/migration-head-agnostic` has none). So it is a stale-reference failure of that test on any branch based after 01B/01D, not caused by 03B; not fixed here because it is another package's test (lead decision) |
| `eval_doc_consistency.py` re-run after the evidence file was added; 03B + w10_4 tests under .venv | PASS; 63 passed |
Commands: `pytest tests/test_admin_plans_03b.py tests/test_plans_entitlements_w10_4.py tests/test_admin_qualification_w10_14.py -p no:cacheprovider` (both venvs), the evaluator list from `.github/workflows/ci.yml`, `cd frontend && npx tsc --noEmit && npm run lint && npx vitest run && E2E_PORT=3111 npx playwright test e2e/admin-plans-03b.spec.ts e2e/admin.spec.ts e2e/w11-visual-a11y.spec.ts e2e/admin-navigation-03a.spec.ts`.

## Migration
None. Reserved `0046` was not used; the Alembic chain is unchanged from the base branch (a test compares `migrations/versions` against the base ref and uses `tests/_alembic_head.py` for the dynamic single-head check).

## Risks and limitations
- Base: this branch is stacked on the UNMERGED `origin/chore/migration-head-agnostic`; merge that first or retarget.
- Revision tokens are derived hashes; they detect a change, they do not say what changed. The bulk preview token covers up to 100 subjects, so a large concurrent assignment elsewhere forces a re-preview (intended).
- Legacy-shape routes accept a missing revision (see mapping). Another admin using an old client could still overwrite without a check; the Admin UI cannot.
- Rollback only restores the entitlement values and display name of an earlier version; it does not move subscribers back (assignment is a separate, previewed step by design).
- The Basic-never-Premium-only rule is code-defined and applies on draft edit and activation. Existing stored data is not rewritten.
- No concurrency stress run: SQLite serialises writes; PostgreSQL row-lock behaviour of the `with_for_update` reads was not exercised (no PostgreSQL here).
- Not run: a live browser session against a real backend (Playwright is network-mocked by design); no paid or live call anywhere.

## Remaining human or operational evidence
- OD-PLAN-LIMITS (concrete limits and allowances) and OD-PLAN-ENFORCE decide what a limit key would be; none is invented here.
- Owner decision: should plan activation or bulk assignment need a second approver (new rule, not required by existing rules)?
- Owner decision: make `expected_revision` mandatory on the legacy plan routes once the remaining callers are updated.
- CI "not available until a PR exists"; PR and merge order are the owner's.

## Throughput
Start 2026-10-22 01:57 CEST. First push: see the final report (pushed after the last gate). Rework rounds: 3 (route count in two places, a GET-versus-POST audit-invariant clash for the preview, the view-as name guard) plus one fixture hand-patch.
SHA: see the final report.
