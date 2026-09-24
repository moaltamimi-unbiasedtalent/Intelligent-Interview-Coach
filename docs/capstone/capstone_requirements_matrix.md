# Ask4Mo Capstone — Canonical Requirements Matrix

One reconciled inventory across the v3 controlling plan, the reference package, and verified code.
Status: DELIVERED / PARTIAL / ABSENT / UNVALIDATED / BLOCKED / OUT_OF_SCOPE. Stable IDs map to the
reference package's A/B/C/K IDs and the D1–D9 platform additions; groups A–L organise them for the
Capstone. Acceptance gates reference AC-01–25 (`reference/03_Release_Acceptance_Checklist.md`) and
EX-01–16 (`reference/02_Expanded_Acceptance_Checklist.md`).

## Group A — Core product (carry-forward + gaps)
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| A1 | History detail + report | DELIVERED | Preserve, account-scope | P2 | AC-04 |
| A2 | Active-session discovery/resume | ABSENT | Discoverable owned unfinished sessions | P2 | AC-05 |
| A3 | Progress metrics | DELIVERED | Preserve | P2 | AC-06 |
| A4 | Sources catalogue + links | DELIVERED | Preserve | P2 | AC-07 |
| A5 | Knowledge readiness distinction | PARTIAL | Distinguish catalogue/snapshot/live | P2/P6 | AC-07 |
| A6 | Owned recent agent-run list | ABSENT | Owned run discovery | P6 | AC-18 |
| A7 | Evaluation evidence UI | DELIVERED (data env-dep) | Correct artifact provenance | P6 | AC-18 |
| A8 | Retrieval/RAG diagnostics | PARTIAL (overview only) | Selected-run evidence | P6 | AC-18/22 |
| A9 | Report export + completed-history deletion | ABSENT | MD/JSON export + confirmed deletion (PDF optional) | P4 | EX-01 |

## Group B — Agent / orchestration
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| B-agent | ReAct/goal-based bounded agent | DELIVERED | Preserve | — | AC-15/16 |
| B-tools | 6 career + 2 HITL tools, allowlist | DELIVERED | Preserve; add specialist tools | P5 | AC-15 |
| C4 | Preparation + Evaluation specialists (multi-agent) | ABSENT | Bounded orchestrator/specialist | P5 | EX-05 |
| B8 | Mo coordinates Research/Candidate specialists | PARTIAL | Bounded delegation | P5 | AC-15/16 |

## Group C — Knowledge / RAG
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| C-rag | Governed agentic RAG | DELIVERED | Preserve | — | AC-07/22 |
| K1 | Germany occupation compensation | ABSENT | Bounded reviewed dataset | P6/E6 | EX-13 |
| K2 | Credentials / regulated professions | ABSENT | Declared jurisdiction matrix | P6/E6 | EX-14 |
| K3 | Emerging roles / aliases | ABSENT | Versioned aliases | P6/E6 | EX-15 |
| K4 | Additional Adzuna capabilities | ABSENT | Entitled ops as bounded tools | P6/E6 | EX-16 |

## Group D — Platform productisation (owner-added)
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| D1 | Admin Console | ABSENT | Bounded PLATFORM_ADMIN control plane | P1 foundation → P6 | new AC (admin authz) |
| D2 | Platform roles / RBAC | ABSENT | USER / PLATFORM_ADMIN | P1 | AC-02 ext |
| D3 | Basic/Premium entitlement model | ABSENT | Entitlement dimension (no billing) | P1 | new EX (entitlement) |
| D4 | Server-side entitlement enforcement | ABSENT | Enforced at API/service | P1→P6 | new EX |
| D5 | User privacy/data controls | PARTIAL | Export/delete/consent self-service | P1/P4/P6 | EX-01, privacy |
| D6 | Privacy/legal public surfaces | ABSENT | Policy/terms/AI-transparency pages | P8 | AC-25 |
| D7 | Public marketing website | ABSENT | Public front door | P8 | AC-25 |
| D8 | Public/authenticated route separation | ABSENT | Route boundary | P1/P8 | AC-01/19 |
| D9 | Pricing/product presentation | ABSENT | Basic/Premium presentation | P8 | AC-25 |

## Group E — Identity / collaboration
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| B1 | Registration + verified login + logout/expiry | PARTIAL (transitional subject) | Real backend-verified accounts | P1 | AC-01/03 |
| C6 | Social + email auth, recovery | ABSENT | One social + email verify + recovery | P1 | EX-07 |
| C5 | Teams/workspaces + roles + invitations | ABSENT | Bounded workspace model | P6 | EX-06 |
| P/share | Explicit resource sharing + revocation | ABSENT | Selected-resource shares | P6 | EX-06 |

## Group F — Candidate data / documents
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| B4 | Private document library (PDF/DOCX/TXT) | ABSENT | Upload + extract + review + index | P4 | AC-08/09/10 |
| C2 | OCR (scanned PDF/images) | ABSENT | Bounded OCR worker, provenance | P4/E2 | EX-03 |
| C7 | Evidence/story bank | ABSENT | Source-backed STAR drafts | P3/E3 | EX-08 |
| B2–B3 | Profile + opportunities | PARTIAL | Durable scoped context | P1/P6 | AC-03/17 |

## Group G — Interview Practice
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| G-practice | Durable Practice + evaluation + report | DELIVERED | Preserve | — | AC-04/17 |
| B6–B7 | Recorded answers + spoken questions | PARTIAL (experimental) | Recorded mode + spoken Qs | P7 | AC-13/14 |

## Group H — Speech / multimodal
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| B5 | App-wide dictation | ABSENT | Every eligible input, editable transcript, no auto-submit | P3/P8 | AC-11/12 |
| C1 | Realtime voice + interruption | PARTIAL/experimental | Streaming + interrupt + fallback | P7 | EX-02 |
| C3 | Multilingual speech (EN/DE) | ABSENT | Real EN/DE STT/TTS | P7 | EX-04, AC-23 |

## Group I — Evaluation / observability
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| I-eval | Deterministic agent/retrieval eval | DELIVERED | Extend (separate suite) | P9 | AC-22 |
| I-ragas | RAGAS harness (opt-in paid) | DELIVERED | Preserve | P9 | AC-22 |
| C8 | Per-operation model policy | PARTIAL (registry) | Server allowlist per op | P5/E4 | EX-09 |
| I-obs | Observability (optional Langfuse) | DELIVERED | Preserve | — | — |

## Group J — Security / privacy
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| J-authz | Object-level ownership / cross-user isolation | DELIVERED | Extend to teams/shares/docs | P1/P6 | AC-02 |
| J-privacy | Data export/delete/retention | PARTIAL | Full lifecycle + policy | P1/P4/P6 | EX-01/10 |
| J-inject | Injection/SSRF guards | DELIVERED | Extend to docs/OCR | P4 | EX-03 |

## Group K — Deployment / operations
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| C12 | Public hosting (HTTPS, verified-email reg) | ABSENT | Reproducible deploy + limits + rollback | P8 | EX-12 |
| C9 | Bulk retention cleanup | PARTIAL (`cleanup_runtime_data.py`) | Dry-run + bounded batches | P6/E7 | EX-10 |
| C11 | Prompt Lab (admin-only) | ABSENT | Versioned synthetic experiments | P6/E6 | EX-11 |

## Group L — Marketing / product experience
| ID | Requirement | Current | Target | Phase | Acceptance |
|---|---|---|---|---|---|
| L-mkt | Marketing site + positioning | ABSENT | Public IA + pricing + trust | P8 | AC-25 |
| C10 | Guided onboarding / Help | DELIVERED | Preserve/adapt | P8 | AC-19 (C10 optional) |

## Totals (P0/E0 snapshot)
DELIVERED ≈ 20 · PARTIAL ≈ 12 · ABSENT ≈ 22 · OUT_OF_SCOPE (see exclusions) · UNVALIDATED: eval/knowledge data on fresh clone · BLOCKED: none at planning stage (auth/hosting/providers require owner authorization to *activate*, not to *plan*).

## Explicit OUT_OF_SCOPE
Camera/emotion/biometric assessment; recruiter rankings; automatic job applications; unrestricted crawling / job-board scraping; autonomous prompt/code/model changes; plugin marketplace; billing/payment; enterprise SSO/SCIM/HRIS; whole-app UI translation; comprehensive enterprise administration. Spoken feedback and PDF export remain optional enhancements.
