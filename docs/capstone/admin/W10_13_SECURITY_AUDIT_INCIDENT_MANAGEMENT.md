# P10B-W10.13 - Security, Audit and Incident Management

**Status:** **W10.13 COMPLETE** - merged to `main` in PR #128 (feature head `44f8a7397c4cadf1df9c8f3b603dbaad7410ff29`, merge commit `b47a10b37219cfe51c117fa1b8d99c964a18c5ff`, 2026-10-05); Alembic head `0025_security_audit_incidents`; qualification used a **disclosed contamination with stable post-incident qualification baseline** (see section 54). ROLE-W10-01 remains deferred to W10.14. **W10.14 is NOT STARTED.**
One additive migration (`0025_security_audit_incidents`). No new dependency. 0 paid/live calls. Permission registry stays at 43. ROLE-W10-01 stays deferred to W10.14.

> SECURITY ADMINISTRATION IS NOT PRIVATE-CANDIDATE-DATA ACCESS. No break-glass, no impersonation, no CV / answer / chat / memory / document / prompt browsing. Audit history is not silently mutable. A role change never applies from one Admin alone. Step-up is password re-authentication, not MFA. Alerting is in-app only; nothing pages externally; no live security provider is called.

## 1. Starting main SHA
`4b09022add3db5996354b2bacde7ed82915b8979` (W10.12 complete and integrated; Alembic head `0024_reporting_analytics`).

## 2. W10.12 PRs / merge
Feature PR #126 (merge `18eebed64ff027b38546d6c135a7993f191fe2ef`); completion-docs PR #127 (merge `4b09022`). Documentation hygiene in this wave: the Feature flags row of the capability matrix still said "W10.11 NOT STARTED" and now says COMPLETE (PR #125). Nothing else was reworded, including the older W10.2 "complete when merged" text.

## 3. Branch
`feat/p10b-w10-13-security-audit-incidents`.

## 4. Current-state security audit (before any change)
| Capability | Current implementation | Authority | Persistence | Existing permission | Gap | W10.13 action |
|---|---|---|---|---|---|---|
| Password login success/failure | `AuthService.login` audits `account.login` (success/failure, actor if the account is known, request id, context `invalid_credentials`) | audit_events | durable | none (public) | no security view; no burst rule | project failures into Security Events; burst rule + alert |
| OIDC login | `account.oidc_login` success audit | audit_events | durable | none | code-present, not live validated | unchanged (documented limitation) |
| Password reset | `account.reset_request` / `account.reset_complete` audited | audit_events | durable | none | not visible to Security | projected as `password_reset` |
| Session revocation / deactivation | `admin.sessions_revoked`, `admin.account_status_change` (W10.2, same-transaction audit) | audit_events | durable | `users.sessions.revoke`, `users.manage` | not visible to Security | projected |
| Failed Admin authorization | `record_denial` writes `admin.access.denied` best-effort | audit_events | durable | n/a | no alerting | projected; denied-burst alert |
| Role change | `POST /admin/users/{id}/role` applied immediately for ONE authorised Admin | `users.role.assign` | user row + audit | `platform.users.role.assign` | **W10.2 gap reproduced: no second approver, no step-up** | replaced by a governed request/approval |
| Request ids / rate limiter | `X-Request-Id` on every audit row; in-memory limiter (Redis adapter present, not live) | audit/limiter | durable / process | none | none for step-up | new buckets reuse the limiter |
| Audit | `AuditEvent` row; `AuditRepository.record/recent/recent_for_actor`; `GET /admin/audit` already returned **cross-actor** events (not own-actor only) but unpaginated (limit <= 500), filtered by event type only, with no export; actor FK `ON DELETE SET NULL`; no update/delete API; **no DB protection** | `platform.audit.read` | durable | audit.read | no filters/pagination/export/DB guard | upgraded; export; triggers |
| Incident domain / alerts / `/admin/security` | none existed | - | - | - | all missing | built |

(The owner prompt mentions `/auth/admin/audit`; no such route exists - the only audit endpoint is `GET /admin/audit`.)

## 5. Security-event sources
A security event is a typed PROJECTION over `audit_events` (there is no second log): failed `account.login`, `account.reset_*`, `admin.access.denied`, the legacy `admin.platform_role_change` history, the new `admin.role_change.*`, `admin.sessions_revoked`, `admin.account_status_change`, `admin.step_up.*`, `admin.audit.exported`. A successful login is not a security event.

## 6. Anomaly semantics and limitations
Two deterministic code-defined rules over EXISTING audit rows for a KNOWN account in a rolling 15 minutes: `authentication_failure_burst` (>= 5 failed sign-ins) and `admin_access_denied_burst` (>= 5 denials). A failed login for an unknown email has no actor and is not grouped (no email/IP tracking was added to make it groupable). **Advanced anomaly detection is not implemented**; there is no classifier.

## 7. Security-event schema
`id, event_type, category, severity, actor_user_id, target_type, target_id, result, request_id, created_at`. `target_id` is an id or a permission name. The `context` JSON is never projected here.

## 8. Candidate-data boundary
No email, password, hash, token, IP, user agent, device, CV, answer, chat, document, prompt, model response, ticket body, support note, candidate query or raw exception appears in any W10.13 response. Guarded by tests and `scripts/eval_admin_security.py`.

## 9. Audit current-state gap
See section 4. The gap was filtering, pagination, export and database-level protection (not "global read", which already existed).

## 10. Audit global view
`GET /admin/audit` (`platform.audit.read`): global safe metadata. `context` is projected only for admin events (built by `build_audit`, which rejects secret/content keys), never for other writers.

## 11. Filters and pagination
`event_type`, `area` (account/admin/security/platform), `result`, `actor_user_id`, `target_type`, `request_id`, `period` (24h/7d/30d/90d/all); page size <= 100; order `created_at desc, id desc`. No free-text or context search, no arbitrary expression. The legacy `events` key is kept for compatibility.

## 12. Export semantics
`POST /admin/audit/export` (`platform.audit.export`, held only by the Security / Privacy Administrator; Platform Administrator can read but not export). CSV or JSON, columns `id, created_at, event_type, result, actor_user_id, target_type, target_id, request_id` (never `context`). CSV cells that start with `= + - @` are neutralised.

## 13. Export limits
A bounded `period` is mandatory (`all` is rejected), at most 90 days, at most 5000 rows (more -> 422 "narrow the filter", never silent truncation), an explicit reason of 8-200 characters, `Cache-Control: no-store`.

## 14. Export audit semantics
The snapshot is taken first, THEN `admin.audit.exported` is committed (actor, request id, filters, format, count, reason). A file therefore never contains its own export event (the next export does). If the audit write fails, no file is returned (fail closed). There is no self-expanding export.

## 15. Append-only database protection
Triggers on `audit_events` and `incident_events`: DELETE is rejected; UPDATE is rejected unless the ONLY change is `actor_user_id` going from a value to NULL. Installed by the migration and by `create_all` (so dev/test databases are protected too).

## 16. SQLite implementation
`BEFORE DELETE` / `BEFORE UPDATE ... WHEN NOT (all other columns unchanged AND NEW.actor_user_id IS NULL AND OLD.actor_user_id IS NOT NULL)` triggers raising `ABORT`. Verified on a freshly migrated database and a `create_all` database, including SQLite's FK `SET NULL` action.

## 17. PostgreSQL implementation and validation level
A `plpgsql` guard function plus a row trigger `BEFORE UPDATE OR DELETE` (JSON columns compared by text). The DDL is rendered and unit-checked in every run and the migration downgrade drops the trigger and function. **It was NOT executed against a live PostgreSQL** in this wave (`TEST_POSTGRES_URL` is absent); the optional disposable-Postgres path remains. We do not claim DBA grants exist or that the table is tamper-proof against a database owner/superuser, who can drop the trigger; production privileges are a deployment responsibility.

## 18. Account-deletion anonymisation exception
Mandatory regression: a user with audit rows is deleted through the real `POST /auth/account/delete`; deletion succeeds; the audit rows survive with `actor_user_id` NULL and every other field byte-identical; direct SQL UPDATE of another field and DELETE are blocked.

## 19. Incident schema
`admin_incidents` (public id, title <= 160, severity, status, affected service, started_at, resolved_at, owner_admin_user_id, affected_user_estimate >= 0, root_cause/remediation <= 1000, created_by, timestamps, revision >= 0; CHECKs including resolved-at consistency), `incident_events` (history), `incident_tickets` (links). No candidate identity list.

## 20. Severity and status lifecycle
Severity: low, medium, high, critical. Status: open, investigating, monitoring, resolved, closed. Transitions (code): open -> investigating | monitoring | resolved; investigating -> open | monitoring | resolved; monitoring -> investigating | resolved; resolved -> investigating (reopen, clears `resolved_at`) | closed; closed terminal. Resolving requires a recorded root cause OR remediation (no invented data to close). A closed incident cannot be edited.

## 21. Affected-service registry
Code-defined: authentication, agent, practice, research, documents, integrations, knowledge, jobs, billing, privacy, admin, platform. No URLs or hosts.

## 22. Incident content boundary
Title/root cause/remediation are internal operator text, never populated from candidate content, with the UI warning "Operational metadata only. Do not paste candidate content, credentials or secrets." Audit and history carry ids, enum before/after and the NAMES of changed fields, never the free text (tested with a sentinel).

## 23. Ticket-link semantics
Link/unlink by support-ticket public id only. Detail shows ticket public id, status and category - never subject, body, replies, notes or attachments. Duplicate link -> 409; unknown ticket -> 404; no ticket search.

## 24. Incident history
`incident_events`: action, prior/new status, actor, request id, safe meta (field names / ticket id). Append-only through the application and by DB trigger (the same narrow actor-anonymisation exception).

## 25. No-delete semantics
No Admin route deletes an incident (tested over the route table). An incident is closed. Status history is the append-only evidentiary stream; incident content itself is not claimed immutable.

## 26. Alert source audit
Real emission seams today: failed login (audit), Admin denial (audit), terminal background-job failure (`JobService.fail` / lease reaper).

## 27. Implemented alert categories
`auth_failure_burst` (high), `admin_access_denied_burst` (medium), `job_failed` (medium, one per job type).

## 28. Unsupported alert categories (not fabricated)
provider outage, error rate, failed payments, stale knowledge source, indexing failure, support SLA breach, deletion deadline, release evaluator failure, job backlog. They are listed by the API as `not_implemented`; no monitoring was invented.

## 29. Deduplication
One row per stable code-defined dedupe key (`auth_failure_burst:<account id>`, `admin_access_denied_burst:<account id>`, `job_failed:<job type>`). A recurrence increments `occurrence_count`/`last_seen_at` and bumps the revision; a recurrence of a RESOLVED alert reopens the same row. Keys contain no secret or candidate data.

## 30. Acknowledge / resolve
`platform.security.manage` only (security.read cannot mutate), `expected_revision` required (stale -> 409), same-transaction audit (failure rolls back). active -> acknowledged -> resolved.

## 31. In-app-only boundary
No email, SMS, pager, chat, webhook or external incident platform; guarded by a source scan and the evaluator. The Command Center shows safe counts only.

## 32. Old role-assignment behaviour
`POST /admin/users/{id}/role` applied the role immediately for one Admin (self-demotion and last-admin guards, same-transaction audit). Reproduced, then removed.

## 33. Role-request schema
`admin_role_change_requests`: public id, target, before_role, requested_role, requester, approver (nullable), status (pending, applied, rejected, cancelled, stale), reason (required), decision_reason, requested/decided/applied timestamps, revision. DB: requester != approver, requester != target, one pending request per target (partial unique index).

## 34. Second-approver rules
Approval is permission-based, not role-name-based: the approver must CURRENTLY hold `platform.users.role.assign` (re-read from the database), be active, and differ from requester and target. Only the Platform Administrator preset holds it; the Security / Privacy Administrator is not an approver.

## 35. Self / target prohibition
requester != target, approver != target, requester != approver; no Admin can request or approve their own role mutation.

## 36. Stale-request rule
At approval the target's CURRENT role is re-read. If it differs from `before_role`, or the requester is no longer an active authorised Admin, the request is marked `stale` (audited), nothing is applied and the call returns 409.

## 37. Transaction atomicity
Approval, the role update and the audit row commit in one transaction; an audit failure leaves the role unchanged and the request pending. Last-platform-admin guard re-checked inside it. Replay of an applied approval by the same approver is idempotent (no second mutation or audit row).

## 38. Step-up implementation
`POST /admin/step-up` verifies the CURRENT password against the stored hash and marks the exact server-side `auth_sessions` row elevated (`elevated_at`, `elevated_until`). No browser token, no storage. Required for creating AND approving a role change; a pending request does not keep elevation.

## 39. Step-up window
`STEP_UP_WINDOW_SECONDS = 300` (one constant). A revoked, logged-out or expired session, or a deactivated account, never authorises anything even if the elevation columns remain set.

## 40. Password semantics
Wrong password: generic `step_up_failed`, audit `admin.step_up.failed`, rate limited, no elevation. The plaintext is never stored, logged or audited (tested).

## 41. OIDC limitation
An account with no local password credential (OIDC-only) fails closed with `step_up_unavailable`. **OIDC step-up reauthentication is not validated in the Capstone**; an ordinary OIDC session is never treated as elevated. Dev-header/anonymous identities have no session and cannot step up.

## 42. No MFA claim
UI, API and docs say "Confirm your password to continue" and `method: password_reauthentication`. The boundary is MFA-ready; the implementation is not MFA.

## 43. Rate limiting
New buckets on the existing limiter: `stepup_user` 5/5 min, `role_request_user` 20/h, `role_approve_user` 30/h. Per-process unless a shared store is active; no distributed limiting is claimed live.

## 44. Direct-bypass closure
The old route is removed; no other route, service or repository caller in `src/api` changes a role (static test and evaluator). `AdminUserRepository.set_platform_role` and `AccountRepository.set_platform_role` remain as repository primitives for bootstrap/tests/guards only and are not reachable from any route.

## 45. Permission mapping
`platform.security.read` (events, alerts, incidents read, summary), `platform.security.manage` (alerts), `platform.incidents.manage` (incident writes), `platform.audit.read`, `platform.audit.export`, `platform.users.role.assign` (request, approve, reject, cancel, step-up). 43 permissions unchanged; no preset changed. Platform Administrator holds security.read but not manage/incidents/export.

## 46. ROLE-W10-01
Still deferred to W10.14.

## 47. Security UI
`/admin/security` with tabs Security events, Audit (with export dialog), Incidents (create, notes, transitions, ticket link, history), Alerts, Role approvals. English-only, permission-gated tabs, severity as text, labelled filters, captioned tables, focus-managed dialogs with Cancel first. The Users page now offers "Request role change" with a required reason and a step-up prompt. No accessibility certification is claimed.

## 48. Command Center integration
A small Security panel with active critical/high, acknowledged alert and open-incident counts and a link; not a second dashboard.

## 49. Audit events
`admin.role_change.requested|approved|rejected|cancelled|stale`, `admin.step_up.succeeded|failed`, `admin.audit.exported`, `security.incident.created|updated|status_changed|ticket_linked|ticket_unlinked`, `security.alert.acknowledged|resolved`. No historical event was renamed (`admin.platform_role_change` stays in history and in the security projection).

## 50. Migration
`0025_security_audit_incidents` (from `0024_reporting_analytics`): five tables, two `auth_sessions` columns, indexes, triggers. Nothing seeded. Downgrade drops triggers (and the PostgreSQL function) before tables/columns. The trigger DDL is frozen inside the migration.

## 51. Tests
`tests/test_security_w10_13.py` (65 tests: security events and thresholds, audit browse/export/limits/fail-closed, append-only triggers, account-deletion regression, incidents, alerts, step-up, the 20-point role-approval matrix, non-interference, migration/constraints/round trip, PostgreSQL DDL rendering), `frontend/tests/security-w10-13.test.tsx` (11), updates to the W10.1/W10.2/P6.5 role tests and evaluator for the governed flow.

## 52. Playwright
`frontend/e2e/security.spec.ts` (4 journeys, network-mocked): Security Admin events/audit/incident/alerts; read-only Admin without mutation controls; requester step-up then second Admin approval; requester has no Approve.

## 53. Evaluator
`scripts/eval_admin_security.py` (40 checks, in CI; 39 CI evaluators in total, all passing).

**Final qualification (exact tree, before the PR):** backend 3106 passed, 4 skipped (live Adzuna, disposable PostgreSQL, Streamlit context, RAGAS conditional), 0 failed; Vitest 756 passed; Playwright 221 passed; typecheck, lint, production build clean; i18n scanner 0 offenders; Ruff and compileall clean; 147 admin routes, 0 ungated; 43 permissions.

## 54. Isolation: qualification environment incident
Qualification runs use temp databases and pytest's own isolation (`tests/conftest.py` refuses any non-temp engine). The six protected stores were fingerprinted at the W10.13 start: dev DB `64d66596...`, checkpoint `b56d0c39...`, Chroma `6357c057...`, research cache `d6708df4...` (itself the disclosed post-W10.11 incident state), `evaluations/` `67259aba...`.

### Qualification environment incident
During development of `scripts/eval_admin_security.py`, one bare-Python evaluator run occurred before the evaluator isolation bootstrap. It inherited the developer `DATABASE_URL` and invoked ORM `create_all` against `data/interview_studio.db`.

Observed impact:
- dev DB fingerprint changed from the W10.13-start baseline (`64d66596...` to `8cd20d50...`);
- schema-object count changed from 141 to 224;
- only empty W10.12/W10.13 tables and the `incident_events` append-only triggers were added;
- existing user/audit data was verified read-only (11 users, 9 historical audit rows, no evaluator rows, every new table empty);
- checkpoint, Chroma, research cache and `evaluations/` were unchanged.

Correction:
- the evaluator now imports `tests.conftest` first;
- temp DB and no-dotenv isolation are mandatory;
- non-temp database engines fail fast.

Qualification interpretation:
- **the original W10.13-start dev-DB fingerprint was NOT preserved, and the dev-DB isolation gate failed once because of evaluator contamination;** the defect was corrected;
- the pre-wave dev-DB equality claim (pre-wave dev DB == post-wave dev DB) is NOT made;
- the current post-incident dev DB (`8cd20d50...`, 224 schema objects) is the disclosed qualification baseline; the owner accepted this baseline;
- the complete deterministic qualification after the correction (full backend, all 39 CI evaluators) left all six protected stores unchanged against that baseline;
- migration correctness was proven on isolated fresh/temp databases, NOT on the contaminated dev DB (which was never migrated or modified afterwards);
- no snapshot restoration was attempted and no claim is made that the dev DB was restored;
- 0 live/paid calls.

This is not "clean pre/post isolation". It is a disclosed contamination with a stable post-incident qualification baseline. W10.14 starts from the then-current protected-store baseline unless a separately approved environment-recovery operation happens outside qualification.

## 55. Manual QA
39 checks on a freshly Alembic-migrated temp database with two real Admin accounts (see the final report for the mapping).

## 56. Performance (50,000 audit rows, 2,000 incidents, 2,000 alerts, 299 pending requests; SQLite, median of 5)
audit page 1: 3 ms; deep page 500: 8 ms; filtered: 1 ms; security events (7d): 25 ms; anomaly rules: 4 ms; export snapshot: 1 ms; incident list: < 1 ms; alert list: < 1 ms; role-approval queue: < 1 ms. No index was added: none was justified at this size (the sort is served by the existing indexes with LIMIT).

## 57. Dependencies
None added.

## 58. Alembic head
`0025_security_audit_incidents` (single head).

## 59. Live-call count
0 paid or live calls.

## 60. W10.14 handoff
W10.14 resolves ROLE-W10-01, re-runs the whole Admin permission matrix and requalifies privacy, secrets, audit/security and route coverage together. Known limits to carry forward: PostgreSQL triggers not executed live; OIDC step-up unvalidated; no advanced anomaly detection; unsupported alert categories; universal operator search (W10.12/W10.13 matrix row) was not built in this wave.
