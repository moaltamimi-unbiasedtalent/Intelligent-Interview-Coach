# P10B Wave 8 - Integrated Qualification, Moderated Pilot & RC-P10-002

**Status:** PHASES 2-6 + 8 COMPLETE (qualification evidence gathered). Scope per owner instruction:
*"Just the qualification evidence, no RC and no pilot pack yet."* **RC-P10-002 NOT created** (deferred);
**Pilot-2 pack NOT built** (deferred). Wave 8 change footprint: **evidence only** - one new deterministic
evaluator, one new integrated-journey E2E spec, and this document. No product/runtime code changed.
**Branch:** `feature/capstone-p10b-wave8-release-qualification` (from `origin/main`).
**Baseline SHA:** `477d8c5` (Merge PR #96 = Wave 7; Waves 1-7 all merged).
**Migration head:** `0014_opportunities` (single head; graph linear 0001..0014; up/down/re-up valid).
**Previous RC:** `RC-P9-001` (`artifacts/capstone/p9/RC-P9-001/`, SHA `319759d`) - **immutable**. `RC-P10-002` does **not** exist yet.
**Pre-qualification decision:** **CONDITIONAL GO** (deterministic release readiness proven; live-provider
validation + second human pilot are the two documented STOP gates that remain).
**Paid/live/provider calls this wave:** 0.

Wave 8 qualifies the complete Ask4Mo candidate journey as one integrated product, validates it with a
second moderated human pilot, remediates only consequential evidence-backed defects, runs final
regression, and creates RC-P10-002 only if the release gate passes. It is NOT a feature wave.

## Baseline verification (empirical)
- `origin/main` = `477d8c5`; recent history: #96 (W7) ← #95 (W6) ← #94 (W5) ← #93 (W2 reintro) ← #89 (W4) ← #88 (W3) ← #87 (W1). No unexpected post-Wave-7 work.
- Working tree clean; branch cut cleanly from `origin/main`.
- Alembic: single head `0014_opportunities`. Migrations 0001..0014 linear.
- RC-P9-001 present + immutable; no RC-P10-002.
- Running dev servers (frontend :3015, backend :8020) are local conveniences, not part of the tree.

## Integrated architecture inventory (A-V)
| # | Subsystem | Primary implementation | Governance/notes |
|---|---|---|---|
| A | Identity/auth | `src/authsec/*`, `src/auth_repository.py`, `src/application/auth_service.py`, `src/api/routes/auth.py`, `dependencies.get_current_user_id/principal` | Session cookie; fail-closed in prod; Google OIDC live UNVALIDATED |
| B | Onboarding/personalisation | `frontend/components/onboarding/*`, `src/api/routes/auth.py` (onboarding), migration 0013 | Gate on `onboarding_completed`; coaching style tone-only |
| C | Opportunity | `src/persistence.py` (Opportunity), `src/opportunity*.py`, `src/api/routes/opportunity.py`, `frontend/app/opportunities/*` | Owner-scoped; private; migration 0014 |
| D | Company intelligence | `src/copilot/research/*`, `src/application/company_intelligence_service.py`, `src/api/routes/company.py` | FACT/REVIEW/MODEL_INFERENCE; providers NOT integrated |
| E | Documents | `src/documents/*`, `src/application/documents_service.py`, `frontend/components/documents/*` | Owner-scoped; OCR live UNVALIDATED; failure taxonomy (0012) |
| F | Evidence/provenance | `src/application/evidence_access_service.py`, story/claim repos | Approved-only; revocation propagates |
| G | Mo/orchestrator | `src/agent/*` (LangGraph) | Bounded tools; HITL; no user_id from model |
| H | Specialist agents | `src/agent/specialist_tools.py`, `src/agent/specialists/*` | Advisory; deterministic evidence specialist |
| I | Prepare | `frontend/components/agent/AgentPrepareWorkspace.tsx`, agent run API | Opportunity context prefill (W6) |
| J | Practice | `src/api/routes/interview.py`, durable session store, `frontend/components/interview/*` | opportunity_id association (W6) |
| K | Scoring/evaluation | `src/prompts.py`, interview evaluation | Coaching tone never changes scoring |
| L | Reports | `interviews`/`reports` tables, report export | Crash-safe idempotent save |
| M | History/progress | `src/api/routes/history.py`, `progress.py` | Owner-scoped |
| N | Language/i18n | `frontend/lib/i18n/*` (7 locales), bounded language directives | Interface≠conversation≠dictation≠geography |
| O | Dictation/voice | `frontend/lib/speech/*` | Turn-based; realtime live UNVALIDATED; no audio storage |
| P | Workspace/collaboration | `src/workspace_repository.py`, sharing_service | VIEW-only; distinct from Opportunity |
| Q | Admin | `src/api/routes/admin.py`, `require_platform_admin` | Metadata-only; not a data superuser |
| R | Security/privacy | `src/security.py`, `web_fetch` SSRF, guards, owner scoping | Injection-as-DATA; SSRF; fail-closed |
| S | Marketing/trust/pricing | `frontend/components/marketing/*`, `lib/pricing.ts` | Opportunity-centred (W7); no billing |
| T | Model/provider policy | `src/llm/policy.py`, `src/llm/models.py` | Per-op tiers; no slug from client |
| U | Observability/audit | `src/observability/*`, `audit_events` | Safe projections; metadata-only |
| V | Deletion/export/lifecycle | `src/application/account_deletion_service.py`, export | Cascade incl. opportunities (W6) |

## Known limitations carried into Wave 8
- **LIVE UNVALIDATED (0 paid calls, by policy):** company official-web fetch, Adzuna market data, realtime voice, OCR real-world quality, model-generated multilingual interview quality, all external model/provider paths. Google sign-in UNVALIDATED. Deterministic + fixture coverage exists for each.
- **Hosted deployment (EX-12): BLOCKED/NOT RUN** (no authorized deployment; artifacts READY).
- **Human validation: none yet** - AC-24 first pilot was PREPARED in P10A but NOT RUN; Wave 8's second moderated pilot also requires real humans.
- **Translations:** engineering draft (no human/legal review); Trust-card + Privacy/Terms/AI-transparency bodies English-only.
- **Opportunity sharing:** deferred (future seam over existing VIEW-only share model).
- **SQLite:** `opportunity_id` FK not DB-enforced (app-layer enforces); no raster OG image; no hreflang.
- **Pricing:** presentation-only (no billing; Premium is a preview) - by design.

## Release qualification criteria (RC-P10-002 GO gate)
RC-P10-002 may be created only if ALL hold: clean repo; single Alembic head + up/down/re-up valid;
backend regression green; frontend unit/lint/typecheck/build green; full Playwright green; all
required deterministic evaluators green; the Wave 8 integrated evaluator green; 0 unresolved P0; 0
unresolved P1; security/privacy/HITL/provenance boundaries pass; claims/pricing/provider status
truthful; public/private route boundaries pass; integrated candidate journey passes (desktop + 390px);
no test weakening; 0 unapproved paid/live calls; known limitations documented; every remaining
unvalidated live capability explicitly classified; human pilot plan ready. If any fails: **no RC**.

## Wave 8 qualification plan (phases)
1. **Phase 1 (this doc):** baseline + architecture inventory + criteria. [done, no code change]
2. **Phase 2 - Requirements traceability:** audit the capstone matrix vs implementation; status ladder (IMPLEMENTED / DETERMINISTICALLY TESTED / LIVE VALIDATED / HUMAN VALIDATED / PARTIAL / DEFERRED / N/A / BLOCKED); never collapsed.
3. **Phase 3 - Full integrated regression:** backend pytest + ruff + compile + OpenAPI + migrations up/down/re-up; frontend unit/lint/typecheck/build + full Playwright; discover + run ALL evaluators. Record counts/skips; 0 paid/live.
4. **Phase 4 - Wave 8 integrated evaluator:** `scripts/eval_release_candidate.py` - cross-system invariants (the 45 listed + any discovered). Deterministic, 0 paid/live.
5. **Phase 5 - Integrated candidate journey (E2E):** add only where existing coverage is insufficient; deterministic fakes; desktop + 390px + keyboard; no duplication.
6. **Phase 6 - Production-like qualification:** build/startup/env-validation/health/readiness/migrations-clean+upgraded/lifecycle/gates/pause/cost/degraded-provider/no-secret-in-bundle/no-private-in-logs - only what is achievable without external/paid calls.
7. **Phase 7 - Live/external validation gate:** inventory every CONFIGURED/IMPLEMENTED-but-NOT-LIVE-VALIDATED capability with a validation proposal (credential/cost/privacy/inputs/success+failure criteria). **STOP for approval before any paid/live call.**
8. **Phase 8 - RC pre-qualification GO/NO-GO.**
9. **Phase 9 - Create RC-P10-002** (only if GO), following the RC-P9-001 convention (`artifacts/capstone/p10/RC-P10-002/{manifest.json,gate_results.md}`), immutable.
10. **Phase 10 - Second moderated human pilot:** build `docs/capstone/p10/pilot2/*` pack (moderator guide, tasks 1-15, observation sheet, issue log, results, release decision). **Requires real humans - if none available here, prepare the pack and STOP.**
11. **Phase 11 - Pilot triage** (P0/P1/P2/P3/ENHANCEMENT/OBSERVATION) - only after real evidence.
12. **Phase 12 - Consequential remediation only** (evidence-backed; smallest coherent fix; regression coverage).
13. **Phase 13 - Final regression** + final capstone evidence matrix + final release decision (GO / CONDITIONAL GO / NO-GO).

---

# Wave 8 qualification evidence (Phases 2-6 + 8)

All commands run at branch tip over the merged Waves 1-7 baseline. Every result below is empirical
(executed this wave), not asserted. No paid/live/provider calls were made anywhere.

## Phase 2 - Requirements traceability (status ladder)
Ladder (never collapsed): **IMPLEMENTED** (code exists) · **DET-TESTED** (passing deterministic
tests/evals) · **LIVE-VALIDATED** (against a real paid provider) · **HUMAN-VALIDATED** (moderated
pilot) · **PARTIAL** · **DEFERRED** · **N/A** · **BLOCKED**. Source: `capstone_requirements_matrix.md`
(current through Wave 7). Wave 8 added no features, so status = the merged baseline, re-verified this wave.

| Group / ID | Capability | IMPLEMENTED | DET-TESTED | LIVE-VALIDATED | HUMAN-VALIDATED | Notes |
|---|---|:--:|:--:|:--:|:--:|---|
| A1-A4 | History / resume / progress / sources | ✅ | ✅ | ✅ (real accounts) | ⏳ pilot | owner-scoped |
| A5-A8 | Knowledge readiness / run+eval diagnostics | ✅ | ✅ | n/a | ⏳ | A6/A8 PARTIAL (diagnostics) |
| B-agent/tools, C4, B8 | Bounded agent + specialists + delegation | ✅ | ✅ (eval_agent, eval_multi_agent GATE PASS) | ❌ live model | ⏳ | deterministic path shipped |
| H1 | Candidate company intelligence | ✅ | ✅ (eval_company_intelligence) | ❌ official-web/Adzuna | ⏳ | FACT/REVIEW/INFERENCE separation |
| H2 | Live employer-review providers | ✅ links-out | N/A | **NOT INTEGRATED** (ToS) | N/A | UI links out; copies no content |
| I1/I2 (C) | Workspace vs Opportunity; Opportunity container | ✅ | ✅ (eval_opportunity_journey, eval_release_candidate) | n/a | ⏳ | mig 0014; owner-scoped/private |
| C-rag, K1-K4 | Governed RAG + knowledge datasets | ✅ | ✅ (knowledge_governance/retrieval GATE PASS) | ❌ Adzuna live/K4 | ⏳ | figures engineering-draft |
| D1-D9 | Admin / RBAC / entitlements / privacy / marketing / pricing / routing | ✅ | ✅ (platform_admin, identity, marketing_product_trust, account_deletion) | partial (Google live ❌) | ⏳ | no billing (by design) |
| B1/C6/C5/share | Accounts / social / teams / sharing | ✅ | ✅ (identity, workspace_security GATE PASS) | ❌ Google/email live | ⏳ | Google sign-in UNVALIDATED |
| B4/C2/C7/B2-B3 | Documents / OCR / evidence / profile | ✅ | ✅ (documents_evidence) | ❌ OCR real-scan accuracy | ⏳ | OCR runtime-available; accuracy not benchmarked |
| G-practice, B6-B7 | Durable Practice + turn-based voice | ✅ | ✅ (voice_experience, prepare_practice_integration) | ❌ live STT/TTS quality | ⏳ | text-only eval preserved |
| B5, C1, C3, E5 | Dictation / realtime voice / multilingual speech | ✅ | ✅ (dictation, realtime_voice, i18n) | ❌ realtime provider (no key) | ⏳ | C1 architecture DET-validated; live NOT RUN |
| I-eval/ragas, C8, I-obs | Eval suite / model policy / observability | ✅ | ✅ (multi_agent policy, quality_v2 offline) | ❌ ragas/judge (paid, NOT RUN) | n/a | deterministic baselines preserved |
| J-* | Ownership / audit / privacy / injection+SSRF | ✅ | ✅ (eval_security 22/22 detect, 0 FP; account_deletion) | n/a | ⏳ | fail-closed |
| C12/EX-12 | Public hosting | ✅ READY | ✅ (hosting_readiness) | **BLOCKED** (no authorized deploy) | n/a | artifacts ready; not deployed |
| C9/C11 | Retention cleanup / Prompt Lab | ✅ | ✅ (retention, prompt_lab GATE PASS) | n/a | ⏳ | no auto-promotion |
| L-mkt/L-mkt7/C10 | Marketing / Opportunity-centred story / onboarding | ✅ | ✅ (marketing_product_trust 32, onboarding) | n/a | ⏳ | engineering-draft copy; legal review pending |

**Traceability conclusion:** every in-scope capability is IMPLEMENTED and DET-TESTED. The only columns
not fully green are **LIVE-VALIDATED** (paid provider paths - deliberately not run; 0 paid calls) and
**HUMAN-VALIDATED** (second moderated pilot - not run; no participants in this environment). EX-12
(hosted deploy) remains BLOCKED. These are exactly the two STOP gates below. Nothing regressed.

## Phase 3 - Full integrated regression (all green)
| Check | Command | Result |
|---|---|---|
| Backend unit/integration | `pytest -q` | **2455 passed, 3 skipped, 0 failed/errored** (exit 0) |
| Backend lint | `ruff check src scripts` | clean |
| Backend compile | `python -m compileall src scripts` | clean |
| Migrations | `alembic upgrade head` → `downgrade base` → `upgrade head` | single head `0014`; up/down/re-up valid |
| OpenAPI | `create_app().openapi()` | generates; **112 paths** |
| Frontend typecheck | `tsc --noEmit` | clean (7-locale key parity enforced) |
| Frontend lint | `next lint` | no warnings/errors |
| Frontend build | `next build` | success (static + dynamic routes prerendered) |
| Frontend unit | `vitest run` | **282 passed / 53 files** |
| E2E | `CI=true playwright test` | **119 passed, 0 failed** (118 baseline + 1 new Wave 8 spec) |

**Evaluators (all 40 discovered under `scripts/eval_*.py`):**
- **28 gated evaluators PASS** - 17 print `RESULT: PASS` (incl. the new `eval_release_candidate` 27/27)
  and 11 print `GATE STATUS/GATE: PASS` (agent, multi_agent, platform_admin, workspace_security,
  knowledge_governance, knowledge_retrieval, feedback_learning, feedback_intelligence, external_research,
  prompt_lab, retention).
- **Security:** `eval_security` - 22/22 attacks detected, 0 missed, 0 false positives (detection 1.0, FP 0.0).
- **Diagnostic report-writers** (always exit 0; not hard gates): product_coverage (routing 100%,
  evidence hit@5 93%, citation 100%, tool 100%; `insufficient_evidence` 94% is an **offline/lexical**
  artefact of the keyless local hash embedder, not a regression), faithfulness_v2, quality_v2
  (Hit@5 0.917 / MRR 0.704 / tool 1.0 / OOD leaks 0), expanded, knowledge_expansion, rag, retrieval.
- **Live/paid evaluators correctly NOT RUN** (no keys, no spend): agent_judge, agent_live, ragas,
  retrieval_quality_v2 (semantic). Each self-skipped with an explicit "paid/live not authorized" notice.
- **0 evaluators FAILED. 0 paid LLM / provider / speech / OCR / realtime / live calls across all evaluators.**

## Phase 4 - Wave 8 integrated evaluator
`scripts/eval_release_candidate.py` - **27 cross-system invariants, all PASS**, 0 paid/live. Behavioural
checks run real services over in-memory SQLite (Opportunity + Company Intelligence with the deterministic
fake provider); structural checks grep the codebase. Covers: Opportunity privacy/owner-scoping,
foreign-id non-disclosure, JD owner-scoping + deletion-clears-linkage, Opportunity-delete preserves
history, governed Practice context (server-resolved JD via `_apply_governed_context`/`extracted_text`,
owner-verified `opportunity_id`), Prepare/Practice prefill-not-override, coaching-tone-never-scoring,
company FACT vs MODEL_INFERENCE, provenance/freshness, no-model-supplied-user_id, HITL boundary,
language-dimension separation, admin-not-superuser, account-deletion coverage, premium-preview-no-billing,
authenticated-routes-noindex, no-candidate-content-in-URLs, 7-locale namespace parity, marketing-claims
guard present, and `rc_gate_not_bypassed` (RC-P10-002 absent without a passing documented gate). Ruff clean.

## Phase 5 - Integrated candidate journey (E2E)
Assessment: existing E2E already covers the journey **in segments** (`journey.spec` connected
journey → handoff → approve → Practice; `opportunities.spec` create wizard + nav; `home-handoff`,
`company`, `documents`, `return-response`, `interview`, `progress`). One integration seam had **no
browser coverage**: launching Practice **from an Opportunity** (`/practice?opportunity=<id>`) and
proving the Wave 6 governed association survives the whole UI path. Added exactly one focused,
deterministic spec - **`frontend/e2e/opportunity-practice.spec.ts`** - mocked at the network layer:
open the Opportunity home → click "Start practice" (awaited client navigation) → assert the setup
prefills from the opportunity (context note + role, not overriding an explicit entry) → assert the
create request carries the owner-scoped `opportunity_id` and prefilled configuration. Passes 3/3 under
`--repeat-each=3` and inside the full suite (119 total). No duplication; no test weakening (awaited
navigations + a captured request, no sleeps/retries/networkidle/`.first()` shortcuts).

## Phase 6 - Production-like qualification (no external/paid calls)
| Check | Method | Result |
|---|---|---|
| No secret in client bundle | grep 55 `.next/static` JS chunks for key/secret/PEM patterns | none found |
| Env fail-fast (deploy guard) | `enforce_runtime_config()` with `API_ENV=production`, no critical env | **raises RuntimeError** (fail-closed); `development` ok |
| Prod config validation | `validate_runtime_config('production')` | `ok=False`, 4 critical (FRONTEND_ORIGINS, DATABASE_URL, ...) surfaced |
| Security headers / CORS / cookies / readiness / malware fail-safe | `eval_hosting_readiness` + `test_p8_hardening` (Phase 3) | PASS |
| Migrations clean + upgraded | Phase 3 up/down/re-up | single head `0014` |
| Account lifecycle / deletion cascade | `eval_account_deletion` (Phase 3) | PASS |

Not achievable here (require external infra / authorized deploy): live HTTPS certification, multi-replica
shared-store limits, live ClamAV - all carried as known limitations / EX-12 BLOCKED.

## Phase 8 - RC pre-qualification GO / NO-GO

**Decision: CONDITIONAL GO.**

Against the RC-P10-002 GO gate (criteria section above), the **deterministic** conditions are all
satisfied: clean scope-limited tree; single Alembic head with valid up/down/re-up; backend green
(2455/3-skip/0-fail); frontend unit+lint+typecheck+build green; full Playwright green (119/0);
28 gated evaluators green incl. the new integrated evaluator (27/27); security 22/22 with 0 false
positives; 0 unresolved P0; 0 unresolved P1; no test weakening; **0 unapproved paid/live calls**;
integrated candidate journey passes (desktop + 390px covered by the existing responsive specs and the
new opportunity→Practice spec); public/private route boundaries pass; claims/pricing/provider status
truthful; known limitations documented and every unvalidated live capability explicitly classified.

Two gate elements remain **open by policy, not by defect**, and are the reason this is CONDITIONAL:
1. **LIVE-VALIDATED (paid providers):** company official-web fetch, Adzuna market data, realtime voice,
   OCR real-scan accuracy, model-generated multilingual interview quality, Google sign-in - all remain
   deterministic-only. No paid/live call was authorized for this wave. Validation proposals belong to
   Phase 7 (STOP gate).
2. **HUMAN-VALIDATED (second moderated pilot):** requires real participants, unavailable in this
   environment. Belongs to Phase 10 (STOP gate).
3. **EX-12 hosted deploy:** BLOCKED (no authorized deployment); artifacts READY.

Per the owner's selected scope, **RC-P10-002 is deferred** (not created) and the **Pilot-2 pack is
deferred** (not built). No defect blocks release readiness; the remaining work is authorization-gated
(spend, humans, deployment), not engineering.

## Anticipated STOP gates (require your input)
- **Phase 7 (live validation):** paid/live provider calls are not authorized; several capabilities remain LIVE UNVALIDATED. I will present the validation proposals and STOP rather than spending money.
- **Phase 10 (human pilot):** a moderated pilot needs real participants, which this environment cannot provide. I will prepare the complete pilot pack and STOP, with exact instructions for you to run it and return evidence.
- Consequently, the final decision will most likely be **CONDITIONAL GO** (deterministic release readiness proven; live + human validation pending), not an unqualified GO - unless you authorize live validation and provide pilot evidence.
