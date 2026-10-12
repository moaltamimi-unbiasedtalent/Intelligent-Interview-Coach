# W12.1 - Platform Admin owner / orchestrator: implementation record

**Status: IMPLEMENTED and qualified (deterministic, offline, 0 paid or live calls).** Owner decision **AD-W12-01** (`AD_W12_01_PLATFORM_ADMIN_OWNER_ORCHESTRATOR.md`) is now the CURRENT runtime: `platform_admin` holds all 43 canonical permissions. This is a code-defined preset change. No migration, no new permission, no role table, no custom role.

- Starting point: `main` at `9bd4baf8645a7e5a06e5c61e4814381cc8757d3c` (Pilot 2 P1 integrated qualification, PR #143, merged).
- Previous CURRENT runtime: `platform_admin` = **28 / 43** (W10.14 / ROLE-W10-01, preserved as history).
- New CURRENT runtime: `platform_admin` = **43 / 43**. Registry unchanged at exactly 43.
- Not done here (by instruction): Admin Owner Walkthrough, journey documentation, P10C, RC-P10-004. AC-24 stays PARTIAL.

## 1. The change
`src/application/admin_permissions.py`: `ROLE_PLATFORM_ADMIN: PERMISSION_SET` (the registry itself, no second hand-maintained list). `permissions_for_role` is unchanged: an unknown role, `None`, the empty string or the candidate (`user`) still resolves to the empty set. `BANNED_PERMISSION_FRAGMENTS` is unchanged. No route code changed: every privileged route is still `require_permission(...)`, and no code path checks the role name.

### The 15 permissions added (43 minus 28, verified exactly before the change)
`platform.audit.export`, `platform.billing.read`, `platform.billing.refund`, `platform.config.manage`, `platform.incidents.manage`, `platform.integrations.secret.rotate`, `platform.jobs.manage`, `platform.jobs.read`, `platform.knowledge.approve`, `platform.knowledge.manage`, `platform.legal.manage`, `platform.plans.price.change`, `platform.privacy.execute`, `platform.reports.commercial.read`, `platform.security.manage`.

### Specialist presets (unchanged; they gained nothing)
| Role | Before | After |
|---|---:|---:|
| platform_admin | 28 | **43** |
| support_operator | 7 | 7 |
| billing_admin | 10 | 10 |
| knowledge_admin | 6 | 6 |
| security_privacy_admin | 11 | 11 |
| operations_admin | 11 | 11 |

Each specialist set is a strict subset of the owner set. `platform.integrations.secret.rotate`, which no preset held under W10.14, is now held by `platform_admin` only.

## 2. What 43 / 43 does not mean
- **No private-content superuser.** No permission reads a CV, document, answer, Mo conversation, memory, evidence, report content or preparation chat; none was invented. Admin responses stay allowlist schemas and candidate repositories stay owner-scoped. No break-glass, no impersonation, no "view as user".
- **No role-name authorization.** The owner passes a route only because its resolved permission set contains the route permission.
- **Secondary governance is not bypassed.** Step-up (password re-authentication) is still required for the owner; a requester can never approve its own request (role change, price change, refund); a different active administrator holding the approve permission is required; stale target role, last-active-`platform_admin` protection, expected-revision checks and same-transaction audit are unchanged.
- **Authorization is not capability, entitlement or billing.** `secret.rotate` passes the gate but the environment SecretStore is externally managed and read-only (HTTP 409, no value echoed). `billing.refund` and `commercial.read` still operate on MOCK BILLING (labelled), never live billing or revenue. `config.manage` is still only the platform pause (no generic environment or secret editor). `knowledge.manage` still cannot index or activate unapproved knowledge (409, nothing reaches candidate retrieval). `privacy.execute` still changes request state through the existing service (no second deletion engine). `jobs.manage` still only manages code-defined job types.

## 3. Evidence and test changes
- `tests/_admin_matrix.py`: the historical 15-permission set is renamed `W10_14_PLATFORM_ADMIN_ABSENT` and is used only to assert the W10.14 record and the delta, never to derive current HTTP expectations (those come from the presets via `role_perms`).
- `tests/test_admin_qualification_w10_14.py` (a historical file name that is also a current CI module): the W10.14 least-privilege test is split into `test_ad_w12_01_current_runtime_platform_admin_owns_all_43_canonical_permissions` (current runtime) and `test_w10_14_historical_record_stays_28_of_43` (the W10.14 document must keep recording 28 / 43). New tests: the owner passes the secret-rotation gate but the store stays read-only; the owner cannot bypass step-up or approve its own role request.
- Existing tests that pinned platform_admin denial were updated to prove the same boundaries with the correct subject: billing, integrations, knowledge, platform config (pause, including a stale-revision refusal for the owner), privacy and legal, reporting, security (where the read-versus-manage separation is now proven with a test-only read-only preset because no shipped preset holds read without manage), and W11. Where the owner now succeeds, the tests also assert that the downstream rule still holds (no self-approval, state machine, mock label, revision).
- Evaluators: `eval_admin_qualification` (current 43 / 43 plus historical-record checks), `eval_w11_integrated` (`permissions_43_and_platform_admin_43`), `eval_admin_billing` and `eval_admin_security` (specialist subject for denial checks, owner positive checks). **`eval_rc_p10_003` semantic change:** RC-P10-003 is immutable and its manifest still records `platform_admin` = 28 / 43; the evaluator now asserts that historical manifest value (`rc_manifest_records_historical_platform_admin_28`) and separately that the CURRENT runtime is the AD-W12-01 owner (`current_platform_admin_is_ad_w12_01_owner_not_the_rc_time_preset`). The candidate SHA, artifact identity, release matrix identity and RC-time language identity checks are unchanged.
- Frontend: `frontend/tests/fixtures/admin-role-permissions.json` is regenerated from the backend; the Vitest destination test and a new Playwright test (`e2e/admin.spec.ts`, W12.1) prove that an account with all 43 permissions is shown every Admin destination (derived from permission strings only, no role-name special case), specialists keep their delegated destinations and the candidate sees none.

## 4. Results
| Check | Result |
|---|---|
| Permission matrix hash (43 x 7, derived from code) | `47bc35f2c5b1429b` (the old `dfe33b8da0bbdfe7` is the W10.14 historical value) |
| Admin routes, personas, route x persona cases | 147 routes, 7 personas, 1029 cases; every one of the 147 routes is allowed for `platform_admin` at the permission gate, and denial expectations for the candidate and each specialist are unchanged |
| Admin-related backend targeted suites | all pass after the updates (19 files) |
| Full backend `pytest` | 3,172 passed, 4 skipped, 0 failed |
| Vitest | 831 passed (93 files) |
| Typecheck, lint, production build | clean |
| Playwright (full, `E2E_PORT=3017`) | 272 passed |
| CI-safe evaluators (all 43 in `.github/workflows/ci.yml`) | all PASS |
| Migrations (temporary SQLite) | single head `0025_security_audit_incidents`; base to head, head to `0024_reporting_analytics`, back to head, head to base to head all succeeded; no developer DB |
| Private-content sentinels (candidate memory, answers, documents, reports planted; owner surfaces exercised) | none appear in any Admin response, audit payload, report or diagnostic (`test_privacy_and_secret_sentinels_never_appear_in_any_admin_surface` and the W11 sentinel suite) |
| Manual Admin QA (owner navigation at 1280 px with mocked data) | all 20 destination groups shown (billing, jobs, knowledge, privacy, legal, security, audit, integrations, configuration, flags, reports, AI, providers and the rest); labels stay truthful ("Mock billing (not live)", provider health "not tested"); no live external action was performed |
| Protected stores before and after | identical: dev DB `81eef3479704ed91e58abb876926f98108968842` (224 objects), checkpoint `b56d0c39fbba64786495ebb5db59eedecfae5c71`, Chroma `6357c057606273f313b408cc7f144390453a0832`, cache `25264b17b36f7a365ff8dfaca9eec97e997ee710`, evaluations `67259aba185daa495f8bf8958e1c905fd086b2be` |
| Paid or live calls | 0 |

## 5. Current versus historical audit of the old "28 / 43" wording
| Location | Classification |
|---|---|
| `docs/capstone/admin/W10_14_FULL_ADMIN_QUALIFICATION.md` | A. historical evidence, unchanged |
| `artifacts/capstone/p10/RC-P10-003/*` and `docs/capstone/p10/RC_P10_003_RELEASE_CANDIDATE.md` | A. immutable historical RC, unchanged |
| W10.7, W10.11, W10.12, W10.13 wave documents (ROLE-W10-01 sections) | A. historical wave records, unchanged |
| `ADMIN_CAPABILITY_MATRIX.md` (wave status rows) | A. historical status text |
| `docs/capstone/p10/pilot2/PILOT2_P1_REMEDIATION_QUALIFICATION.md` ("remains 28 of 43 for now") | A. historical: written before this wave |
| `ADMIN_PLATFORM_MASTER_PLAN.md` (ROLE-W10-01 section, role table), `ADMIN_ARCHITECTURE_DECISIONS.md` (ADR-16) | B. updated: amended or superseded for the current runtime, W10.14 text kept as history |
| `capstone_phase_plan.md`, `P10B_RELEASE_ACCEPTANCE_MATRIX.md` (R-56), `AD_W12_01_...md`, `CLAUDE.md` | B. updated to the current 43 / 43 rule, with the 28 / 43 history preserved |
| `tests/_admin_matrix.py`, `tests/test_admin_qualification_w10_14.py`, `scripts/eval_admin_qualification.py`, `scripts/eval_rc_p10_003.py`, `scripts/eval_w11_integrated.py` | B. updated; remaining mentions of 28 / 43 only assert the historical record |

No current roadmap, architecture statement or evaluator claims that `platform_admin` is still 28 / 43.

## 6. State after this wave
No RC was created or repinned (RC-P10-003 immutable, RC-P10-004 not created). AC-24 remains PARTIAL. The historical Pilot 2 verdict is unchanged. The Admin Owner Walkthrough, journey documentation and P10C have not started and remain next, in that order (see `capstone_phase_plan.md`).
