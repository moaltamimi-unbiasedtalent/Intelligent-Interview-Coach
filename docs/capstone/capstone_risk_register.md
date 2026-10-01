# Ask4Mo Capstone — Risk Register

Severity: P0 (blocker) · P1 (must fix before freeze) · P2 (documented, bounded) · P3 (future).
All evidence-backed at planning time; owner decisions noted where required.

| ID | Risk | Sev | Evidence | Mitigation | Phase |
|---|---|---|---|---|---|
| R-1 | Scope > available capacity by 20 Oct (11 extensions + 4 data areas) | P1 | Plan §11–§12 flags unresolved hours/budget/hardware | Feasibility checkpoints 4/8/13 Oct; MUST/SHOULD/COULD triage; owner decides scope vs date | P0, ongoing |
| R-2 | Identity is the critical-path spine; slippage blocks docs/teams/entitlements/admin/hosting | P1 | `auth.py` transitional only | Do P1 first; keep transitional subject until accounts stable | P1 |
| R-3 | Demo/eval knowledge data is gitignored → empty on fresh clone/host | P2 | artifacts absent on clean clone (alignment review) | `check_demo_knowledge.py` provisioning; document prerequisites; never fabricate | P0/P6/P8 |
| R-4 | Paid/live provider costs (LLM, STT/TTS, OCR, email, hosting) | P1 | providers unconfigured | Per-user + global limits, pause switch, budgets; activate only with owner authorization | P7/P8 |
| R-5 | Privacy/GDPR for real user data (EU) before public launch | P1 | no policy surfaces; new sensitive data (docs/audio) | Technical controls in P1/P4; legal text requires counsel review; EU hosting decision before real content | P4/P8 |
| R-6 | Cross-workspace / share-revocation / deleted-data resurrection | P1 | teams/sharing absent | Server-side authz on every path; revocation + cache/vector/backup cleanup tests | P6 |
| R-7 | Upload / OCR / document prompt-injection attack surface | P1 | ingestion absent today | Type/size/scan; extracted text as untrusted DATA; sandboxed parse | P4 |
| R-8 | Multi-agent complexity without measured benefit | P2 | single agent works well | Add specialists only where justified; keep single-agent baseline for comparison | P5 |
| R-9 | Speech accuracy/latency/cost across EN/DE | P2 | not wired | Recorded→STT→existing eval first; realtime deferred; measure on real samples | P7 |
| R-10 | Documentation contradictions mislead reviewers | P2 | 6 items in current-state doc | Docs-reconciliation pass (P0/P2); single current evidence index | P0 |
| R-11 | Entitlement/admin bypass via frontend-only hiding | P1 | no server entitlement/role yet | Server-side enforcement mandatory; negative tests | P1/P6 |
| R-12 | Hosting/public launch readiness (backups, rollback, limits) | P1 | single Dockerfile, no staging | Private staging first; explicit owner authorization for public | P8 |
| R-13 | Scope creep into excluded areas (crawling, billing, emotion, SSO) | P2 | broad ambition | Enforce exclusion list; every feature checked against it | all |
| R-14 | Provider lock-in / EU data handling | P2 | provider choices pending | Abstract interfaces; EU region; DPAs; mock/local paths | E0/P7/P8 |
| R-15 | Regression to Sprint 4 features during expansion | P1 | large surface | DoD requires green regression each phase; preserve tags | all |
| R-16 | Admin privilege creep: platform admin becomes a private-candidate-data superuser | P1 | W10 scope adds support/users/KB tooling | Capability-based authz, metadata-only defaults, governed break-glass only if approved (reason, time-box, audit), candidate-denied tests | W10.0/W10.2/W10.14 |
| R-17 | Mock billing/payment represented as live | P1 | W10.5 permits mock adapter | Visible mock/sandbox labelling in UI/docs/reports; qualification check | W10.5/W10.14 |
| R-18 | Secret exposure through admin integration/config UI | P1 | W10.6/W10.11 | Write-only secrets, rotate/disable/test only, no secrets in config/audit/logs/exports | W10.6/W10.11 |
| R-19 | Unqualified AI model/prompt activated by an admin | P1 | W10.7 | Draft->Validate->Evaluate->Approve->Activate; no bypass; second approver | W10.7 |
| R-20 | Manual KB upload becomes production RAG without provenance/safety review | P1 | W10.8 | Safety->Parse->Classify->Provenance/licence->Preview->Approval->Index; distinct upload/approve capabilities | W10.8 |
| R-21 | Admin scope (W10, 15 sub-waves, two XL) delays RC/Pilot 2/P10C | P1 | critical path in roadmap | W10.0 design gate; must-have vs mock-acceptable split; desirable waves may ship reduced | W10 |
| R-22 | Technical debt TD-W9-01/02 (invalid Tailwind opacity classes; test-isolation leak) reaches release | P2 | W9 register | Scheduled in W9.12; closure evidence required before W9.13 | W9.12 |

## Owner decisions required (not blockers to P0/E0)
Weekly capacity; provider budget; chosen social IdP + email + STT/TTS + hosting providers; EU hosting
region; public-launch authorization; K1–K4 dataset selections; annual price; any paid/live run.
