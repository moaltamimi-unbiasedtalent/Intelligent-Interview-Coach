# P10B — Information Architecture Proposal

_Analysis + recommendation only (no implementation). Compares the current IA against the
founder's proposed journey and recommends a target structure. Reuses existing capabilities;
proposes no destructive rename/migration in this phase._

## Current IA (as built)
```
/  (marketing)  →  /register or /sign-in  →  /app (candidate home / return journey)
app nav (primary):  Prepare · Practice · Progress · History
"More" menu:        Documents · Workspaces · Sources · Help · Review [· Admin if platform_admin]
account control:    avatar → /account  (Settings only via /account or /progress "Manage")
```
Problems (from the audit):
- **Flat feature list, no per-role container.** Prepare, Practice, Documents, Progress, History
  are parallel destinations; nothing ties "preparing for Role X at Company Y" together. Documents
  are a silo (G2/G5); company research is only an implicit Mo toggle (H1).
- **Settings/language buried**, no "Settings" nav entry (D1); `ACCOUNT_NAV` dead.
- **Workspaces is orphaned** for a solo candidate — it's collaboration/sharing only (I1), with an
  empty state that gives no reason to use it, and no "my prep space" concept (I2).

## Founder's proposed journey (to evaluate — not auto-accepted)
```
PUBLIC → GET STARTED → FIRST-RUN SETUP → MY HOME → OPPORTUNITIES →
ROLE/COMPANY { JD · Company Research · CV & Evidence · Prepare · Practice · Report · Progress }
→ HISTORY / EVIDENCE / ACCOUNT      (separately)  WORKSPACES → collaboration/sharing
```

### Assessment
**This materially improves clarity and matches how candidates actually think** ("I'm preparing
for *this job*"). It resolves the biggest structural issues at once:
- Introduces an **Opportunity** = a candidate's prep space for **one role/company**, which becomes
  the natural home for JD, company research, CV/evidence, Prepare, Practice, report and progress —
  directly fixing the Documents silo (G2/G5), the undiscoverable company research (H1), and the
  "features feel disconnected" perception.
- Cleanly **separates Opportunity (solo prep) from Workspace (collaboration/sharing)**, fixing the
  founder's confusion (I1/I2) without removing the existing, working sharing feature.
- Adds **First-run setup** (E1) and a **My Home** that lists Opportunities + continue-practice.

**Risks / caveats:**
- An Opportunity is a **new persistent concept → a new model + migration** (medium/large). It must
  reuse, not replace, existing interviews/documents/evidence/PreparationContext.
- Must **preserve** all current deep links (`/prepare`, `/practice`, `/documents`, …) during any
  migration (compatibility redirects), and not break the merged P8 marketing `/` ↔ `/app` split.
- Must keep **security/ownership/HITL/evidence-provenance** intact — an Opportunity is just an
  owner-scoped grouping; it grants no new cross-user access.

## Recommended target IA (phased, non-destructive)
Adopt the founder's structure **incrementally**, newest concept last:

```
PUBLIC SITE (/)                      ← redesign (Wave 7)
  └ Get started → FIRST-RUN SETUP    ← new wizard (Wave 2)
        └ MY HOME (/app)             ← return journey + Opportunities list (Wave 1 nav, Wave 6 opps)
             └ OPPORTUNITY (role/company)          ← new container (Wave 6)
                  ├ Job Description  (upload/paste; reuse Documents + JD text)
                  ├ Company Research (directable UI over research/*)   ← Wave 5
                  ├ CV & Evidence    (reuse Documents + EvidenceAccessService) ← Wave 3/4
                  ├ Prepare          (existing Agent Coach, scoped to the opportunity)
                  ├ Practice         (existing interview flow, scoped)
                  ├ Interview Report (existing)
                  └ Progress         (existing, scoped)
        └ HISTORY · EVIDENCE · ACCOUNT/SETTINGS   ← global (Wave 1 IA)
WORKSPACES (/workspaces)            ← keep as collaboration/sharing; reframe copy (Wave 6)
ADMIN (/admin)                      ← unchanged authz; discoverability doc only (Wave 1)
```

### Global chrome fixes (independent of Opportunity — do first, Wave 1)
- Add a **Settings** entry to the account menu (wire the dead `ACCOUNT_NAV`), and surface
  **Account & Settings** as a coherent hub (D1/D2).
- Add a **language switcher** to the app header and marketing chrome (C4/B5), reusing
  `I18nProvider.setLocale` / `LanguageSettings`.
- Add a **mobile marketing nav** (B5).

### Opportunity vs Workspace (explicit product decision to ratify)
| Concept | Definition | Owner | Sharing | Status |
|---|---|---|---|---|
| **Opportunity** (proposed) | a candidate's private prep space for ONE role/company (groups JD, company research, CV/evidence, Prepare, Practice, report, progress) | single candidate | private by default | **new** (Wave 6; new model + migration) |
| **Workspace** (exists) | controlled collaboration: invite members, VIEW-only share a report/story | owner + members | explicit VIEW grants only | keep; **reframe copy** so it reads as "sharing with people", not "my prep space" |

Recommendation: **introduce Opportunity; keep Workspace unchanged in behaviour** but reword its
purpose/empty-state so the two are clearly different. Do **not** rename or migrate Workspace data.

## Migration/compat notes (for later waves, not now)
- New `opportunity` table (owner-scoped) linking existing `interviews`, `candidate_documents`,
  claims/stories, and a per-opportunity JD/company field; strictly additive.
- Backfill/compat: existing standalone sessions/documents remain valid (an Opportunity is
  optional grouping, not a hard requirement) — avoids a breaking data migration.
- Keep every current route working; add opportunity-scoped routes alongside.

## Verdict
The founder's IA is a **genuine improvement** and should be adopted **incrementally**: global
nav/settings/language integrity first (Wave 1, no migration), then the Opportunity container
(Wave 6, additive migration), with Documents/Prepare/Practice/Company-research integration
(Waves 3–5) feeding into it. Workspace stays as-is (collaboration), reframed in copy.
