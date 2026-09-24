# Ask4Mo Capstone — Security & Privacy Architecture

Extends the Sprint 4 controls (tool allowlist, injection/SSRF guards, output guard, user scoping,
sanitised logging/observability, fail-closed identity). Distinguishes **technical controls** from
**legal/policy** items that require appropriate review before public launch.

## Threat model (Capstone additions)
| Threat | Asset | Existing mitigation | Missing / to add | Phase | Test |
|---|---|---|---|---|---|
| Broken object-level authz / IDOR | any owned resource | ownership checks (Sprint 4) | extend to docs/evidence/recordings/shares | P1/P4/P6 | AC-02, neg tests |
| Cross-user access | candidate data | user_id scoping | keep on every new table | P1 | AC-02 |
| Cross-workspace access | shared resources | — | membership+share checks; re-check on async results | P6 | EX-06 |
| Privilege / admin escalation | platform ops | — | server-side PLATFORM_ADMIN gate; no superuser bypass | P1/P6 | admin neg tests |
| Entitlement bypass | Premium features | — | server-side entitlement enforcement | P1→P6 | EX-09-style |
| Malicious / oversized / MIME-spoofed uploads | ingestion | — | type/size/scan; no path traversal; sandboxed parse | P4 | AC-09 |
| Document / OCR prompt injection | agent | trust-separated retrieved DATA | treat extracted text as untrusted DATA | P4 | EX-03 |
| External-content prompt injection / SSRF / redirects | research | SSRF-safe fetch, allowlist | preserve; extend to any new fetch | P6 | eval_external_research |
| Stored XSS / unsafe markdown | rendered content | markdown sanitisation | keep for docs/stories/transcripts | P3/P4 | e2e |
| Secret / provider-credential / private-URL leakage | providers | env-only, sanitised logs | keep; audit new providers | all | secret scan |
| Candidate-data / transcript / audio exfiltration | private data | scoping | storage authz + signed URLs + retention | P4/P7 | privacy tests |
| Unsafe / revoked share access; deleted-data resurrection | shared/deleted data | — | revocation + cache/vector/backup cleanup | P6 | EX-06/10 |
| CoT / raw prompt / checkpoint / observability leakage | internals | Inspector safe projection | keep for all new surfaces | all | inspector tests |
| Rate-limit abuse / cost abuse | providers, cost | — | per-user + global limits, pause switch | P8 | EX-12 |

## Privacy data inventory (purpose · store · visibility · retention · deletion · LLM?)
| Category | Purpose | Store | Visibility | Retention | Deletion | Sent to LLM? |
|---|---|---|---|---|---|---|
| Account identity / verified email | auth | DB | self + admin(min) | account life | account delete | no |
| Social-auth identifiers | auth | DB | self | account life | account delete | no |
| Profile / opportunities | context | DB | self (+ explicit share) | account life | self-serve | context only |
| CV / documents / OCR output | preparation | object store + DB | self | user-set | self delete + derived cleanup | extracted text as DATA |
| Job descriptions / answers / evaluations / reports | practice | DB | self | account life | self delete / export | yes (bounded) |
| History / Progress | journey | DB | self | account life | account delete | no |
| Approved memory | personalisation | DB | self | until deleted | self delete | injected as DATA |
| Evidence / story bank | preparation | DB | self (+ explicit share) | account life | self delete | drafts only |
| Audio recordings / transcripts | speech practice | object store + DB | self | short/default, opt-in | self delete | transcript as DATA |
| Team/workspace data + shares | collaboration | DB | members per role | until removed | revoke/remove | no |
| External-research requests/results | current-market | ephemeral/cache | self | short | expiry | query only, no PII out |
| Observability metadata | ops | sink (optional) | platform | policy | policy | sanitised, no content |
| Feedback | improvement | DB | self + aggregate | policy | self delete | never into prompts |
| Audit events | governance | DB | platform admin | policy | retained | no |

## User-facing controls (technical)
Privacy info + data-usage transparency; consent where required; export my data (MD/JSON);
delete my data / account; memory management; document deletion; recording deletion;
sharing + revocation; retention visibility. **These are available to ALL users — never Premium-gated.**

## Public legal/product surfaces (require legal review before publication)
Privacy Policy · Terms of Use · Cookie/Tracking notice (if applicable) · AI transparency &
responsible-use · data export/deletion guidance · privacy-request contact · subprocessor disclosure.
Mark all formal legal conclusions/text as **requiring counsel review** — do not fabricate compliance.

## GDPR engineering implications (EU/Germany intended)
Lawful-basis + consent records; data-subject rights (access/export/erasure/rectification) wired to
real operations; data minimisation (store only what's needed; don't send PII to providers
unnecessarily); retention limits + deletion that reaches caches/vectors/backups; subprocessor
transparency; EU hosting/region decision before real user content; breach-response readiness.
These are **engineering requirements**; the **legal policy text and compliance sign-off are legal
tasks**, explicitly out of engineering's certification.

## Principle
Core privacy rights and security protections are baseline for every user and every tier. Server-side
enforcement everywhere; least privilege; private by default, including from team and platform admins.
