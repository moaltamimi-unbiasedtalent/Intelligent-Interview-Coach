# Pilot 2 P1 remediation: integrated qualification

**Verdict: PILOT 2 P1 REMEDIATION QUALIFIED - READY FOR NEXT ARCHITECTURE WAVE.**

This is a qualification record, not a feature wave. It proves that the four P1 remediations (P2-01 to P2-04) coexist on one integrated runtime and did not regress the surrounding contracts. It does not create a release candidate, does not claim human revalidation and does not change the historical RC-P10-003 Pilot 2 verdict.

- Qualified base: `main` at `a72f91097b25b3db4007ca5c319786a2efb57ef9` (PRs #139 to #142 merged). The qualification branch adds only this document, one integrated Playwright spec and minimum current-state wording.
- Qualification date: 2026-10-12.
- Scope: P2-01, P2-02, P2-03, P2-04. P2-05 to P2-09 are not started.

## 1. Individual remediation states (unchanged)
| Item | State |
|---|---|
| P2-01 sharing and revocation discoverability | REMEDIATED - PENDING HUMAN REVALIDATION |
| P2-02 isolated representative knowledge environment | REMEDIATED - ENVIRONMENT READY, PENDING HUMAN REVALIDATION |
| P2-03 answer-score interpretation | REMEDIATED - PENDING HUMAN REVALIDATION |
| P2-04 provenance clarity | REMEDIATED - PENDING HUMAN REVALIDATION |

No state moved to validated: no participant has seen the remediated runtime.

## 2. Results
| Gate | Result |
|---|---|
| Vitest | 831 passed (93 files) |
| Typecheck, lint, production build | clean |
| Playwright (full, `E2E_PORT=3017`) | 271 passed (270 existing + 1 new integrated spec) |
| Backend `pytest` (full, isolated) | 3,170 passed, 4 skipped, 0 failed (skips are the existing conditional skips; no live or paid call) |
| CI-safe evaluators (all       43 listed in `.github/workflows/ci.yml`, including `eval_release_matrix`, `eval_doc_consistency`, `eval_w11_integrated`, `eval_rc_p10_003`, `eval_documents_evidence`, `eval_i18n_l10n`, the Admin set, privacy, voice, agent, multi-agent) | all PASS |
| Migrations (temporary SQLite only) | single head `0025_security_audit_incidents`; base to head, head to previous (`0024_reporting_analytics`), previous to head, head to base to head all succeeded |
| Isolated knowledge fixture | built in a new throwaway directory (`local-hash-v1`, `career_knowledge_base`, 4 sources, 10 chunks); 17 of 17 validation checks PASS; the directory was then removed |

Non-isolated or manual evaluators were not run, in particular `scripts/eval_retrieval.py`. Paid or live calls: **0**.

## 3. Integrated gates
- **P2-01.** Data & Privacy shows "Manage sharing & access", the overview links to `#sharing`, the landmark resolves, the share names workspace and resource, revoke is explicit with a truthful confirmation, exactly one revoke request is sent (no retry), the empty state says private-by-default, and Workspaces links to `/account/data#sharing`. Backend owner-only revoke, foreign-user refusal, revocation cutting access and membership-alone exposing nothing remain covered by the existing sharing tests and `eval_workspace_security`, which pass.
- **P2-02.** The fixture drives the real Chroma, local-hash, hybrid retrieval path: a known STAR query returns evidence, every citation maps to a fixture chunk, no external URL is invented, an unrelated query returns no fixture evidence, an injection query is blocked, no synthesis model is called and no network call is made. The builder still refuses `data/chroma` and any path inside the repository.
- **P2-03.** Practice shows "Interview Answer Score" with `x / 100`, the this-answer-only and separate Practice Readiness statements and "Practice feedback only, not a hiring decision." All seven dimensions render as `x / 10`; there is no formula, average, weighting, band or hiring probability; Credibility states it is not a check of whether the candidate is telling the truth; Deep Dive uses the same presentation; the final Practice Readiness stays session-level. The backend is unchanged (LLM-backed, schema validated, no deterministic formula, no Evaluation Specialist).
- **P2-04.** No sources shows AI-generated only. External retrieval shows AI-generated plus External sources used with the real title and no whole-answer claim. "Your evidence considered" appears only from a successful `FindCandidateEvidence` `tool_completed` event with `status = ok` and `source_count > 0`, and not from `retrieval_used`, `journey.understand.evidence_used`, CV presence, `candidate_background` or configuration. Document states read Not reviewed yet, Reviewed by you, Corrected by you, Rejected by you; Story Bank states read Built from your evidence, Written by you, Edited by you, AI suggested, Supporting evidence available, Supporting source removed, No supporting source. "Evidence verified" is absent from candidate-facing copy.

## 4. Cross-P2 scenario
`frontend/e2e/pilot2-p1-integrated.spec.ts` is the smallest deterministic flow showing the surfaces do not contradict each other (network mocks, no provider): a Prepare answer with an external source and no candidate-evidence event shows AI-generated and External sources used but not Your evidence considered; the same surface with a successful `FindCandidateEvidence` event adds Your evidence considered; Practice shows the labelled score and seven dimensions with no Prepare provenance chrome; Data & Privacy reaches sharing from the quick action and revokes once. Exactly one DELETE (`/shares/40`) is sent, no account-deletion or admin call is made and nothing else is removed.

## 5. Language, voice, Admin and privacy contracts
- Eight interface locales and eight Mo conversation languages; seven dictation, TTS, realtime, document and KB languages. Russian: interface yes, Mo conversation yes, dictation, TTS, realtime, documents, KB, official ESCO and automatic geography no. The slogan "Ask More. Be More." is unchanged. `eval_i18n_l10n` and the scanner report 0 unexplained literals.
- No Admin candidate-private-content browser, impersonation, break-glass or new candidate-content permission was added; `eval_admin_qualification` and `eval_platform_admin` pass. `platform_admin` remains 28 of 43 for now (the 43 of 43 change, AD-W12-01, is approved and not implemented here).

## 6. Responsive and visual QA
`/prepare`, `/practice` (after an answer), `/account/data#sharing`, `/workspaces`, `/documents` and `/sources` were captured at 1280 px and 390 px in light and dark: horizontal overflow 0 on all 24 captures, and the score, provenance badges and sharing controls were readable with acceptable contrast. This is an automated capture plus visual inspection of sampled frames, not human testing. The existing unrelated 390 px header logo and "More" overlap is still present and is recorded, not fixed.

## 7. Protected stores
Before and after the full qualification all six fingerprints are identical to the accepted baseline: developer DB `81eef3479704ed91e58abb876926f98108968842` (224 schema objects), checkpoint `b56d0c39fbba64786495ebb5db59eedecfae5c71`, Chroma `6357c057606273f313b408cc7f144390453a0832`, research cache `25264b17b36f7a365ff8dfaca9eec97e997ee710`, `evaluations/` `67259aba185daa495f8bf8958e1c905fd086b2be`.

## 8. What this does not claim
- No human revalidation of P2-01 to P2-04.
- AC-24 stays **PARTIAL**: the four fixes are regression-tested, but the changed runtime has not yet been recorded under a successor RC and release gate (RC-P10-004 does not exist).
- RC-P10-003 remains immutable and its historical verdict (CONDITIONAL GO - TARGETED REMEDIATION REQUIRED) is unchanged.
- No RC, tag or manifest was created. P10C is not started.

## 9. Out-of-scope findings (preserved, not fixed)
Workspaces inline one-click revoke with raw resource labels; the 390 px header logo and "More" overlap; the production RAG relevance cutoff for unfiltered queries; P2-05 onboarding communication, P2-06 pricing and positioning, P2-07 Progress intelligence, P2-08 Mo naturalness, P2-09 Opera voice reproduction.

## 10. Next
The next architecture wave is the Platform Admin 43 of 43 change (AD-W12-01); the Admin Owner Walkthrough follows it.
