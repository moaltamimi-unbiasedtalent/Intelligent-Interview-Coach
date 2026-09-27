# P10B Wave 6 - Opportunity Model, Candidate Journey & Workspace Clarification

**Status:** DELIVERED (implementation complete; gates green).
**Branch:** `feature/capstone-p10b-wave6-opportunities` - **not merged**.
**Baseline:** `main` @ `2c1c14a` (Waves 1-5 merged; PRs #87/#88/#89/#93/#94).
**Migration:** `0014_opportunities` (additive; single head; up/down verified).
**Release candidate:** none. RC-P9-001 immutable; RC-P10-002 only at Wave 8.
**Paid/live calls:** 0.

Introduces the missing candidate-preparation concept - the **Opportunity** - so the product reads as
"I am preparing for this specific job" instead of a set of disconnected features, and clarifies that a
**Workspace** is for collaboration/sharing. It reuses (never rebuilds) documents/evidence, Company
Intelligence, Prepare, Practice, interviews, reports and progress.

## Definitions (durable product rule)
- **Opportunity** = a candidate's private preparation context for ONE job (role + company + optional
  JD). It groups Company Intelligence, Prepare, Practice, reports and progress for that job.
  Owner-scoped, private by default. It NEVER auto-creates a Workspace and is never required.
- **Workspace** = a controlled collaboration area to work with other people and share selected
  resources (VIEW-only). Unchanged in behaviour; copy reframed so the two are unmistakable.

## Domain model & migration
`0014_opportunities` (additive, chains from `0013`, single head):
- New table **`opportunities`**: `id`, `user_id` (FK `users.id` ON DELETE CASCADE), `title`,
  `target_role`, `company_name`, `company_location`, `company_country` (ISO-2), `company_domain`,
  `job_description_document_id` (FK `candidate_documents.id` ON DELETE SET NULL), `status`
  (`active|interviewing|offer|closed|archived`), `notes`, `created_at`, `updated_at`, `archived_at`.
- **Nullable** `interviews.opportunity_id` and `interview_sessions.opportunity_id` (FK
  `opportunities.id` ON DELETE SET NULL). SQLite cannot ALTER-add an FK, so on SQLite the column +
  index are added and the FK is created only on databases that support it (e.g. PostgreSQL); fresh
  schemas built from the ORM carry the FK inline. Existing standalone/legacy rows stay valid with a
  NULL link - **no fabricated associations, no destructive change** (STOP conditions not triggered).

**A/B/C/D/E classification:** Columns on Opportunity = role/company/location/country/domain/JD-ref/
status/notes (A); nullable `opportunity_id` on `interviews` + `interview_sessions` (B); global
candidate documents/claims/stories/memory stay independent (C); progress/journey/company-research
stay derived/ephemeral (D); `share_grants` stays workspace-specific - an Opportunity can be shared
LATER by allow-listing a `resource_type` with zero schema change, deliberately deferred (E).

## Opportunity vs Workspace
Not merged and not cross-wired: workspace/sharing code has no reference to Opportunity, and the
Opportunity model has no members/shares. A `workspaces.vsOpportunity` clarification string states the
distinction in the UI. **Opportunity sharing is NOT implemented in Wave 6** (would require no new
authorization - it is a future seam over the existing explicit VIEW-only share model).

## Create journey
A 4-step wizard (`OpportunityCreate`): **Role -> Company -> Job description -> Review**. Only the role
is required; the JD reuses the governed `DocumentPicker` (no second uploader). Fast enough to create
in about a minute when a JD already exists. The title is derived deterministically ("Role - Company -
Location") when no label is given.

## Opportunity home
`OpportunityHome` shows: Overview (role/company/location/website/JD status + bounded status
quick-change), Company Intelligence, Prepare with Mo, Practice, Your evidence, Interviews & reports
(linked count + View history) and a clear next action, plus archive/reactivate/delete. Restrained
cards, progressive disclosure, no dashboard noise.

## JD integration
An Opportunity may reference a `job_description` document (owner-scoped; a foreign/missing/non-JD id
is rejected with 422). When that document is deleted, the link is cleared (Postgres FK SET NULL; on
SQLite the document-delete path clears it), and `context`/`overview` always re-check ownership so a
stale link is reported **unavailable** - never exposing inaccessible content. No raw document
duplication; OCR, failure taxonomy and injection-as-DATA boundaries are untouched.

## Evidence integration
No CV/evidence text is copied into an Opportunity. Candidate evidence stays governed by the existing
system; only APPROVED evidence reaches governed preparation (rejected/unreviewed/revoked stays
excluded, and source deletion/revocation still propagates). The home links to Documents to manage it.

## Company Intelligence integration
Reuses the Wave 5 engine and endpoint unchanged. The home deep-links to `/company?opportunity=<id>`;
`CompanyResearchClient` pre-populates company name/location/country/website/role/JD from the
owner-scoped Opportunity (the candidate can still edit everything). No second research endpoint, no
uncontrolled research persistence.

## Prepare / Practice integration & context precedence
Deep-links `/prepare?opportunity=<id>` and `/practice?opportunity=<id>` pre-populate role + JD from
the Opportunity (a subtle "Preparing for this opportunity" note is shown). A new session launched from
an Opportunity carries its `opportunity_id` (server-verified ownership); a completed interview inherits
it so the report is discoverable from the Opportunity. **Precedence** is preserved:
**explicit session choice > Opportunity context > account preference > device/default** - Opportunity
context is only an initial value and never silently overrides an explicit session choice (e.g.
conversation language stays account/session-owned; the Opportunity model carries no language field).
Mo's identity/persona, tool allow-list and HITL are unchanged; retrieved JD/company material remains
untrusted DATA and never becomes system instructions.

## Session / report association
`interviews.opportunity_id` + `interview_sessions.opportunity_id` (nullable). Historical sessions
remain valid (NULL). Reports are NOT duplicated - the Opportunity references existing interviews and
they remain discoverable from History/Progress; deep links preserved. Deleting an Opportunity never
deletes its interviews/documents/evidence (SET NULL / kept).

## Authorization, security & privacy
- Every endpoint is owner-scoped by the trusted authenticated user id; a foreign/unknown id returns
  **404**; invalid input returns **422**. Opportunities are **BASIC** (no capability gate), consistent
  with history/documents/memory.
- create/archive/delete emit **metadata-only** audit events (`opportunity.created/archived/deleted`;
  no title/company/JD content).
- **Platform Admin** gains no opportunity content (admin routes never read the model).
- **Account deletion** removes owned opportunities (explicit, after interviews/sessions).
- **Privacy:** the model stores only bounded candidate-entered strings + a JD reference; no CV/evidence
  text, no research content, no secrets, no private content in logs. Company/career geography stay
  independent; geography is never inferred from language; user-entered names/roles are not translated.
  Privacy inventory updated.

## i18n & accessibility
New `opportunity` namespace (83 keys) + `nav.opportunities` + `workspaces.vsOpportunity` across all 7
locales (parity enforced by `tsc`). Keyboard-complete wizard/nav, text-based step indicator, labelled
fields, status never conveyed by colour alone, mobile-responsive, no emoji, no em dash.

## Evaluation & tests
- `scripts/eval_opportunity_journey.py` - 25+ deterministic invariants, PASS, 0 paid/live.
- Backend `tests/test_opportunity_journey.py` (lifecycle, foreign-access 404, JD owner scoping +
  deleted-JD safety, session/interview association, historical-session validity, deletion preserves
  history, account deletion). Affected suites (interview durable, api, persistence hardening,
  application boundary, migrations, openapi) updated for the new `save_interview(opportunity_id=...)`
  signature (fakes kept in sync - not weakened).
- Frontend `tests/opportunities.test.tsx` + `e2e/opportunities.spec.ts` (list/empty, wizard, home,
  nav discoverability).

## Status ladder (do not collapse)
- **IMPLEMENTED:** model + migration, repository/service, API, wizard/list/home UI, context
  propagation into Company/Prepare/Practice, session/report association, Workspace copy reframe, i18n,
  evaluator.
- **DETERMINISTICALLY TESTED:** all suites above (0 paid/live).
- **LIVE VALIDATED:** none (no live provider path added).
- **HUMAN VALIDATED:** none (engineering-draft translations; no pilot in this wave).

## Files changed
Backend: `src/persistence.py` (Opportunity ORM + opportunity_id columns + User relationship),
`migrations/versions/0014_opportunities.py`, `src/opportunity.py`, `src/opportunity_repository.py`,
`src/application/opportunity_service.py`, `src/api/schemas/opportunity.py`,
`src/api/routes/opportunity.py`, `src/api/dependencies.py`, `src/api/main.py`,
`src/api/routes/interview.py`, `src/api/routes/documents.py`, `src/api/schemas/interview.py`,
`src/interview/session_repository.py`, `src/repository.py`, `src/application/history_service.py`,
`src/application/account_deletion_service.py`, `tests/*`.
Frontend: `frontend/app/opportunities/{page,[id]/page}.tsx`, `frontend/components/opportunities/*`,
`frontend/lib/useOpportunityContext.ts`, `frontend/components/company/CompanyResearchClient.tsx`,
`frontend/components/agent/AgentPrepareWorkspace.tsx`, `frontend/components/interview/{PracticeClient,
InterviewSessionSetup}.tsx`, `frontend/app/practice/page.tsx`, `frontend/components/layout/nav-items.ts`,
`frontend/lib/api/{client,types}.ts`, `frontend/lib/i18n/messages/*.ts` (7 locales), tests.
Docs: this file + IA proposal, remediation plan, requirements matrix, privacy inventory, CLAUDE.md.

## Known limitations
- Opportunity sharing is deferred (future seam over the existing VIEW-only share model).
- On SQLite the `opportunity_id` FK is not enforced at the DB layer (added only where supported);
  ownership + link-clearing are enforced in the application layer.
- Engineering-draft translations (not human/legal reviewed).

## RC impact
No RC created. RC-P9-001 immutable; RC-P10-002 only at Wave 8. This wave changes runtime (new model +
endpoints + UI); a pilot before Wave 8 would require a new RC.

## Next recommended wave
**Wave 7** - Marketing / Product / Trust / Pricing redesign. Not started.
