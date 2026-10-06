# RC-P10-003 — Release Candidate

## 1. Status / activation rule
**RC-P10-003 is the current candidate only when the directory `artifacts/capstone/p10/RC-P10-003/` is present on main.** On the pull-request branch it is PREPARED; once merged to main it is CREATED / CURRENT. **W11 did NOT create RC-P10-003** (the W11 document is unchanged and still says so). This separate, owner-approved post-W11 action does. The RC follows the existing repository convention: it is an evidence ARTIFACT pinned to one merged-main SHA. It is not a Git tag, a version bump, a deployment, a production release, permission to resume Pilot 2 or permission to start P10C.

## 2. Candidate identity
- `release_candidate_sha`: `54aad500ec937b4828984c32c64b77746534633d` (main after W11 feature + completion docs)
- `qualified_runtime_merge_sha`: `d27993d7f2757cf7605355e3f76c71dac6f85c10`
- W11 feature head: `654ca47ab603fe96d093e10faaa778f5f5ab2e33`
The candidate is not pinned to this artifact's own commit: the artifact is evidence ABOUT the candidate, not the candidate.

## 3. W11 qualification basis
[P10B_W11_INTEGRATED_REQUALIFICATION.md](P10B_W11_INTEGRATED_REQUALIFICATION.md): W11 COMPLETE AND INTEGRATED; P10B INTEGRATED QUALIFIED. Historical bases: [W9.13](w9/P10B_W9_13_FULL_REQUALIFICATION.md) and [W10.14](../admin/W10_14_FULL_ADMIN_QUALIFICATION.md). The gate G1 in [P10B_W9_ACCEPTANCE_GATES.md](w9/P10B_W9_ACCEPTANCE_GATES.md) names the replacement RC artifact path used here.

## 4. Provenance
Feature PR #132 (head `654ca47`, merge `d27993d`); docs PR #133 (head `98c79c8`, merge `54aad50`). PR #133 is documentation-only, so the runtime at the candidate SHA equals the W11 feature merge.

## 5. Integrated matrix
[P10B_RELEASE_ACCEPTANCE_MATRIX.md](P10B_RELEASE_ACCEPTANCE_MATRIX.md): **99 requirements, 88 PASS, 11 ACCEPTED, 0 BLOCKER.** No R-100 was added for the RC: RC creation is evidence packaging, not a product requirement.

## 6. Qualification results
Backend 3145 passed / 4 skipped / 0 failed / 0 errors; Vitest 768 (89 files); Playwright 239; CI evaluators 42/42 at W11 close; W11 evaluator 27 checks; typecheck, lint, build, Ruff, compileall clean; i18n 0 offenders. Details in `gate_results.md`.

## 7. Accepted limitations (11)
- **R-33** — Email verification is not required to sign in.
- **R-38** — Legacy Streamlit is retained.
- **R-46** — Distributed Redis rate limiting exists as an adapter but is not live validated.
- **R-49** — Native/legal language review is pending.
- **R-50** — Live generated-language validation requires a separately authorised live run.
- **R-51** — Metadata localization / bundle optimization remains post-P10B optimization work.
- **R-93** — Support attachments are not implemented.
- **R-94** — Admin workspace deactivation and universal operator search are not built.
- **R-95** — Live billing, production secret vault and external paging are absent.
- **R-96** — PostgreSQL-only paths have not been exercised against a disposable/live PostgreSQL qualification environment.
- **R-97** — Google OIDC live behaviour is not validated.

These are ACCEPTED, not blockers, and not completed. The product is not described as fully production-ready.

## 8. R-52 / R-98 / R-99
R-52 (A11Y-W9-13-01) PASS; R-98 (LAYOUT-W11-01) PASS after an owner-approved bounded fix (navigation handoff `md`→`lg`, no threshold relaxation); R-99 (CI-W11-01) PASS after the workflow YAML was repaired. History is preserved in the W11 document.

## 9. Candidate / Admin separation
Cross-plane seam tests are green: Admin never sees private candidate content (sentinels) or secrets; candidate behaviour is unaffected by Admin billing/plan operations; Admin and candidate authorization are separate.

## 10. Privacy / security boundary
43 canonical Admin permissions, six least-privilege role presets (platform_admin 28/43), two-person role changes with password step-up (not MFA), append-only audit via database triggers, in-app alerts only, no break-glass or impersonation.

## 11. Entitlement / billing truth
Billing is MOCK. Billing events never touch subscriptions or candidate entitlements; nothing is sold (R-95).

## 12. Language architecture
8 interface locales, 8 Mo conversation languages, 7 speech/document/KB languages. Russian: interface and Mo conversation supported; speech, KB and official ESCO not. Interface language owns UI chrome; Mo conversation language owns Mo-voiced text. "Ask More. Be More." is never translated. Native/legal review is pending (R-49) and live generated-language validation was not run (R-50).

## 13. Model / evaluation architecture
11 tools (6 Career, 3 specialists, 2 human-action). Specialists: `role_opportunity`, `candidate_evidence`, `interview_strategy`; there is no Evaluation Specialist. Evaluation is an LLM-backed service with schema-validated, model-produced scores and no deterministic scoring formula.

## 14. Admin status
ADMIN PLATFORM QUALIFIED (W10.14). Not built: workspace deactivation by Admin and universal operator search (R-94); support attachments (R-93).

## 15. Migration identity
Single Alembic head `0025_security_audit_incidents`; base→0025, downgrade to 0024 and re-upgrade PASS.

## 16. GitHub CI evidence
PR #132 final head: CI and Browser E2E PASS. PR #133 final head: CI PASS; Browser E2E PASS after a same-commit rerun of an external `packages.microsoft.com` HTTP 403 during Playwright browser installation (before any test; no source change; external infrastructure). CI-W11-01: the main CI workflow had not parsed on GitHub for W10.11–W10.14 and early W11 (earlier wording implying all GitHub CI jobs ran was inaccurate); fixed in W11.

## 17. Fresh-checkout evidence
Backend 3138 passed / 11 skipped / 0 failed; Vitest 768; Playwright 239; evaluators 42/42; Ruff, compileall, typecheck, lint, build, i18n clean; no developer stores created. The 11 skips are listed in `gate_results.md`; 0 blockers.

## 18. Protected-store qualification history
W10.13: "disclosed contamination with stable post-incident qualification baseline" (permanent). W11 qualification: all six stores unchanged against the W11-start baseline. After qualification the developer used the app interactively (including a company-research request) and the dev DB and research cache changed; this is post-qualification developer activity, does not invalidate W11 qualification, and no restore was performed.

## 19. Pre-RC developer baseline (environmental only)
Captured after the app servers were stopped; not part of the RC code identity and not the W11 baseline: dev DB `81eef3479704ed91e58abb876926f98108968842`; schema 224 sqlite_master objects; checkpoint `b56d0c39fbba64786495ebb5db59eedecfae5c71`; Chroma `6357c057606273f313b408cc7f144390453a0832`; research cache `25264b17b36f7a365ff8dfaca9eec97e997ee710` (accepted post-incident value; previously `a3ad0eea…`, see section 19A); evaluations `67259aba185daa495f8bf8958e1c905fd086b2be`.

## 19A. Qualification-environment incident (RC-QUAL-ENV-01)
During the targeted RC-P10-003 evaluator run, the legacy `scripts/eval_release_candidate.py` executed company research for the deterministic fixture company `Acme` without first loading the test-isolation bootstrap. It wrote one cache entry: `data/cache/external/be293349a0419d930134b8c6.json`. The research-cache fingerprint changed `a3ad0eea16f2fadd337bba0ce2fd5ea6a88b1dc8` -> `25264b17b36f7a365ff8dfaca9eec97e997ee710`. No other protected store changed. The evaluator was corrected to bootstrap test isolation before application imports (and 19 further evaluators lacking the same import received it; `eval_rc_p10_003.py` now enforces the rule for every `scripts/eval_*.py`). No cache entry was deleted and no cache state was restored; the file is environment state, not RC evidence, and is not committed. The post-incident fingerprint is the accepted pre-RC baseline. Classification: RC qualification contamination caused by an unisolated legacy evaluator; corrected before RC creation. This is separate from the permanent W10.13 dev-DB disclosure and from the post-W11 interactive app-use drift. The pre/post store comparison of the first targeted run is therefore NOT clean; stability is proven against the new baseline from the corrected run onward. Scope note: the rule covers every CI evaluator (43). Seventeen manual/non-CI evaluators (eval_agent_judge, eval_agent_live, eval_company_intelligence, eval_expanded, eval_external_research, eval_faithfulness_v2, eval_feedback_intelligence, eval_knowledge_retrieval, eval_onboarding_personalisation, eval_opportunity_journey, eval_prepare_practice_integration, eval_quality_v2, eval_rag, eval_ragas, eval_retrieval, eval_retrieval_quality_v2, eval_security) do not bootstrap isolation; they are not run by CI, some are live/opt-in by design, and they are listed as a known follow-up rather than changed here.

## 20. Freeze semantics
RC-P10-003 is immutable once created. The candidate SHA is `54aad500…`; artifact/evidence commits on top do not alter its identity. RC-P10-002 stays immutable. Pilot 2 must run against ONE candidate SHA. Any material runtime/backend/frontend/schema/permission/entitlement/billing/security/privacy change after RC-P10-003 requires a NEW candidate (expected RC-P10-004). A documentation-only evidence correction does not change the candidate SHA, and no favourable-result gate rerun changes the identity. No production deployment is implied.

## 21. Pilot 2
PAUSED. It resumes only on separate owner authorization, against this one candidate SHA.

## 22. P10C boundary
NOT STARTED.

## 23. Live-provider boundary
0 paid/live calls. Live provider validation was NOT RUN (R-46, R-50, R-96, R-97).

## 24. Production-readiness caveats
Not production-ready in full: mock billing, no production secret vault or external paging (R-95), distributed rate limiting and PostgreSQL-only paths not live validated (R-46, R-96), Google OIDC not live validated (R-97), native/legal review pending (R-49). Public launch is NOT AUTHORIZED.

## 25. Next owner decision
Review and merge this artifact PR, then separately decide whether and when to resume Pilot 2 against this candidate and what follows. Neither is started here.
