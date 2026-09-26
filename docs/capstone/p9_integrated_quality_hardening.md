# P9 — Integrated Quality, UX, Recovery & Release-Candidate Hardening

_Capstone P9. Not a feature phase: test Ask4Mo as one integrated system, execute the
deterministic/local acceptance evidence, close AC-20/21 and the deterministic parts of
AC-22/23, repair integration/UX/security/recovery defects, and identify one release candidate
(**RC-P9-001**) for P10. No new capabilities; no unauthorized paid/live calls; not deployed;
not merged. Companions: [`p9_acceptance_ledger.md`](p9_acceptance_ledger.md),
[`p9_quality_register.md`](p9_quality_register.md),
[`p9_voice_measurement.md`](p9_voice_measurement.md),
[`p9_localization_completeness.md`](p9_localization_completeness.md)._

Baseline: main `eb91125` (P8 merged, PR #84); Alembic head `0011_workspaces_shares`; branch
`feature/capstone-p9-integrated-hardening`.

## Why P9
Every phase shipped with its own gate; P9 verifies the assembled product and produces one
honest, versioned acceptance ledger + a release candidate. The discipline: run the real gates
now, disposition each AC/EX truthfully, and keep live/deployment/human-review portions separate
from what deterministic local evidence can prove.

## RC methodology
1. Baseline gate (P8 merged verified). 2. Build the acceptance ledger. 3. Consolidate the
quality register with severities. 4. Execute all deterministic gates + evaluators. 5. Freeze
comparison cases + record a version identity. 6. Disposition AC-20/21/22/23. 7. Sweep security,
recovery, provider-failure, deletion, claims, UX. 8. Assign RC-P9-001 + evidence package. No
material change after freeze without a new RC id.

## Acceptance ledger
See `p9_acceptance_ledger.md`. Result: **AC** 18 PASS / 6 PARTIAL / 1 NOT RUN (AC-24→P10); **EX**
5 PASS / 10 PARTIAL / 1 BLOCKED (EX-12). No FAIL. Every non-PASS is gated on live access,
authorized deployment, human/legal review, or the P10 pilot — none on a code defect.

## Integrated journeys (J1–J11)
Representative end-to-end journeys, each backed by deterministic tests (fakes for external
providers; no paid calls):

| Journey | Result | Evidence |
|---|---|---|
| J1 New user (register→verify→prepare→practice→report→progress→resume) | PASS | `auth.spec`, `interview.spec`, `progress.spec`, backend auth/interview suites |
| J2 Returning user (sign in→Return Journey→resume→complete→history/export) | PASS | `return-response.spec`, `journey.spec`, report export tests |
| J3 Document evidence (upload→OCR fixture→review→approve→Story Bank→use→revoke) | PASS | `documents.spec`, `test_documents_*`, `documents_evidence` eval |
| J4 Multi-agent preparation (role→evidence→strategy→Mo→HITL→handoff) | PASS (deterministic) | `agent-coach.spec`, `multi_agent` eval, `test_multi_agent_specialists` |
| J5 Multilingual (locale ≠ conversation ≠ dictation; no geography change) | PASS | `i18n.spec`, `voice_experience`/`i18n_l10n` evals |
| J6 Turn-based voice (Listen→Speak→edit→Submit) | PASS | `voice.spec`, `voice_experience` eval |
| J7 Realtime fallback (connect→interrupt→commit-once→fail→turn-based) | PASS (fake) | `realtime-voice.spec`, `realtime_voice` eval |
| J8 Workspace (create→invite→accept→share→read→revoke→denied) | PASS | `workspaces.spec`, `test_sharing_p6_5`, `workspace_security` eval |
| J9 Privacy (export→delete resource→revoke→account deletion→artifacts unavailable) | PASS | `account_deletion` eval, `test_p8_hardening`, `settings-memory.spec` |
| J10 Admin (metadata view→entitlement→knowledge status→Prompt Lab→privacy queue; no candidate content) | PASS | `admin.spec`, `platform_admin`/`prompt_lab` evals |
| J11 Public product (marketing→pricing→Trust→Privacy→AI-transparency→register/sign-in) | PASS | `marketing.spec`, `route-migration.spec` |

## AC-20 restart / recovery / backup / restore / migration
`scripts/eval_restart_recovery.py` (new deterministic tooling) seeds representative owned state,
proves it survives an application **restart** (engine dispose→reopen), creates a **backup**,
**destroys** the state, **restores**, and re-verifies — all PASS on disposable SQLite. Migration
**up → downgrade(0003) → up** completes with a **single Alembic head**. The production Postgres
path is exercised by `deploy/scripts/{backup,restore,migrate}.sh` (syntax-checked) and the
hosting runbook; a real hosted restore remains EX-12 (NOT RUN).

## AC-21 required regression gate + skip audit
The release gate = backend pytest + frontend unit + Playwright + ruff + compileall + lint +
typecheck + build + OpenAPI + Alembic single-head + secret scan + all deterministic evaluators.
All green (see the final report for exact counts). **Skips (3, all justified):** live Adzuna
(needs creds), legacy Streamlit component render (needs Streamlit context), a ragas adapter case
(inverse skip). None required for release.

## AC-22 agent/retrieval evaluation
Frozen comparison cases live in versioned fixtures; a **version identity** manifest
(`artifacts/capstone/p9/RC-P9-001/manifest.json`) records SHA + eval/knowledge/policy versions so
metrics are never pooled across SHAs. Deterministic results: model-policy `policy_pass_rate 1.0`
(client cannot override; bounded fallback); routing/specialist duty tests pass. Retrieval suites
run **separately**: the historical deterministic ID baseline (**P/R ≈ 0.6757 / 0.5161**) is
preserved as *historical only*; the current Capstone extension suite (`eval_knowledge_retrieval`)
scores **pass_rate 0.9136**, **citation_completeness 1.0**, **no_fabricated_citation 1.0**,
evidence_coverage 0.8857 (7 known occupation-resolution misses, measured not hidden). A live
comparative benchmark and paid RAGAS remain **NOT RUN**.

## AC-23 voice measurement
`p9_voice_measurement.md`: EN+DE synthetic reference transcripts (5 categories each), a
word-level correction-burden metric, and deterministic UI-latency separation. Live browser STT
correction burden + provider round-trip latency are **NOT RUN** (no real engine/key) and are not
faked. Seven languages CONFIGURED, not HUMAN-VALIDATED.

## Security integration
Deterministic security evals (`security`, `workspace_security`, `identity_platform`) PASS.
Cross-boundary isolation is covered by existing suites (`test_authorization`,
`test_auth_security_matrix`, `test_sharing_p6_5`, `test_copilot_security`, `account_deletion`):
owner-scoped object access (foreign ids rejected), share revocation invalidates agent evidence
lookup, deleted-account cookies/sessions/files unavailable, admin sees metadata only, paused
provider rejected, entitlement enforced server-side, foreign checkpoint/run id denied. ~80
object-id route usages are owner/workspace/admin/public-classified. **No cross-user/authz
failure found.**

## Accessibility / browser / viewport
- **Accessibility:** skip link, focus-visible, ARIA labels + live regions, heading hierarchy,
  keyboard-operable voice/realtime controls, `<html lang>` synced; marketing mobile layout has no
  horizontal overflow (asserted in `marketing.spec`).
- **Browser matrix:** Chromium **FULLY TESTED** (Playwright); Firefox/WebKit **NOT TESTED** in
  this environment (documented); Web Speech features carry browser caveats (no parity claimed).
- **Viewport matrix:** mobile 375–390px, tablet/small-laptop 768px, desktop 1280px — critical
  screens smoke-tested via Playwright viewport emulation.

## Localization
`p9_localization_completeness.md`: candidate flows localized across 7 locales (key parity
enforced); reviewer/admin technical surfaces + source content + proper nouns are approved
English; marketing legal bodies + legacy Help bodies are documented engineering-draft debt.
Human + legal translation review are blockers for public launch, not P10.

## Defects
**P0: 0 · P1: 0 · P2: 0 · P3: 0** found in integration. The known `product-surfaces` review/rag
flake is dispositioned **ENVIRONMENT** (20/20 in isolation; 1/30 only under a stressed batch),
monitored, no sleep/retry added.

## Performance (deterministic/local)
Descriptive only (no live provider latency): evaluator runtimes are seconds (e.g. account
deletion/rate-limit/hosting-readiness < 1s each of logic; multi-agent/knowledge evals a few s);
full backend suite ~88s (2381 tests); Playwright suite ~35s (104 tests). Restart/recovery
backup ~0.36 MB representative DB. LLM/provider latency **UNVALIDATED** (no live call). No
release performance threshold is asserted where evidence is insufficient — measurements are
reported descriptively.

## Known limitations
See `p9_quality_register.md`. Headlines: EX-12 (deployment), all live-provider validations,
human/legal review, distributed rate-limit store, checkpoint residual, CSRF posture, browser
matrix, localization debt.

## Release candidate
**RC-P9-001** — assigned when all deterministic gates pass with 0 P0/P1 defects. **Code/
evaluation SHA `319759db1dd7c91ddd6ca313837326c40e05219c`** (`319759d`); versions in
`artifacts/capstone/p9/RC-P9-001/manifest.json`. A later documentation-only evidence-closure
commit corrected the AC totals and recorded this SHA — it changed no product/runtime code, no
acceptance denominator, no evaluation case, and reran no gate for a more favourable result, so
**RC-P9-001 stays valid and does NOT become RC-P9-002**. A material runtime/code change during
P10 would require a new RC. No release tag yet.

---

## Presentation evidence (§68)

```
BUILD → INTEGRATE → BREAK → REPAIR → REGRESSION TEST → FREEZE → RELEASE CANDIDATE (RC-P9-001)
```

| Gate | Evidence | Result | Limitation |
|---|---|---|---|
| Backend regression | pytest 2381/3-skip | PASS | 3 live/legacy skips |
| Frontend unit | vitest 242 | PASS | — |
| Integrated E2E | Playwright 104 (chromium) | PASS | Firefox/WebKit not tested |
| Evaluators (20) | all deterministic gates | PASS | live portions NOT RUN |
| AC-20 recovery | restart+backup+restore+migration | PASS | hosted restore = EX-12 |
| AC-22 agent/retrieval | policy 1.0; extension 0.9136; citation 1.0 | PARTIAL | live benchmark NOT RUN |
| AC-23 voice | EN/DE refs + deterministic latency | PARTIAL | live STT/latency NOT RUN |
| Security integration | isolation/authz/deletion/pause | PASS | scope = deterministic suites |
| EX-12 hosting | readiness eval + artifacts | BLOCKED | needs authorized deploy |
```
Failures/limitations shown honestly; no gate marked PASS on a stub or a live claim.
```
