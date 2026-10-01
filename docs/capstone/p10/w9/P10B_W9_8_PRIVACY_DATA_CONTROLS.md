# P10B-W9.8 - Privacy & Candidate Data Controls

Implementation record. Candidate-side only. **No migration** (Alembic head stays `0014_opportunities`), 0
paid/live calls, no RC-P10-003, Pilot 2 not resumed, W9.9 and W10 not started.

## 1. Baseline
`main` = `150c6471555b90b73cbecdecfd174ca6496adbfe` (roadmap reconciliation PR #102 merged). Branch
`feat/p10b-w9-8-privacy-data-controls`.

## 2. Pre-implementation data inventory (verified in code)
Classes: A candidate-controlled, B derived candidate content, C operational metadata, D security/audit, E legal,
F shared/workspace, G non-user.

| Domain | Class | Candidate can view | Delete before W9.8 | Delete type | In export before | Retention constraint |
|---|---|---|---|---|---|---|
| Account/profile | A | `/account` | account deletion only | hard cascade | partial (email, tier) | none defined |
| Preferences/language | A | settings | account deletion only | hard | no | none |
| Opportunities | A | list/home | `DELETE` + archive | hard / status change | no | none |
| Documents (+versions, claims) | A/B | `/documents` | `DELETE` | hard cascade, files purged | no | versions kept on replace |
| Stories/evidence | B | `/documents` | `DELETE` | hard; shares not revoked (fixed) | no | none |
| Memories | A | settings, progress | `DELETE` | hard; source run not purged | no | none |
| Agent runs/checkpoints | B | Prepare only | `DELETE /agent/runs/{id}` by id | checkpoint thread | no | no per-user index |
| In-progress interviews | A | Practice | `DELETE /interviews/{id}` | hard | no | 30-day stale cleanup script |
| Completed interviews, answers, evaluations, reports | A/B | history | **none via API** | n/a | yes | none |
| Feedback | A | per item | `DELETE` per target | hard | no | none |
| Workspaces/memberships | F | `/workspaces` | leave/remove (POST) | revoke shares | no | none |
| Share grants | F | `/shares/mine` | `DELETE` revoke | soft (`status=revoked`) | no | row retained |
| Auth sessions | C/D | none | logout | hard | no | expired rows never purged |
| Consent/legal acceptance | E | none | n/a | n/a | n/a | **not stored at all** |
| Audit log | D | admin only | anonymised on account deletion | actor set NULL | no | retained |
| Support data | - | none exists | | | | |

## 3. Deletion-semantics matrix (what the UI may truthfully say)
| Action | Semantics | UI wording |
|---|---|---|
| Delete document | hard; file, versions, claims removed; stories re-derived as not source-backed; JD link cleared | "Delete" / "deleted for good" |
| Delete memory | hard; does not touch history | "Delete" |
| Archive Opportunity | status change, still stored | "Archive" (never "delete") |
| Delete Opportunity | hard; interviews/sessions kept and now **explicitly unlinked** (W9.8 fix) | "Delete" |
| Delete interview (new) | hard cascade (questions, answers, evaluations, report), linked in-progress session discarded, share grants revoked | "Delete" |
| Revoke share | soft; future access stops; nothing already seen is recalled | "Revoke access" |
| Delete account | immediate hard cascade; files purged; audit anonymised | "Delete" with a "what is kept" list |

## 4. Export scope
`GET /auth/account/export` now returns one JSON file (`Content-Disposition: attachment`, `Cache-Control: no-store`),
generated on demand (immediate, nothing stored, no expiry), built by `src/application/data_export.py`
(`build_candidate_export`, `ask4mo.candidate-export.v1`): account, preferences, Opportunities, documents (+versions,
claims; no files, no storage keys), stories, memories, interviews, feedback, workspace memberships, shares. The file
states its own `scope.included` / `scope.not_included` and `legal_acceptance: {recorded: false}`. Excluded: original
files, audit/security records, others' data, prompts/secrets. The pre-W9.8 shape is kept under `data` for
back-compat. Not implemented: asynchronous export, original-file bundle (documented gap).

## 5. Retention findings
No retention periods exist for candidate content; the only time-based rule is a 30-day cleanup of stale in-progress
sessions, run by an operator script (not scheduled). Expired auth sessions/tokens are never purged. Candidate copy
therefore states **no periods**, only: kept until deleted, deleted now, backups not erased instantly, security
records kept without identity, provider processing under the provider's terms. Gap for W10.10.

## 6. Consent/legal-version findings
Nothing is persisted (no Terms/Privacy/AI-transparency version or timestamp; registration has no acceptance field).
The Data & Privacy page therefore links the three documents and states that no acceptance history is recorded yet. It
never fabricates a version. Needs a migration + registration/re-acceptance flow: **owner decision / future wave**.

## 7. Architecture
Route `/account/data` ("Your data & privacy"), linked from `/account` and Settings. `components/account/DataPrivacyCenter.tsx`
composes existing owner-scoped GET endpoints (no aggregate API); each section loads independently through
`lib/hooks/useResource.ts` and degrades to a section-tier ErrorState with a safe GET retry. New shared primitive
`components/ui/ConfirmDialog.tsx` (alertdialog, focus on Cancel, focus trap, Escape, focus restore, scroll lock;
page behind is `inert`; failures stay in the dialog; never auto-retried). Sections: overview, export, remove
individual data (Opportunities, Documents, Memories, Interviews), sharing, retention, consent/legal, account deletion.
The old export link and one-click delete in `AccountPanel` moved here.

## 8. Backend added
- `DELETE /api/v1/history/interviews/{id}` (owner-scoped; 404 foreign/repeat, never 5xx; discards the source session;
  revokes interview-report shares; metadata-only audit `interview.deleted`).
- Story delete now revokes its share grants (previously `invalidate_on_delete` had no callers).
- Opportunity delete explicitly unlinks interviews/sessions (SQLite has no `SET NULL` for the added column; ids can be reused).
- Export rewritten (section 4). `InterviewRepository.delete_interview_with_source`.
- `tests/_auth_factories.build_auth_app` now also overrides `get_memory_service`: memory writes in tests were
  landing in the configured dev DB because that dependency calls `get_repository()` directly (a root cause of TD-W9-02).
  I removed the 3 stray rows my own runs wrote.

## 9. Deferred / unsupported (stated plainly)
1. **Preparation chats (agent checkpoints):** no per-user run index and no list API, so a candidate cannot list or delete
   chats from this page, and account deletion purges only runs reachable via `source_run_id` of a saved memory. A scan of
   the checkpoint store was prototyped and **rejected** (it deserialises every checkpoint: >2 minutes on a 35 MB dev store,
   and unsafe in tests). Proper fix needs a run-ownership table (migration) - STOP/owner decision. Candidate copy says
   "may remain until cleaned up" and "removing a single chat is not available yet".
2. Consent/legal acceptance history (section 6). 3. Bulk "clear all memory" (no bulk endpoint; per-item only).
4. Per-version document delete. 5. Auth-session list/revoke UI (backend `list_active` unused). 6. Feedback list/delete
page (feedback is reset where it was given). 7. Original-file bundle in export. 8. Orphan workspace invitations to a
deleted user's email. 9. Audit `context` is not allow-list enforced (call-site discipline; no private content found).
10. Deletion safeguards beyond a confirmation dialog (no re-auth); the orphaned soft `delete-request` endpoint is unchanged.

## 10. Privacy/security boundaries
Every endpoint is owner-scoped from the session (never a browser id); foreign ids are 404; admin gained no capability
(no `/admin/privacy`); export excludes secrets/storage keys/hashes; writes are never transport-retried
(`retry.ts` GET/HEAD only, asserted in test + evaluator).

## 11. Localization and review status
`dataPrivacy` namespace (~115 keys) x 8 locales in `lib/i18n/messages/w98/`, merged via the w96 aggregator (a missing
locale throws). Scanner 0 offenders; slogan not touched. **All non-English privacy/legal-adjacent copy, including
Russian, is an ENGINEERING TRANSLATION - human/legal review required before production reliance.**

## 12. Accessibility / mobile / theme
alertdialog semantics, default focus Cancel, focus trap/restore, inert background, descriptive button names
("Delete: My CV"), non-colour destructive cue (text + border), 44px dialog targets, role=status/alert announcements.
390px light/dark (ru, de) verified: no horizontal overflow, dialog within viewport (screenshots reviewed).

## 13. Tests
Backend `tests/test_w98_privacy_controls.py` (16): export content/headers/exclusions/auth, interview delete cascade,
foreign/repeat 404, audit, share revocation on interview/story delete, share revoke, document/memory/opportunity
semantics, owner-scoped reads, account-deletion cascade + audit anonymisation, opportunity unlink, no write retry.
Frontend `tests/data-privacy-center.test.tsx` (15, incl. all-8-locale key/dash/slogan checks). Playwright
`e2e/data-privacy.spec.ts` (6: core journey, account deletion cancel/confirm, de, ru, 8-locale smoke, mobile light/dark).
Evaluator `scripts/eval_privacy_controls.py` (11 invariants, added to CI). Cross-user browser tampering is not
applicable (no id-entry surface); backend tests are authoritative.

## 14. Future W10 reuse
`build_candidate_export`, `delete_interview_with_source`, the share-invalidation seam and the (missing) consent model
are the services W10.10 should call for operator-side access/export/deletion requests; deletion status tracking and
the run-ownership index belong there.

## 15. W9.9 handoff
Trust & Visual Product Polish: start from the Data & Privacy page as a reference surface; no dependency on W9.8 gaps.

## 16. Confirmation
Migration: **no**. Paid/live calls: **0**. RC-P10-003: **not created**. Pilot 2: **not resumed**.
