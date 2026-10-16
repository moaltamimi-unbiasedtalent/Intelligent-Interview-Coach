# W12.4D-P2-B: history, progress and artifact access entitlements

Status: **CODE QUALIFIED OFFLINE. Basic/Premium history and progress entitlements are implemented behind a default-DISABLED server gate. Candidate rollout is DISABLED. Commercial Premium is NOT activated.**
No Stripe call, no paid entitlement, no change to what any real candidate sees today, no migration (Alembic head stays `0032_ai_operation_events`). AI usage-limit enforcement stays off; all six billing gates stay off.
Starting point: `main` `9469f6b91c6edd6b615998e9b0c2d63983fb313a` (P2-A merged).

## 1. Approved owner policy (unchanged, now implemented)

Basic: the latest THREE completed interviews are accessible, and progress statistics are calculated from those same three. Premium: the complete eligible retained history, and progress from it. These are ACCESS restrictions, never deletion, storage or retention limits: nothing is deleted, moved or rewritten by a plan change, and a re-upgrade restores access with no data operation. Previously generated independent Premium artifacts stay readable and downloadable after a downgrade; creating new Premium artifacts, regenerating with Premium AI and new Premium analytics are restricted (P5-A and P4 work; none of those features exists yet). Trends and attempt comparison are not part of this wave.

## 2. Architecture assessment (VERIFIED)

* Completed history is the `interviews` table (one row per completed interview, saved after the report is durable, idempotent on `(user_id, source_session_id)`); draft and active interviews live in `interview_sessions` and never occupy a completed-history slot.
* There was no entitlement on any history route, and the History list ordered by `created_at` only (ties undefined; the five most recent interviews in progress had the same weakness).
* `EntitlementService` is the single authority (active subscription, else Basic fallback; an unlisted key is disabled). This wave adds NO key, NO writer and NO second subscription system.

## 3. History access inventory

| Path | Exposes | Before | Now (gate on) |
| --- | --- | --- | --- |
| `GET /history/interviews` | metadata (id, role, mode, status, question count, time) | all | window |
| `GET /history/interviews/{id}` | full content: questions, answers, feedback, report | owner | window; owned but outside gives 403 `history_not_available`; foreign or missing stays 404 |
| `GET /reports/{id}/export.json` and `.md` | full report content | owner | window (same refusal) |
| `GET /progress` | aggregates and five recent interviews | all | same window as history |
| Opportunity detail (`interview_ids`, `interview_count`) | ids and counts of linked interviews | all | window |
| Session routes for COMPLETED saved sessions: `GET /interviews/{session_id}` and `/report`, Deep Dive start, answer, next, return, `POST /report` | questions, feedback, report | owner | refused when the session's saved history record is outside the window; draft and active sessions are never affected |
| Workspace share creation for an interview report | resource selection | owner | refused (as a missing resource) when the interview is outside the OWNER's window |
| Existing share reads (`GET /shares/resource/...`) | bounded report view | recipients | **unchanged** (documented ambiguity, section 12) |
| `GET /auth/account/export` (privacy) | the complete account export | owner | **unchanged: a data right** |
| Owner delete `DELETE /history/interviews/{id}` | n/a | owner | unchanged (a data right) |
| Account deletion, retention, reporting aggregates | none for a candidate | n/a | unchanged (no candidate read path; Admin reports are aggregates only) |
| Agent, Mo, Career, memory, evidence, company research | **no read of completed interview history exists** (static test scans `src/agent`, `src/copilot`, `agent_service`, `career_service`, `company_intelligence_service`, `memory_service`, `evidence_access_service`) | none | none; the test fails if one is ever added without authorisation |
| Feedback rating targets | exact-target ownership check, no content returned | owner | unchanged |

## 4. The canonical policy

`src/application/history_access.py`: `HistoryAccessPolicy.decide(user_id) -> HistoryDecision(window, reason)`. One selection mechanism, `InterviewRepository.eligible_ids(user_id, window)`, is the only place "latest three" is computed; every surface passes the window to it. Premium means an ACTIVE subscription of the Premium plan family, read from the existing `EntitlementService` (`source == "subscription"` and `plan_code == "premium"`).
* Not Premium: no subscription, an ended one, an unreadable entitlement (unresolved, fails closed to the approved window, never unlimited), a `premium_preview` flag, a Premium label from the client, a non-subscription fallback.
* `premium_preview` is never consulted. No client plan label, header, query parameter or body field is read (tested with forged values both gate off and on).
* Interim design note: the plan-family comparison is deliberate and isolated in one function; P4 (quota enforcement) introduces limit-type entitlements and should replace it with a plan-data window. No registry key was added because that would change the public pricing truth table.
* Admin and trusted internal processing use repositories without a window; Admin is not a data superuser and no admin route returns candidate interview content.

## 5. Rollout gate (default disabled)

`HISTORY_RESTRICTIONS_ENFORCED = False`, a code constant (like the billing gates and `AI_COST_LIMITS_ENFORCED`). While False every decision is `gate_disabled` (no window); the window argument is not even passed to repositories, so existing behaviour and repository signatures are unchanged. No setting, startup, Admin action, frontend flag, Premium preview or Stripe fixture can enable it. A synthetic decision (`override=`) is a test seam that refuses to construct unless `API_ENV` is development or test (tested). **Activation procedure (a future reviewed release):** (1) owner approves enabling for real candidates and the wording; (2) the Premium plan version and who holds it are settled (P3, billing waves), because every account without an active Premium subscription becomes Basic; (3) decide grandfathering (an existing candidate with more than three interviews loses visibility, not data); (4) flip the constant in a reviewed release with a rollback of flipping it back; (5) announce; (6) legal review of the privacy-export treatment (section 10).

## 6. Deterministic ordering

"Latest" is `created_at` DESC then `id` DESC. `created_at` is the server-assigned time the completed row was persisted (after the report is durable), so it is the authoritative completion time; `started_at` and `ended_at` come from the client payload and are nullable, so they are not used. `id` is unique and monotonic, so ties resolve identically on every call (tested with six rows sharing one timestamp, repeated and across Basic and Premium). The same order feeds the list, direct access, progress, exports, Opportunity views and the five recent interviews in progress, and `export_user_data` ordering gained the same tie-breaker. All rows in `interviews` are completed history (`status` is always `completed`); the eligibility query also filters `status = 'completed'`, failing closed for any other value. No migration: an index could be added later; today the user-id index plus a LIMIT query is sufficient (measured below).

## 7. Basic, Premium, direct IDs, feedback and reports

Basic sees at most three (tested for 0, 1, 2, 3, 4 and 7 interviews). An interview outside the window is refused by id on detail and both exports (answers, feedback and report are part of the detail and the exports, and the refusal body carries no content). The refusal is **403 `history_not_available`** with fixed copy ("not been deleted ... remains stored ... you can still export or delete your data"), not a 404, so a candidate is never told their data was deleted; a foreign or missing id stays **404**, so ownership of another candidate's records is never confirmed. This refines the "non-disclosing" instruction: the caller is the owner, so the distinct state discloses nothing about anyone else. Premium sees all of their own history and never another candidate's (tested).

## 8. Progress

Basic progress is computed from exactly the history window (count, average, most common improvement area, average answer time and the recent list) and a test proves older low scores do not leak into the average; Premium uses the complete history; downgrade and re-upgrade switch between them on the next request. No trend analytics were added. The progress queries now eager-load questions and answers (the previous per-interview lazy loading was an N+1).

## 9. Downgrade and re-upgrade

Downgrade keeps every record (row counts equal before and after, tested with eight interviews), recomputes the window on the very next request (nothing cached), restricts older detail, exports, Opportunity listings, session reads and progress, and recreates nothing. Re-upgrade restores the full list, direct access, feedback, report and full-history progress with no duplication and no regeneration (question rows unchanged, tested). Ended, removed or unreadable subscriptions behave as Basic. These transitions are exercised with synthetic subscription rows only; no Stripe-driven transition exists in this wave.

## 10. Privacy export and legal review

The candidate's own account export (`/auth/account/export`) remains complete for any plan (tested: six of six interviews for a Basic account with the gate on), remains authenticated (unauthenticated is 401) and keeps its existing safeguards; owner deletion and account deletion are unrestricted. The commercial window is never applied to a data right. **LEGAL REVIEW REQUIRED:** confirm that the self-service export and the Basic history window are compatible with the applicable data-access obligations and wording. No retention period was invented; retention remains an open owner and legal decision.

## 11. Artifact classification and non-bypass

| Artifact | Independently stored? | Embeds interview content? | Shareable | Downloadable | Rule |
| --- | --- | --- | --- | --- | --- |
| Completed interview and its report and feedback | no, it IS the history | yes | interview_report shares | JSON and MD export | governed by the history window |
| Story Bank items | yes | no (no interview foreign key) | yes (story shares) | MD and JSON | unaffected by the history window |
| Candidate documents and approved evidence | yes | no | no | no | unaffected |
| Opportunity | yes | links ids only | no | no | linked ids filtered by the window |
| Opportunity Preparation Pack | **does not exist (P5-A)** | would | would | would | classification required before P5-A |
| Trend and comparison outputs | do not exist (P4) | would | | | classification required |
Non-bypass: no independent artifact in the code base embeds interview transcripts today (a test asserts that the Story table has no interview reference and that no pack table exists). The rule for the future is fail closed: an artifact that embeds restricted interview content is governed by the history rule unless an explicit, owner-approved classification says otherwise. **Unresolved classification (assigned to P5-A and an owner decision):** whether a pack that embeds excerpts of restricted interviews stays readable on Basic; whether a Premium comparison snapshot is an artifact or restricted history; whether artifacts shared with a workspace stay shared after a downgrade.

## 12. Sharing

A Basic owner cannot create a NEW share for a restricted interview (refused exactly like a missing resource, tested); sharing the latest three still works. **Product-policy ambiguity, documented and not silently changed:** a share created while the owner was Premium continues to work for its recipients after a downgrade (their access is not silently altered); the owner can revoke it, and source deletion still invalidates it. Whether a downgrade should suspend existing shares of restricted interviews is an owner decision.

## 13. Agent context

No candidate-facing agent, Career, Mo, memory, evidence or research path reads completed interview history today (verified by inspection and enforced by a static test), so no restricted content can reach a model context and nothing relies on a prompt to hide it. Any future path that feeds interview history to a model must call the policy before retrieval; the test is the tripwire.

## 14. Database

No migration. Existing columns and indexes suffice: the window is one `ORDER BY created_at DESC, id DESC LIMIT n` query over the per-user index; direct access and Opportunity filters reuse that id list. The Alembic head remains `0032_ai_operation_events`. Interview content is untouched.

## 15. Security tests

`tests/test_history_entitlements_p2b.py` (39 tests, real application, real subscription rows, isolated database): gate default disabled and no change for existing candidates; forged plan labels ignored with the gate off and on; hosted synthetic-decision refusal; Basic windows 0, 1, 2, 3, 4 and 7; timestamp ties and stable order; draft and active sessions excluded; newest completion displaces the oldest; direct-ID denial for detail and both exports with no content in the refusal; foreign and missing ids stay 404; refusal wording; owner delete still allowed; Premium full history and direct access; Premium never crosses candidates; ended or missing Premium is Basic; `premium_preview`, unresolved and non-subscription labels are Basic; decision reasons; Basic progress equals the window and leaks nothing; Premium progress and downgrade; history, progress, detail and export agree across five transitions; downgrade then re-upgrade with row and question counts unchanged; no stale authorization; privacy export complete and authenticated; Opportunity filtering; sharing creation refusal; session guard (active, inside, outside, Premium) and the guard on every content-returning session route; the agent tripwire; artifact classification; query shape (LIMIT and no per-row question queries) and 120-interview performance; billing gates, AI enforcement off, 44 permissions; no billing or second entitlement code in the policy; windows never mutate rows. Frontend `tests/history-restricted-p2b.test.ts` plus the updated error-kind list (eight locales, no upgrade or checkout wording).

## 16. Performance

The window is one limited query; history and Opportunity use `IN (ids)`; the list and progress queries use `selectinload` (questions, answers), removing the previous per-interview N+1. A 120-interview account lists three in well under the test bound with no per-interview question queries.

## 17. Candidate experience

Unchanged while the gate is off. When on: History and Progress show the three or the full set from the server; the new `history_not_available` response maps to a localized state in all eight locales ("outside the history included in your current view; it has not been deleted; you can still export or delete your data") with no Upgrade or checkout call to action; direct navigation therefore shows an accurate state, not "deleted". Premium UX and messaging remain P3.

## 18. Known limitations and P2-C dependencies

Plan-family comparison for Premium (replace with a limit entitlement in P4); existing shares survive a downgrade (policy decision); session-route guard relies on `saved_report_id` (a completed session whose save failed has no history record and is treated as active); no UI shows "N interviews hidden" (P3); Premium plan version and holders are undefined until the billing and P3 work; enabling needs the activation procedure. P2-C (model-profile authorisation and quality qualification) is independent of this wave but shares the same activation discipline.

## 19. Programme dependencies (kept visible)

P2-A cost protection: code implemented, enforcement not activated. Live Redis validation: pending. Model-profile quality validation: P2-C. Premium UX: P3. Usage quota approval: pending. Trends and comparisons: P4. Opportunity Preparation Pack: P5-A. Ask4Mo UG incorporation: pending. Stripe Managed Payments eligibility: pending. Stripe sandbox validation: pending. Live Brevo validation: deferred. Research-cache evaluator isolation: unresolved. Product coverage below gate (insufficient-evidence 94 %, n = 412): unresolved. RC-P10-004: not created. AC-24: partial.
