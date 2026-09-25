# P6.5 — Authorization & Sharing Design

_Written before implementation. It fixes the vocabulary so the workspace + admin work
never collapses distinct concepts into one `role` field, preserving the P1 principle that
these dimensions are **orthogonal**._

## The ten orthogonal concepts

| # | Concept | Question it answers | Where it lives | Notes |
|---|---|---|---|---|
| 1 | **Identity** | Who is this account? | `users` (id, email, created_at) | Stable account identity. |
| 2 | **Authentication** | Has the caller proven they are this identity now? | server-side session cookie (P1) | Session ≠ identity ≠ authorization. |
| 3 | **Platform role** | Ordinary user or platform operator? | `users.platform_role` = USER / PLATFORM_ADMIN | Global operations role. **Never a data superuser.** |
| 4 | **Workspace** | A bounded collaboration space | `workspaces` | Not a company/legal entity; name is a label only. |
| 5 | **Workspace membership** | Does this user belong to this workspace? | `workspace_memberships` (user_id, workspace_id) | A user may belong to 0..N workspaces. |
| 6 | **Workspace role** | What may a member do IN this workspace? | `workspace_memberships.role` = WORKSPACE_OWNER / WORKSPACE_MEMBER | Belongs to the **membership**, never to the User. Grants nothing outside its workspace. |
| 7 | **Product entitlement** | Which product tier/limits? | account tier (BASIC / PREMIUM) + capability map (P1) | **Separate dimension** — Teams ≠ Premium. |
| 8 | **Feature flag** | Is a capability enabled in this deployment? | server-authoritative flag | Client flags never override server authz. |
| 9 | **Resource ownership** | Who owns this candidate resource? | `owner_user_id` on the resource (reports, stories, …) | Ownership **stays with the candidate** — sharing never transfers it. |
| 10 | **Sharing grant** | Has the owner explicitly granted view of ONE resource into a workspace? | `share_grants` | Explicit, allow-listed, revocable, VIEW-only. |
| — | **Consent** | Did the owner deliberately choose to share? | the act of creating a share grant | Workspace membership is **not** consent to inspect an account. |

## The authorization decision (server-side, always)

```
allowed = ( caller owns the resource
            OR a VALID (unrevoked, non-expired) share grant exists
               for (resource, a workspace the caller is a member of) )
          AND workspace role permits the action
          AND product entitlement permits
          AND feature flag enabled
```

Frontend hiding is never the control. Route classes (per the target architecture):
**PUBLIC · USER · WORKSPACE · ADMIN · REVIEWER**.

## Private-by-default (the controlling rule)

**Personal candidate data is private by default.** Joining a workspace exposes **nothing**
automatically — not CVs/documents, extracted claims, Memory, interview answers, History,
Progress, Practice sessions, Story Bank or reports. The ONLY way another member sees a
resource is an explicit, owner-created, VIEW-only **share grant** for that specific
resource; revocation and source-deletion both cut access immediately.

## Shareable vs never-shareable

**Allow-listed shareable (VIEW-only, owner-initiated):** OPERATIONAL today = a selected
interview **report** and a selected approved **story/evidence** item (both durable,
owner-scoped, with wired owner loaders). A **preparation summary** is PLANNED / NOT YET
WIRED (no durable owned resource yet) and is excluded from the operational allowlist.

**Never auto/shareable:** raw uploaded document / full CV / raw extracted text, approved
**Memory**, authentication data, audit trail, account-recovery information. (These are not
in the share allow-list; an attempt to share them is rejected.)

## Platform Admin boundary (PLATFORM_ADMIN ≠ DATA_SUPERUSER)

Admin may inspect **operational/account metadata** (account status, verification, platform
role, entitlement, created date; workspace metadata; knowledge/eval/feedback/privacy-request
metadata; safe provider status; audit metadata). Admin may **NOT** inspect candidate-private
content (CV, answers, Memory, Story Bank, raw conversation, private documents). There is
**no "view as user"** and **no universal private-data search**. Owner-scoped repositories
stay owner-scoped — no `if admin: return everything`. Every privileged admin action is
audited.

## Teams ≠ Premium; no billing

Workspace/team access is a **separate capability dimension** from BASIC/PREMIUM. This phase
adds no billing, no Stripe, no enterprise SSO/SCIM/HRIS, no org hierarchy, no chat/channels,
no candidate ranking or hiring decisions (see §37/§38 exclusions).

## Deletion & lifecycle semantics (decided here)

- **Revoke a share** → immediate loss of access; a cached/shared link cannot bypass it
  (access is re-checked server-side on every read).
- **Delete the source resource** → all its share grants are invalidated; a grant never
  resurrects deleted content.
- **Member leaves / is removed** → their personal data stays theirs; **their outbound share
  grants into that workspace are revoked** (prefer revocation on leave).
- **Last owner** may not orphan a workspace: ownership must be transferred first, or the
  workspace is deactivated.
- **Workspace deleted/deactivated** → workspace share grants revoked; **member-owned
  candidate resources are never deleted**; candidate ownership preserved.
- **Account deletion** → memberships, invitations and outbound share grants are removed;
  owned workspaces require ownership transfer or deactivation. (The known private-file +
  LangGraph checkpoint purge gaps remain carried — global deletion is **not** claimed
  complete.)
