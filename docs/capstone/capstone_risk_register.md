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

## Owner decisions required (not blockers to P0/E0)
Weekly capacity; provider budget; chosen social IdP + email + STT/TTS + hosting providers; EU hosting
region; public-launch authorization; K1–K4 dataset selections; annual price; any paid/live run.
