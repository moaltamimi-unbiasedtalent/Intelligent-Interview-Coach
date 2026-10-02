# P10B-W10.3 - Customer Support & Ticketing

**Status:** implemented on branch `feat/p10b-w10-3-support-ticketing`; **complete when merged to `main`**. **W10.4 is NOT STARTED.**
One additive migration (`0015_support_ticketing`). No new dependency. 0 paid/live calls.

## 1. Starting point
`main` `2923d5c3466d9cdb7c28833a763f4c7bc904593c` (W10.2 complete), clean tree, Alembic head `0014_opportunities`.

## 2. Branch
`feat/p10b-w10-3-support-ticketing`.

## 3. Pre-existing support audit
| Capability | Current implementation | Reusable? | W10.3 action |
|---|---|---|---|
| Help | Public searchable Help Center (`/help`), localized x8 | Yes (entry point) | Added a Contact Support link |
| Feedback | `user_feedback`: ratings and bounded comments attached to an output | No (not a conversation) | Left unchanged |
| Request id | Every response carries `X-Request-Id` (W9.1); error cards show it | Yes | Optional field on the form; stored on ticket and messages |
| Support permissions | `platform.support.read/reply/manage/note` already in the canonical 43; `support_operator` preset holds all four | Yes | Used as-is; added to `platform_admin` (it had none). Registry unchanged at 43 |
| Support routes / tables / contact form / email | None | - | Built |
| Upload/storage | `DocumentStore` is tied to the candidate-document pipeline (parse, OCR, extraction) and has no support-scoped authorization, download or cleanup contract | No | Attachments deferred (section 24) |

## 4. Domain model
Three tables with physical boundaries: `support_tickets` (operational record), `support_messages` (customer-visible thread; author kind `candidate` or `support`), `support_internal_notes` (Admin-only). Internal notes are a separate table, not a visibility flag, so no candidate query can reach them.

## 5. Migration design
`0015_support_ticketing` (chains from 0014, single head, reversible). CHECK constraints on category, priority, status and author kind; unique `public_id`; FKs: ticket owner `ON DELETE CASCADE`, assignee and message/note author `ON DELETE SET NULL`, messages and notes `CASCADE` from the ticket. Indexes only for real queries: `public_id` (unique), `(owner_user_id, updated_at)`, `(status, updated_at)`, `(assigned_user_id, status)`, `(ticket_id, id)` on messages and notes. No SLA columns, no attachment table, no full-text index. Tested from a fresh database, from an existing 0014 database, constraint enforcement, downgrade and a round trip.

## 6. Public ticket identifier
An opaque `public_id` (`uuid4().hex`, standard library) is the candidate-visible reference; the integer id is internal. Authorization never depends on the identifier: every candidate query also filters by the authenticated owner, and a foreign or unknown reference is the same 404. Admins may use either.

## 7. Ownership model
A candidate owns their tickets (`owner_user_id`). Candidate routes (`/support/tickets...`) are owner-scoped; admin routes use canonical permissions.

## 8. Account-deletion semantics
No retention period is invented and no legal retention is claimed: deleting an account deletes its tickets, messages and internal notes (explicitly, children first, because SQLite does not enforce FK cascades; the FK cascade covers PostgreSQL). Operator references (assignee, message and note author) are anonymized (set to null), so deleting an operator never removes another person's thread. Tested: the deleted candidate's three tables are empty for them, another candidate's thread survives the operator's deletion. If support records had to outlive account deletion, that would be a retention/legal decision belonging to W10.10.

## 9. Export semantics
The self-service export gains `support_tickets` (subject, category, status, timestamps and the customer-visible thread). Internal notes are excluded and the export's `scope.not_included` says so; Data & Privacy lists both lines (x8 locales). It is not described as a complete legal DSAR. PRIV-W9-01 and PRIV-W9-02 stay OPEN.

## 10. Status model
`new`, `triaged`, `in_progress`, `waiting_for_customer`, `resolved`, `closed` (CHECK-constrained). Server-validated transitions: new/triaged/in_progress/waiting_for_customer may move forward or to resolved or closed; `waiting_for_customer` may return to `in_progress`; `resolved` may reopen to `in_progress` or close; `closed` is terminal. A candidate reply on a waiting or resolved ticket moves it to `in_progress`; a reply on a closed ticket is rejected (409). `resolved_at` and `closed_at` are set and cleared accordingly.

## 11. Priority model
`low`, `normal` (default), `high`, `urgent`. Set only by support staff (`platform.support.manage`); a candidate cannot send it (the create and reply request models reject unknown fields). Priority is an internal label and implies no response time.

## 12. Category model
`account_login`, `opportunity`, `prepare`, `practice_interview`, `documents`, `ai_response`, `billing`, `privacy`, `accessibility`, `technical`, `data_issue`, `other`, validated server-side. Candidates see localized labels (x8); the admin UI shows English labels.

## 13. SLA decision
No SLA policy is approved, so there are no SLA or due-date columns, no automatic due timestamps, no breach counts, and no copy that promises a response time. The candidate page says: "We cannot promise a response time."

## 14. Candidate intake
`/support`: topic, subject (max 200), message (max 5,000), optional request reference. The page also reads an optional `from` pathname (query string and fragment dropped, server too) and `ref`; the environment is derived server-side. No cookies, tokens, local storage, page HTML, query strings or logs are captured. Creation stores the ticket and its first message in one transaction (a failure leaves no empty ticket). Rate limit: 10 tickets per hour per user and 60 replies per hour (existing W9.12 abstraction, in-memory per process; not a distributed limit, and Redis is not used).

## 15. Candidate localization
All new candidate copy (64 keys plus two Data & Privacy lines) exists in en, de, fr, es, it, pt, nl and ru, typed against English so a missing key fails `tsc`; a test checks every key in every locale, no SLA/24-7 claim and the protected slogan is untouched. They are engineering translations pending native review, like every other locale.

## 16. Candidate list, detail and thread
Paginated own-ticket list (subject, topic, status as text, last updated); detail with reference, status, topic and the thread (candidate and "Ask4Mo Support" messages; no operator identity). Replies while the ticket is not closed; a closed ticket explains itself. Messages render as plain text (React escapes; a test submits HTML and script and finds no element). Candidates must return to the page to see replies: no email is sent.

## 17. Admin support queue
`/admin/support`: server-side status, category, priority, assignee (me, unassigned, id) filters, search by ticket reference, candidate email or account id (not message text), stable ordering, pagination (max 100), unknown filter values are 422. Rows carry no thread text.

## 18. Admin ticket detail
Ticket (reference, subject, category, status, priority, assignee, timestamps, request id, source pathname, environment), safe requester metadata (the W10.2 account summary), the customer-visible messages and, separately labelled, the internal notes. Nothing else about the candidate is fetched.

## 19. Assignment
`POST /admin/support/tickets/{ref}/assign` (`support.manage`): assign, reassign or unassign. The assignee must be an active account whose preset holds `platform.support.manage` (ordinary candidates, inactive accounts and admins without support are rejected). `GET /admin/support/assignees` lists only those.

## 20. Customer-visible replies
`POST .../reply` (`support.reply`) writes a `support` message; the candidate sees it on refresh. A closed ticket rejects replies.

## 21. Internal notes
`POST .../notes` (`support.note`) writes to `support_internal_notes`. Only Admin ticket detail returns them.

## 22. Internal-note leakage protections
Physical separation (own table and model); the candidate side of the repository has no reference to the notes model; candidate response models have no note, priority, assignee or operator-id field (extra=forbid); candidate routes have no note path; the export excludes them; audit payloads hold the note id only. Tests assert the note text is absent from the candidate ticket, candidate list, export and every audit row, and `eval_admin_support.py` checks the same structurally.

## 23. Rate limiting
See section 14. Limits are deliberately generous so support stays usable.

## 24. Attachment decision
Deferred: "Support attachments are not yet enabled." The existing store is built for the candidate-document pipeline and offers no support-scoped authorization, secure download or cleanup, and no malware scanning exists. No weak upload path was added, and there is no attachment table.

## 25. XSS and content rendering
Plain text everywhere: the server strips control characters (NUL etc.) and trims; nothing is rendered as HTML (no `dangerouslySetInnerHTML`, guarded by the evaluator). Limits (server-enforced): subject 200, message 5,000, internal note 5,000, route 200, request id 64; over-limit is a validation error.

## 26. Audit events
New canonical events: `admin.support_ticket_assigned`, `admin.support_ticket_status_changed`, `admin.support_ticket_priority_changed`, `admin.support_reply_sent`, `admin.support_internal_note_created`. Each mutation and its audit row are one transaction (tested: an audit failure rolls back assign, status, priority, reply and note). Payloads carry the ticket id, enum before/after, assignee ids, and message or note ids; never text. Candidate ticket creation and replies are candidate actions, not privileged Admin audit events.

## 27. Permissions and routes
`GET /admin/support/tickets` and `/tickets/{ref}` and (`support.read`), `POST .../reply` (`support.reply`), `.../assign`, `.../status`, `.../priority` and `GET /assignees` (`support.manage`), `.../notes` (`support.note`). Eight new privileged routes; **current total 41, 41 permission-covered, 0 uncovered**. Candidate routes: `POST/GET /support/tickets`, `GET /support/tickets/{id}`, `POST /support/tickets/{id}/messages` (owner-scoped, not Admin). `support_operator` and (new) `platform_admin` are allowed; candidate, billing, knowledge, operations and security presets are denied; a preset with only `support.read` cannot mutate (tested).

## 28. Command Center integration
With `support.read`, the Command Center shows counts only: open, unassigned, waiting for customer, high or urgent. No text and no SLA or breach figures. Without the permission the block is absent.

## 29. Privacy boundary
Support sees what the candidate sent to Support, safe W10.2 metadata, request ids and support history. There is no "open candidate data" action, no impersonation, no break-glass and no private-content endpoint; the Admin UI states the boundary.

## 30. Backend tests
**2659 passed, 3 skipped, 0 failed, 0 errors** (`python -m pytest`, 205 s; baseline 2630/3). Skips unchanged: live Adzuna, a Streamlit-context render, a RAGAS test. New `tests/test_support_w10_3.py` (29): create atomicity and validation, every category, list and detail shape, cross-user isolation, reply lifecycle, candidate cannot set operational fields, rate limit, permission matrix, queue filters and search, detail, transitions, priority, assignment, visible reply versus internal note, audit payloads, audit rollback x5, plain-text, export, account deletion, Command Center, schema guard, route coverage, migration (fresh, from 0014, constraints, downgrade). Existing migration and W10.1 tests updated for head `0015`. `ruff check .` clean.

## 31. Frontend tests
607 unit tests in 78 files (candidate: entry, form validation with associated errors and focus, limits, creation with pathname-only source, failure not retried, list, empty/error/retry, pagination, detail, plain text rendering, reply, closed state, not-found, x8 copy; admin: Support nav gating, queue filters and pagination, detail, read-only state, status/priority/assignment confirmations, reply and note, failure not retried, closed state, no role-name authorization). Async content is always awaited with `findBy*`/`waitFor`. Typecheck, lint, production build and the hardcoded-English scanner (0 offenders) are clean.

## 32. Playwright
**204 passed** (201 baseline plus the candidate journey and its validation test, and the admin support journey), serial, no retries or timeout changes. The journeys mock the network (as established); ownership, isolation and audit are proven in Python.

## 33. Evaluators
**30 of 30** CI evaluators pass, including the new `scripts/eval_admin_support.py` (21 checks) and the W10.0-W10.2 guards (updated for the new head and for Support as an operational destination). The registry stays at 43.

## 34. Manual QA
Freshly migrated local backend (head `0015_support_ticketing`, migration state match): a candidate created a ticket through the form; the list showed it with status text. As staff: status, priority, assignment, a reply and an internal note were applied; the candidate's ticket page showed the reply and not the note, the export did not contain the note, the Admin detail showed both with the note visually separate, the Command Center counted the ticket, and the audit rows held ids and enums only with request ids. Demoting the same account removed Admin access. HTML typed into the message showed as text. QA found one defect, fixed before commit: an assignee without an email displayed as "Unassigned" (now "Account <id>"), with a regression test.

## 35. Performance
First Load JS: `/support` 400 kB (route 4.5 kB; the candidate locale catalogues dominate, as for `/help` 401 kB), `/support/[ref]` 399 kB, `/admin/support` 115 kB, `/admin/support/[id]` 117 kB, `/admin` 114 kB, shared 103 kB (unchanged). Queue rows carry no thread; one request per page plus assignees on demand; lists are paginated; no client dependency added.

## 36. Migration result
`0015_support_ticketing` applied from fresh and from 0014; downgrade and re-upgrade tested.

## 37. Alembic head
`0015_support_ticketing` (single head).

## 38. Dependencies
None.

## 39. Security status
CLOSED: SEC-W10-01, SEC-W10-02, SEC-W10-03, SEC-W10-06. OPEN: SEC-W10-04 (privacy queue, W10.10), SEC-W10-05 (process-local pause, W10.11). PRIV-W9-01 and PRIV-W9-02 OPEN. No break-glass, impersonation, SLA claim or live provider.

## 40. W10.4 handoff
W10.4 (Plans, Subscriptions and Entitlements) can rely on: stable account identity and status, the support thread and permissions, the `billing` support category (no billing exists), request ids, the audit helper and the Command Center count pattern. No support tier exists; none was invented. Tier remains account metadata until W10.4.

## 41. External calls
0 paid or live provider calls; no email is sent.
