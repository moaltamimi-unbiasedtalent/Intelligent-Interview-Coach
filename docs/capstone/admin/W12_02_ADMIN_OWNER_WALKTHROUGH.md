# W12.2 Admin Owner Walkthrough

**Status: PREPARED - AWAITING OWNER ACCEPTANCE.**

Claude's technical verdict: **TECHNICALLY READY FOR OWNER REVIEW** (no blocker found). This document is a preparation package for Mo. It is not owner acceptance, and no owner decision has been recorded anywhere in it. Nothing was changed in the product: every finding below is recorded, not fixed.

## 1. Environment
- Base: `main` at `9aa3cf55a19814e70b50db5e578845d236f7466e` (W12.1, PR #144, merged). Date: 2026-10-12.
- Isolated runtime: a fresh temporary SQLite database migrated to `0025_security_audit_incidents`, API in development mode with the in-memory email provider and the MOCK billing adapter, Next.js dev server on port 3015, API on port 8020. No developer store was opened.
- Real authorization path: every account signed in through `/auth/login`; nothing was spoofed in the browser. `GET /auth/me` for the owner account returned `platform_role = platform_admin` and 43 `admin_permissions`.
- Synthetic data only (fictional `@example.test` accounts): two `platform_admin` owners (so every two-person flow could be exercised with distinct actors), one account for each specialist preset, three candidates, one workspace, one opportunity, one support ticket, one privacy request, one legal draft, one security incident, one AI configuration draft and mock billing invoices and payments. Credentials are held in a local, owner-only temp file and are not part of this repository.
- Paid or live calls: **0**. The protected developer stores were fingerprinted before and after and are identical to the accepted baseline.
- Evidence (screenshots and run logs) is kept outside Git, because the repository has no established evidence-image convention: `/Users/moaltamimibanqr/Downloads/outputs/w12-02-admin-walkthrough-evidence/` (`desktop_and_flows/` and `responsive/`, with the JSON run logs alongside).

## 2. Admin architecture under review
- `platform_admin` is the platform owner / orchestrator with all 43 canonical control-plane permissions (AD-W12-01, implemented in W12.1). Specialist roles (support_operator, billing_admin, knowledge_admin, security_privacy_admin, operations_admin) are unchanged least-privilege delegated presets.
- 43 / 43 is not a private-content superuser: there is no permission to read a CV, document, answer, Mo conversation, memory or evidence, no break-glass, no impersonation or view-as. Routes are permission-gated, never role-name-gated. Step-up, two-person approval, expected revisions and audit are not bypassed by the owner.
- **Counts (inspected, not assumed):** the literal `ADMIN_DESTINATIONS` table has **19** entries, and the owner sees all 19 in the Admin navigation. W12.1's "20 destination groups" was a miscount in that wave's QA note: there are 19 (the Review and Diagnostics destination leads to `/review`, which has three child surfaces but is not a twentieth navigation item). The corrected figure is also recorded here so it is not carried forward.
- **Child and detail routes exercised:** `/admin/users/{id}` (three accounts), `/admin/workspaces/1`, `/admin/support/{ref}`, `/admin/plans/1`, `/admin/privacy/{ref}`, `/admin/integrations/openrouter`, `/admin/ai/{id}`, `/review/agent`, `/review/rag`, `/review/evaluation`, and the five Security tabs (Security events, Audit, Incidents, Alerts, Role approvals). No route was invented.

## 3. Technical pre-flight (Claude)
| Check | Result |
|---|---|
| Owner reaches all 19 destinations and 10 child routes | yes, 0 unexpected 403, 0 failing API calls, 0 console errors, 0 page errors, no stack trace, no "Something went wrong" |
| Single `h1`, every control named, every table has headers | yes on 22 pages scanned |
| Keyboard order | skip link, header, then the 19 Admin links in order; Security uses real tabs |
| Private-content boundary | no CV, answer, Mo conversation, Story Bank or preparation content appears on any page; the Support ticket shows only the message the candidate sent to Support, labelled as visible to the candidate, and states that CVs, documents, answers and Mo chats are not available |
| Mock and unavailable states | labelled truthfully everywhere (see section 4) |
| Horizontal overflow at 1280, 1024, 768 | none |
| Horizontal overflow at 390 | Integrations 105 px and AI and models 1 px (see F-04); all other sampled pages 0 |
| Light and dark | both render with correct page backgrounds; sampled pages readable |

**Expected governance blocks (not defects).** Two API calls returned 403 during the run: a role-change request before the password step-up, and an approval before the second administrator's step-up. Both are the designed step-up behaviour, and the UI then prompted for the password. The owner who requested a role change saw only "Cancel request" and the second administrator saw "Approve / Reject": a requester cannot approve its own request. A pending role-change request remains in the walkthrough database, unapproved.

## 4. Destination inventory
Claude preflight is a technical and UX read only. **Owner decision is PENDING for every row.**

| Destination | URL | Purpose | Key actions and governance | Technical status | Claude preflight | Owner decision |
|---|---|---|---|---|---|---|
| Overview | `/admin` | Command Center: build, migrations, runtime, counts per domain | read only | live; build details show "unknown" in dev; health is "not tested" until a manual test | ACCEPT WITH FOLLOW-UP (F-08, F-07) | PENDING |
| Users | `/admin/users`, `/admin/users/{id}` | account metadata, role, plan, sessions | deactivate, force logout (confirmation, optional reason, audited); role change request (reason, step-up, a different Admin approves); plan change | live, metadata only | ACCEPT WITH FOLLOW-UP (F-07, F-12, F-14, F-16) | PENDING |
| Workspaces | `/admin/workspaces`, `/{id}` | workspace and membership metadata | member and plan management | live, metadata only | ACCEPT | PENDING |
| Plans | `/admin/plans`, `/{id}` | plan versions and entitlements | draft, activate, retire; active versions immutable | live; entitlement, not billing | ACCEPT WITH FOLLOW-UP (F-10) | PENDING |
| Support | `/admin/support`, `/{ref}` | queue, ticket, reply, internal notes | status, priority, assign, reply (candidate-visible), internal note (staff only) | live; no attachments, SLA or email | ACCEPT | PENDING |
| Review / Diagnostics | `/review` (+ agent, rag, evaluation) | reviewer diagnostics | read only | live, offline metrics only | REQUIRES CHANGE (F-01, F-02) | PENDING |
| Security | `/admin/security` | events, audit history and export, incidents, alerts, role approvals | role approvals need a different Admin and a password step-up; incident and alert changes audited | live; in-app alerts only, no external paging | ACCEPT WITH FOLLOW-UP (F-06) | PENDING |
| Audit | `/admin/audit` | privileged-action log | read only | live, append-only at the database | REQUIRES CHANGE (F-06) | PENDING |
| Billing | `/admin/billing` | mock invoices, payments, commercial terms, refunds, approvals | refund and price change need a different approver | **MOCK, not live**, unmistakable banner | ACCEPT WITH FOLLOW-UP (F-05, F-11) | PENDING |
| Privacy | `/admin/privacy`, `/{ref}` | request queue and workflow state | assign, status, deletion through the existing deletion service, index historical runs (confirmation) | live workflow state; no content access; "not a statement of legal compliance" | ACCEPT WITH FOLLOW-UP (F-07) | PENDING |
| Legal | `/admin/legal` | document versions, publish, acceptance counts | publish (confirmation: immutable, retires the previous version) | live metadata; "not a compliance measure" | ACCEPT WITH FOLLOW-UP (F-07) | PENDING |
| Knowledge | `/admin/knowledge` | governed sources and version lifecycle | upload, review, approve, index, activate as separate explicit steps | live; nothing retrievable until approved, indexed and activated | ACCEPT | PENDING |
| Reports | `/admin/reports` | aggregate product, quality, operations, AI economics, mock commercial | read only | live; small cohorts suppressed; unknown is never zero | ACCEPT WITH FOLLOW-UP (F-09) | PENDING |
| Configuration | `/admin/configuration` | durable platform pause | pause or resume (reason required, expected revision, confirmation) | live; "What this page does not do" is explicit | ACCEPT WITH FOLLOW-UP (F-12) | PENDING |
| Feature flags | `/admin/flags` | two code-defined flags | override or reset (reason required, expected revision, confirmation) | live; a flag can only restrict | ACCEPT WITH FOLLOW-UP (F-12, F-15) | PENDING |
| AI and models | `/admin/ai`, `/{id}` | governed model configuration | draft, validate, evaluate, request approval; a different approver activates | deterministic checks only; no live model call; code defaults active | ACCEPT WITH FOLLOW-UP (F-04) | PENDING |
| Jobs | `/admin/jobs`, `/{id}` | queue and worker diagnostics | queue diagnostic job, retry, cancel queued | live; worker is a separate process and is not running here ("Never" reported) | ACCEPT | PENDING |
| Integrations | `/admin/integrations`, `/{code}` | nine supported connections: configuration, runtime, health | manual connection test only | credentials externally managed and read-only; health "not tested" | ACCEPT WITH FOLLOW-UP (F-04, F-13, F-17) | PENDING |
| Provider status | `/admin/providers` | configuration status of five providers and OCR | read only | configuration only, "configured does not mean healthy" | ACCEPT WITH FOLLOW-UP (F-17) | PENDING |

### What each risk-sensitive area shows
- **Mock billing.** A banner states "MOCK BILLING - NOT LIVE BILLING" with no checkout, payment-method collection, card data or tax engine; every record is labelled MOCK and refunds say no real money moves; the counts carry no revenue figure. Nothing found that could be mistaken for real money movement.
- **Secret rotation.** The owner holds the rotation permission, but the Integrations detail page shows the credential as "Managed outside Ask4Mo ... cannot be viewed or changed here" and offers no rotation control. The backend returns a read-only conflict if called directly (covered by tests). This is the expected outcome, recorded as a known limitation (F-13).
- **Knowledge governance.** The page states that a source is never used until scanned, parsed, reviewed, approved, indexed and explicitly activated; authority levels read "Level 3: reputable public industry research" and the licence defaults to "Unclear (cannot be activated)".
- **Privacy and legal.** Wording avoids compliance claims ("Nothing here is a statement of legal compliance", "not a compliance measure"); the indexing action explains that it reads no chat content; publishing explains immutability and that candidates are not forced to re-accept.
- **Reporting.** Aggregate only, with the suppression floor stated; in this small environment every product metric correctly shows "Suppressed: small cohort", never zero.
- **AI and models.** Evaluations are described as deterministic checks that do not measure live answer quality; the three environments, code defaults, approval and rollback are explained.

## 5. Findings
Severity counts: **BLOCKER 0, HIGH 0, MEDIUM 6, LOW 11. Total 17.** Owner decision is PENDING for each.

| ID | Surface | Description | Evidence | Severity | Type | Recommended action | Owner decision |
|---|---|---|---|---|---|---|---|
| F-01 | Review / Diagnostics | `/review` renders outside the Admin shell: no Admin side navigation and no way back to Admin except the global header menu | `d_review-1280-light.png` | MEDIUM | NAVIGATION | render the three diagnostic pages inside the Admin shell, or add an explicit "Back to Admin" link | PENDING |
| F-02 | Review / Diagnostics | page copy is developer-facing ("For reviewers & developers", "Slightly more technical, same design system") | same | LOW | COPY | rewrite for an Admin owner | PENDING |
| F-03 | Admin navigation at 390 px | the 19-item navigation stacks above the content (about 640 px), so the first screen is navigation only | `responsive/r_light_390__admin_*.png`, `walk7.json` (navH 644) | MEDIUM | NAVIGATION | collapse into a menu or select on narrow widths | PENDING |
| F-04 | Integrations (and AI and models) at 390 px | the integrations table overflows the page by 105 px and clips the Credentials and Health columns; AI and models overflows by 1 px | `r_light_390__admin_integrations.png`, `walk7.json` | MEDIUM | VISUAL | card layout or scroll container for narrow widths | PENDING |
| F-05 | Billing | "Request mock refund" and "Propose terms" open their forms at the bottom of the page, off screen, and focus stays on the button | measured: form heading not in the viewport after click; `j_billing_refund.png` | MEDIUM | UX | move focus and scroll to the form, or use a dialog like other Admin actions | PENDING |
| F-06 | Audit | two audit surfaces: `/admin/audit` is a bare list with raw field names (`created_at`, `event_type`, `actor_user_id`), mid-word wrapping ("succe ss") and an empty "change" column, while filters and export live only under Security, Audit | `d_admin_audit-1280-light.png`, `j_security_Audit.png` | MEDIUM | UX | make Audit the single filtered, readable surface or link the two | PENDING |
| F-07 | Several | raw timestamps with microseconds, snake_case table headers and 32-character references shown in full | billing, privacy, support, users, reports screenshots | LOW | COPY | format dates, humanise headers, truncate references with copy | PENDING |
| F-08 | Overview | long page (13 panels); the Security panel renders after the boundary footnote; some copy cites raw paths ("changed at /admin/configuration") instead of links | `d_admin-1280-light.png` | LOW | UX | prioritise warnings, order panels, link paths | PENDING |
| F-09 | Reports | in a small environment all 15 product metrics show the same "Suppressed: small cohort" card | `d_admin_reports-1280-light.png` | LOW | UX | summarise suppressed metrics in one line | PENDING |
| F-10 | Plans and Billing | Plans says "No prices or payments" while Billing holds mock commercial terms; each is accurate but the relationship is not explained | both screenshots | LOW | TRUST | cross-reference the two pages | PENDING |
| F-11 | Billing | refund amount is entered in minor units (cents) | `j_billing_refund.png` | LOW | UX | money input with currency formatting | PENDING |
| F-12 | Users, Configuration, Flags | high-risk buttons (Deactivate, Force logout, Pause, Disable override) look the same as neutral buttons; the confirmation dialogs are clear and truthful | dialog texts in `walk3.json` | LOW | UX | stronger visual treatment for high-risk actions | PENDING |
| F-13 | Integrations | the owner is authorised for secret rotation but sees no rotation control, because the store is externally managed and read-only | `i_integration_openrouter.png` | LOW | KNOWN LIMITATION | none; explain in the Admin journey document | PENDING |
| F-14 | Users | a development-only anonymous "Account 11 / Local developer" account appears in the list, and in development the anonymous identity makes the sign-in page redirect to onboarding; production is fail-closed | `d_admin_users-1280-light.png` | LOW | KNOWN LIMITATION | none for production | PENDING |
| F-15 | Feature flags | the "Not configurable here" list shows raw environment-variable names | `d_admin_flags-1280-light.png` | LOW | COPY | plain-language labels | PENDING |
| F-16 | Users, Integrations | inline table links are under 24 px high | accessibility scan in this run | LOW | ACCESSIBILITY | larger hit areas | PENDING |
| F-17 | Integrations and Provider status | the two destinations overlap (Provider status is a subset of Integrations plus OCR) | both screenshots | LOW | NAVIGATION | merge or cross-link | PENDING |

Also recorded, not owned by this wave: the candidate header logo and "More" overlap at 390 px is visible on Admin pages too (existing known follow-up; not fixed here).

## 6. Responsive and theme review
- 1280 px: all 19 destinations captured in light, all readable, no overflow.
- 1024 and 768 px: ten representative complex pages measured in light and dark (screenshots kept only for the 768 px Billing page), no horizontal overflow.
- 390 px (ten pages, light and dark): navigation is usable but pushes content down (F-03); tables sit in scroll regions with one real overflow (F-04); the confirmation dialogs fit; billing forms need scrolling (F-05); action buttons wrap correctly.
- Dark and light both applied correct backgrounds; no contrast problem was noticed in the sampled screens (visual inspection, not a contrast audit).

## 7. Known accepted limitations (not findings)
- Billing is mock only; there is no live provider, checkout or revenue.
- The environment SecretStore is externally managed and read-only; rotation is authorised but not technically available.
- Provider health is "not tested" until a manual test; no live provider test was run.
- Google OIDC live validation is outstanding, and Redis distributed rate limiting is not validated live (in-memory per process).
- Email is not live; alerts are in-app only; there is no external paging.
- PostgreSQL append-only audit triggers are rendered and unit-checked, not executed live.
- Step-up is password re-authentication, not MFA.
- Document OCR live quality is UNVALIDATED; live AI answer quality is not measured by the deterministic evaluations.
- Other ACCEPTED W11 and RC-P10-003 release-matrix limitations that apply to Admin remain as recorded there.

## 8. Owner acceptance (for Mo to complete)

[ ] ACCEPT ADMIN OWNER EXPERIENCE
[ ] ACCEPT WITH FOLLOW-UP ITEMS
[ ] REQUIRES CHANGES BEFORE ACCEPTANCE

Owner notes:

Owner decision date:

## 9. State after this wave
Owner acceptance: not given. Journey documentation, integrated Candidate and Admin requalification, RC-P10-004 and P10C have not started. AC-24 remains PARTIAL. The historical Pilot 2 verdict is unchanged.
