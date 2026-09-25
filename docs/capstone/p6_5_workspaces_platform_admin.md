# P6.5 — Teams / Workspaces & Platform Admin

_Capstone P6.5. Bounded Teams/Workspaces with explicit, private-by-default sharing, plus a
bounded PLATFORM_ADMIN operations surface built on the P1/P6 foundations. No billing, no
enterprise SSO, no candidate-private data exposed to admins. Migration `0011` (single head).
See `p6_5_workspace_admin_design.md` for the authorization vocabulary._

## Why
P1 established platform roles + entitlements as orthogonal dimensions and left a
workspace-role *contract only*. P6 added reviewer/admin APIs. P6.5 makes both real: a
candidate can create a workspace, invite by email, and **explicitly** share a selected
report/story/prep-summary (VIEW-only, revocable); a platform admin gets an operational
console — never a data superuser.

## Architecture
- **Models** (`src/persistence.py`, migration `0011_workspaces_shares`): `workspaces`,
  `workspace_memberships` (role WORKSPACE_OWNER/MEMBER on the membership), `workspace_invitations`
  (opaque hashed single-use expiring token), `share_grants` (owner + workspace + resource +
  VIEW + status). Feedback gains an optional `category` column (P6 taxonomy).
- **Repository** (`src/workspace_repository.py`): owner/workspace-scoped dict projections;
  the authorization read `active_share_owner_for_member` re-derives access every call.
- **Services**: `WorkspaceService` (create/invite/accept/decline/leave/remove/transfer/
  deactivate) and `SharingService` (share/revoke/can_view/resolve/invalidate). All invariants
  are enforced here and audited.
- **API**: `src/api/routes/workspaces.py` (USER + WORKSPACE classes) + `shares_router`;
  `src/api/routes/admin.py` (ADMIN class, router-level `require_platform_admin`).
- **Frontend**: `/workspaces` (candidate UX, i18n) + `/admin` (English ops console); a
  feedback category control on `FeedbackControl`.

## Workspace model & membership
A user belongs to 0..N workspaces. The **workspace role lives on the membership**, never on
the User. Creating a workspace makes the creator WORKSPACE_OWNER. Only an owner may invite,
remove members, transfer ownership or deactivate. The **last owner cannot orphan** a
workspace (must transfer first). Leaving/removal marks the membership inactive (kept for
audit) and **revokes that member's outbound shares** into the workspace.

## Invitations
Opaque `secrets.token_urlsafe(32)` token, stored **hashed** (SHA-256) on the invitation,
single-use, 72h expiry, emailed via the existing `EmailSender` abstraction (deterministic
`MemoryEmailSender` in tests; no live email without authorization). Acceptance requires the
accepting account's **own verified email to match** the invitation (foreign acceptance
rejected); replay/expired/used tokens are refused; no member enumeration.

## Sharing (explicit, allow-listed, VIEW-only)
The **operational** allow-listed resource types are exactly the two that are durable,
owner-scoped and have a wired owner loader: **interview report** and **story**. Both are
fully wired end-to-end:
- **interview report** → `InterviewRepository.get_interview(owner_id, id)` (owner-scoped) →
  VIEW via `report_export.build_json_export` (safe bounded projection: score/summary/
  strengths/focus/target-role — never usage, prompts or internal state).
- **story** → `StoryRepository.get(owner_id, id)` (owner-scoped) → safe story projection.

**Preparation summary is PLANNED, not operational.** There is no durable, owned
`preparation_summary` resource with a stable id + owner-scoped loader today (the
`PreparationContext` is transient), so it is **deliberately excluded from the operational
allowlist** — a share attempt returns 422. It is documented here and in the UI/matrix as
NOT YET WIRED so implementation and docs tell the same truth.

Never shareable at all: raw documents/CV, raw extracted text, Memory, auth data, audit
trail, recovery info. A share requires the caller to **own** the resource (owner-verified)
AND be an active member of the target workspace. Ownership never transfers. Reading a shared
resource loads it **as the owner** (owner scoping intact), gated by a valid grant — the read
path is: authenticated member → active grant → resource owner from the trusted grant →
owner-scoped resource service → bounded VIEW projection (never an unrestricted repo read).

## Private-by-default
Joining a workspace exposes **nothing** automatically. The only path to another member's
resource is an explicit share grant. Revocation and source deletion both cut access
**immediately** (the decision is re-derived on every read — a cached/shared link cannot
bypass it). Deleting the source invalidates its grants; a grant never resurrects deleted
content.

## Platform Admin (PLATFORM_ADMIN ≠ DATA_SUPERUSER)
`/api/v1/admin/*` is router-gated by `require_platform_admin` (normal user → 403,
unauthenticated → 401). Admin can see **operational metadata**: account list (email/role/
tier/status/verification/created — never CV/answers/Memory/documents), account stats,
workspace metadata, privacy-request queue, aggregate feedback counts + taxonomy, safe
provider status, recent audit. Admin can perform **audited** privileged changes: platform
role, entitlement tier, account status — with self-lockout guards (an admin cannot demote or
deactivate themselves). There is **no "view as user"**, no private-data search, and
owner-scoped repositories stay owner-scoped (no `if admin: return everything`).

## Entitlements (Teams ≠ Premium)
Product entitlement (BASIC/PREMIUM) and workspace/team access are **separate dimensions**.
Admin tier changes go through the P1 `set_tier` (server-side, audited, not client-spoofable).
No billing.

## Knowledge / Prompt Lab / Feedback integration
The admin console reuses the P6 reviewer APIs (`/reviewer/knowledge/*`, `/reviewer/prompt-lab/*`)
— no second backend. The **no-auto-promotion** Prompt Lab rule remains binding (there is no
promote endpoint). Feedback is surfaced as aggregate counts + taxonomy + improvement
lifecycle metadata only — never raw candidate conversation; no automatic learning.

## Candidate feedback category (P6 carried item, now done)
`FeedbackControl` offers an optional bounded category (P6 taxonomy) when a candidate marks an
answer *not helpful*. A simple thumbs rating stays effortless; the category is additive and
i18n'd across all 7 locales. A candidate's Brief/Detailed preference is never auto-changed.

## Privacy requests
`/api/v1/admin/privacy-requests` lists open deletion requests (metadata only). It does **not**
falsely claim deletion is complete — the known private-file + LangGraph checkpoint purge
gaps remain carried.

## Audit
Workspace/admin mutations are audited with safe allow-listed metadata only (no email bodies,
tokens, PII beyond ids, or candidate content): `workspace.created`, `workspace.invite_created`,
`workspace.invite_accepted/declined`, `workspace.member_left/removed`,
`workspace.ownership_transferred`, `workspace.deactivated`, `share.created/revoked`,
`admin.platform_role_change`, `admin.entitlement_change`, `admin.account_status_change`.

## I18n
All new candidate-facing strings live under the `workspaces` namespace in every locale
(EN/DE/FR/ES/IT/PT/NL; key-parity enforced). Translations are ENGINEERING DRAFT. The admin
console is English (internal ops surface, §14).

## Security (tested)
`scripts/eval_workspace_security.py` + `tests/test_workspaces_p6_5.py`: membership scope,
cross-workspace isolation, private-by-default, explicit-share-required, share owner/workspace
validation, revocation, deleted-resource invalidation, invite single-use, invite expiry,
foreign-invite rejection, role-escalation prevention, admin-not-data-superuser.
`scripts/eval_platform_admin.py` + `tests/test_platform_admin_p6_5.py`: admin authorization,
normal-user 403, metadata-only view, audited entitlement/role changes, self-lockout,
workspace metadata boundary, reviewer reuse, prompt-lab boundary, feedback boundary,
privacy-request boundary, provider secret safety, audit safety.

## Evaluation
`eval_workspace_security` (now incl. `operational_allowlist_truthful`) and
`eval_platform_admin` are wired into CI alongside the existing gates. Backend suite: 2352
passed, 3 skipped (P6.5 closure adds the per-type sharing security matrix). Frontend: **222**
unit tests (adds role-aware nav coverage); **Playwright** adds `workspaces.spec.ts` +
`admin.spec.ts` (5 cases); lint/typecheck/build green. Paid/live calls: 0.

**Test-responsibility division:** backend Python suites
(`test_workspaces_p6_5`, `test_sharing_p6_5`, `test_platform_admin_p6_5`, and the two eval
scripts) are the **authoritative security evidence** (membership, invitation single-use/
expiry/foreign-rejection, per-type share owner/workspace validation, revocation, deletion
invalidation, cross-workspace isolation, admin-not-superuser). Playwright covers the
**browser-level UX states** (rendering, create/revoke interactions, role-aware nav gate,
admin-only access) using deterministic network mocks — it complements, never replaces, the
server-side tests.

## Known limitations
- Global account hard-delete cascade for private files + agent checkpoints remains PARTIAL
  (carried) — deletion is not claimed complete.
- Sharing is VIEW-only; no edit permissions (by design).
- Operational share types are **interview report + story** (both fully wired + tested).
  **Preparation summary is PLANNED / NOT YET WIRED** (no durable owned resource) and is
  excluded from the operational allowlist.
- The `SharingService` owner-verifier/loader map is extensible: adding a new operational
  type requires a durable owner-scoped loader + a bounded VIEW projection (the access
  DECISION is already enforced generically).

## Deferred enterprise features (§37/§48, NOT built)
Billing/Stripe, enterprise SSO/SAML/SCIM/HRIS, directory sync, org hierarchy, custom roles,
workspace chat/channels, task management, document collaboration, candidate ranking, hiring
decisions.
