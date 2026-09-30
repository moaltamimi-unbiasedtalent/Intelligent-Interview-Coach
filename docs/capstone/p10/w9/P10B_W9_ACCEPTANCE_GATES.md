# P10B-W9 — Acceptance Gates for the Replacement RC

Audit phase. These are the **non-negotiable gates** the replacement release candidate (expected
RC-P10-003, subject to §Naming) must satisfy. The RC is created **only after every gate passes** — not
in the audit task, and only on explicit approval.

Each gate names how it is verified (deterministic test / evaluator / E2E / code review). "0 paid/live
provider calls" applies to all verification unless explicitly authorised.

---

## A. Resilience & truthful errors
- **A1** A backend outage/500 never tells the user their internet is the problem. *Verify:* backend test
  (allowed-origin 500 carries `Access-Control-Allow-Origin` + `X-Request-Id`); frontend taxonomy unit
  test; E2E kill-API shows "reaching Ask4Mo", not "check your connection". (PF-01/PF-02)
- **A2** Progress and History recover after a backend restart **without full reload or re-login**.
  *Verify:* restart-recovery E2E + `eval_restart_recovery`. (PF-05)
- **A3** No duplicate catastrophic error messaging on any page (one page-level banner). *Verify:* unit
  test on Progress. (PF-03)
- **A4** A server 500 cannot masquerade as an unexplained CORS/network failure where avoidable; a
  reference id is shown on server faults. *Verify:* header test + `ErrorState` reference rendering.
  (PF-01/PF-06)
- **A5** Distinct, honest messages for offline vs unreachable vs 401/403/404/409/422/429/500/502/503;
  bounded retry only on idempotent/keyed requests, never on 4xx. *Verify:* taxonomy + retry unit tests.
  (PF-07/PF-08)
- **A6** Every `ErrorState` offers in-place Retry. *Verify:* unit sweep. (PF-04)

## B. Discoverability & onboarding
- **B1** Opportunity is discoverable without moderator instruction (CTA on `/app`, return card link,
  salient nav). *Verify:* discoverability E2E. (PF-10)
- **B2** Onboarding has a clear intentional handoff (completion/welcome screen → first Opportunity).
  *Verify:* onboarding E2E. (PF-11)
- **B3** The tutorial contains an Opportunity step; no step highlights a missing DOM target; tour state
  is account-scoped. *Verify:* tutorial E2E + unit. (PF-12)

## C. Localization
- **C1** All Ask4Mo-owned candidate-facing UI is localized across supported languages (no hardcoded
  English on core authenticated pages). *Verify:* `no-literal-string` guard + key-parity test +
  locale-switch E2E. (PF-13)
- **C2** A machine-checkable guard fails CI on new hardcoded candidate-facing English. *Verify:* the
  guard itself + a seeded regression. (PF-13)
- **C3** Russian is included when W9.7 completes (8-locale allowlists consistent; catalogue key-parity).
  *Verify:* 8-locale evals + `ru.ts` parity. (PF-14)
- **C4** Interface language remains independent of Mo conversation language, dictation language, and
  labour-market geography. *Verify:* `eval_i18n_l10n` (geography = f(query)) + separation tests.
- **C5** No scoring/rubric/evidence/grounding change is caused by localization (directives are
  prose-only). *Verify:* language-directive tests; interview scoring unchanged across languages.

## D. Security & authorization
- **D1** The pilot security concern is either fixed or conclusively classified. *Status:* classified as
  route-visibility/info-disclosure (SECURITY_AUDIT); W9.3 additionally fixes it. (PF-09)
- **D2** No unauthorized menu/API access: no privileged nav item renders for a BASIC user; `/review`
  diagnostics require role/capability; admin/reviewer routes stay `require_platform_admin`; owner-scoped
  routes 404-on-foreign; production fail-closed 401. *Verify:* `eval_platform_admin`,
  `eval_workspace_security`, `eval_multi_agent`, new `/review` authz tests + E2E.
- **D3** The dev-only `X-User-Subject` header cannot override a valid session and is rejected in
  production. *Verify:* existing identity/security tests.

## E. Data integrity & correctness
- **E1** Zero invented salary/career data (abstention preserved). *Verify:* `eval_knowledge_governance`,
  `eval_knowledge_retrieval`, RAG evals.
- **E2** No authority-level semantic inconsistency: canonical order is 1=official … 3=industry; the
  API comment matches; a contract test pins `SourceOut.authority_level` ↔
  `KnowledgeEvidence.authority_level`. *Verify:* new contract test + `career.py:37` comment. (PF-21)
- **E3** No regression to ownership/privacy/HITL/provenance. *Verify:* `eval_multi_agent`,
  `eval_documents_evidence`, `eval_account_deletion`, HITL tests.
- **E4** Career Chat returns 200 with grounded evidence (PR #100 closed and its class closed by A1).
  *Verify:* `tests/test_career_chat_schema.py` + a route round-trip test + live-free repro. (PF-20)

## F. Suite health
- **F1** Existing deterministic backend suite is **0 failed** — including intrinsic isolation of the
  `.env` `OPENROUTER_MODEL_*` artifact (no test weakened). *Verify:* full `pytest` from project cwd = 0
  failed; the 5 model-registry files pass with and without the override. (CURRENT_STATE §4)
- **F2** `ruff` clean; frontend lint/typecheck/vitest/build clean.
- **F3** `npm run e2e` (Playwright) green, including the **new** resilience, localization, and security
  specs. *(Not run in the audit; required at requalification.)*
- **F4** All deterministic evaluators PASS (`eval_release_candidate` + the domain evals), 0 paid/live.
- **F5** No unresolved **P0/P1** defects (PF-01, PF-02, PF-10, PF-11, PF-13 closed).

## G. Process
- **G1** RC-P10-002 unchanged/immutable; the replacement RC is a NEW artifact
  (`artifacts/capstone/p10/RC-P10-003/{manifest.json,gate_results.md}`) pinned to a single merged SHA;
  Pilot 2 never runs across two SHAs.
- **G2** Pilot 2 evidence is not modified; the RC is created only after **all** gates above pass and only
  on explicit approval.
- **G3** 0 paid/live provider calls in qualification unless explicitly authorised; the OpenRouter key is
  never printed/logged/committed.

---

## Naming reconciliation

Repository RC convention is `artifacts/capstone/p10/RC-P10-00N/` (RC-P9-001, RC-P10-002 exist). The next
sequential id is **RC-P10-003**, which matches the prompt's expectation. Adopt `RC-P10-003` unless a
later repository decision changes the scheme. It is a doc/eval artifact pinned to a merged SHA, **not** a
git tag (existing tags are sprint-level only).

## Gate → wave traceability
A: W9.1/W9.2 · B: W9.4/W9.5 · C: W9.6/W9.7 · D: W9.3 · E: W9.11 (+E1/E3 standing) · F: W9.12 · G: post-W9.12.
