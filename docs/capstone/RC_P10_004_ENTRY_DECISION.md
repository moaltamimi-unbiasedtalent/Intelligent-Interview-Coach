# RC-P10-004 Entry Decision (PROPOSAL)

**Status:** PROPOSAL, prepared 2026-10-19 against `main` `4043429`. **RC-P10-004 is NOT created, the directory `artifacts/capstone/p10/RC-P10-004/` does not exist, and nothing here creates it.** Creation needs a separate Product Owner approval. This document reconstructs the entry criteria from the existing release-candidate convention; it does not redefine RC qualification. Related: [`CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md`](CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md), [`ACADEMIC_SUBMISSION_SCOPE_DECISION.md`](ACADEMIC_SUBMISSION_SCOPE_DECISION.md), [`PRE_SUBMISSION_ACCEPTANCE_GATES.md`](PRE_SUBMISSION_ACCEPTANCE_GATES.md) (section 3), the [register](POST_SUBMISSION_DEFERRED_ISSUES_REGISTER.md) (`DI-N IR-RC004-SPEC`).

## 1. The existing convention (read from RC-P10-003 and RC-P10-002)

Sources: `docs/capstone/p10/RC_P10_003_RELEASE_CANDIDATE.md`, `artifacts/capstone/p10/RC-P10-003/manifest.json` and `gate_results.md`, `p10/w9/P10B_W9_ACCEPTANCE_GATES.md` (G1).

1. An RC is an **evidence artifact pinned to ONE merged-`main` SHA**: a directory `artifacts/capstone/p10/RC-P10-00N/` with `manifest.json` and `gate_results.md`, plus a descriptive document. It is **not** a git tag, a version bump, a deployment or a production release.
2. It is **current only while its directory is present on `main`**; on a pull-request branch it is PREPARED.
3. The artifact's own merge commit is evidence packaging; the candidate identity is the earlier pinned SHA.
4. It is created by a **separate, owner-approved action**, never as a side effect of a qualification wave (the W11 qualification explicitly did not create RC-P10-003).
5. It is **immutable once created**; earlier RCs stay untouched; evidence is never mixed across RCs; a documentation-only correction does not change the identity.
6. **Any material runtime, backend, frontend, schema, permission, entitlement, billing, security or privacy change after an RC requires a NEW candidate.**
7. The manifest records version identity (Alembic head, permission count, locales, release matrix result), gate results (backend, vitest, Playwright, typecheck, lint, build, i18n, Ruff, compileall, evaluators, Alembic, fresh-checkout run, GitHub CI, sentinels, paid or live calls), accepted limitations, and the live-provider and production-readiness boundaries.

**Not documented anywhere:** that the 95% product-coverage gate is an RC entry criterion (it is absent from the definition of done, the W9 gate set, the RC-P10-003 documents and the release matrix); how an RC records a failed internal gate; whether live or human items are mandatory for an RC. The backlog states only that the gate must be satisfied "before any release that requires it".

## 2. What changed since RC-P10-003 (why a NEW candidate would be required)

RC-P10-003 pinned candidate `54aad500` at Alembic head `0025_security_audit_incidents` with 43 Admin permissions. Since then: permissions 44, migrations `0026` to `0039`, the encrypted secret store, email and identity hardening, the billing foundations (all disabled), governed speech (disabled), Admin configuration completeness and UX corrections, the P10C engines and P10D requalification, the P10E live harness, the routing fix, and the three grounding policies. RC-P10-003 therefore does not describe the current system; AC-24's "new RC if runtime changed" criterion points at exactly this gap.

## 3. Proposed entry criteria for RC-P10-004

Status key for "state now": MET, NOT MET, PARTIAL, UNDEFINED (needs an owner decision).

| # | Entry criterion | Source | State now |
|---|---|---|---|
| E1 | One immutable candidate SHA that is a merged `main` commit; evidence packaged separately | convention 1 and 3 | MET possible: `main` `4043429` is merged; the SHA would be chosen at creation |
| E2 | Required CI green on the candidate's pull request and on a fresh checkout | convention 7 | PARTIAL: 11 of 11 checks passed on PR #204's head; a fresh-checkout run on the candidate is not yet done |
| E3 | Integrated Candidate/Admin/Operations requalification complete | roadmap | MET (PR #204: executed, no new BLOCKER or HIGH defect) |
| E4 | Regression gate (tests, build, contracts, security) passes on the candidate | AC-21 | PARTIAL: passes on this tree; must be rerun on the candidate SHA |
| E5 | Security and privacy qualification | W9 gates | MET offline; production hardening items are listed in the register and are not RC criteria |
| E6 | Candidate, Admin and Operations evidence (real, offline, mocked, live and not-tested classes stated) | requalification report | MET (documented) |
| E7 | Grounding-policy qualification (contextual citations, factual retrieval with clarification, no unsourced compensation estimates) | owner direction 2026-10-19 | PARTIAL: deterministic evidence complete; the live sample predates the final corrections (`DI-D D-NOT-LIVE`) |
| E8 | Explicit limitation disclosure | convention 7 | MET possible: accepted-limitation list = the register plus the acceptance ledger |
| E9 | All 12 rollout and billing gates disabled; Compensation V2, Premium, Stripe and speech activation disabled | owner rule | MET |
| E10 | Original product-coverage gate **reported with its actual FAILED status**, never relabelled | owner direction 2026-10-19 | MET as a reporting rule; the gate itself is **NOT MET** (386/412 and 258/412 against 392) |
| E11 | Human-validation status reported honestly | owner direction | MET as a reporting rule: P10F deferred, AC-24 PARTIAL, human-qualified coverage 0 of 412 |
| E12 | Single reconciled acceptance ledger agreed by the owner | `DI-N IR-AC-LEDGER` | PARTIAL: proposed ledger written, owner approval outstanding |
| E13 | Owner decision on how an RC records a failed internal gate | not documented | UNDEFINED |
| E14 | Owner decision on whether live or human items are mandatory for an RC | not documented | UNDEFINED |
| E15 | Separate Product Owner approval to create the RC | convention 4 | NOT MET (not requested until now) |
| E16 | No historical evidence rewritten; earlier RC artifacts untouched | convention 5 | MET (no RC artifact was modified) |

## 4. Four different outcomes (they are not equivalent)

| Outcome | What it means | State |
|---|---|---|
| **Engineering candidate readiness** | The tree builds, tests pass, security and isolation hold, gates are disabled, limitations are disclosed | **MET at `4043429`** (deterministic and local evidence) |
| **Limited-scope academic demonstration** | The system can be demonstrated and submitted under a disclosed scope | **CONDITIONAL**: needs the owner's coverage-gate handling, the course rules (deadline, rubric, deployment) and P11; see the scope decision |
| **Full release acceptance** | Every acceptance criterion and internal gate is met | **NOT MET**: 8 criteria PARTIAL, the 95% gate FAILS, AC-24 PARTIAL |
| **Production readiness** | Safe to release to real users | **NOT MET**: 161 register items block production; hosted operation, human qualification, legal review and live provider validation are all open |

## 5. Implications of creating an RC artifact while the coverage gate fails

- **Not forbidden by a written criterion.** No existing document makes the 95% gate an RC entry criterion, and an RC is an evidence artifact, not a release. Creating one that **records the gate as FAIL** is therefore not a contradiction of a written rule.
- **But the word "candidate" carries an implied meaning.** RC-P10-003 was created only after its release matrix showed 0 blockers and its gates passed, and it reads as "CREATED / CURRENT" qualification. An RC-P10-004 that contains a failed internal gate would be the first of its kind and would silently set the precedent that an RC may carry a failed gate. That is a redefinition of RC qualification, which this wave must not do (criteria E13 and E14).
- **It would be meaningful in one narrow sense:** as an immutable snapshot of what is submitted, and as the successor candidate AC-24 and AC-21 point to. It would not change any acceptance disposition: AC-24 would still be PARTIAL without human revalidation, and the coverage gate would still FAIL.
- **Risk if mislabelled:** a reader could take "RC-P10-004 created" as "gates passed". The manifest would have to state, in its first lines, the failed gate, the PARTIAL criteria and the absence of human qualification.
- **Alternative for the owner to weigh:** a course-facing submission can cite `main` at a specific merged SHA and the evidence documents without creating an RC. Nothing in the repository or the available course material makes an RC a submission requirement (the course brief is not available), so this is a question for the owner.

## 6. Recommendation

**RC-P10-004: NO-GO now.** Reasons: criteria E13 and E14 are undefined, so creating the RC would silently redefine what an RC is; the coverage gate fails; the owner has not approved creation (E15); and the course questions that decide whether an RC adds anything (deadline, deployment, rubric) are unanswered. If the planning deadline of 2026-10-20 is real, an RC and P11 cannot both be completed after these decisions, which is a further reason to decide first what the submission needs.

**It flips to CONDITIONAL GO when the owner has decided, in writing:** (1) how an RC records a failed internal gate (for example a manifest section `gate_status` that lists the coverage gate as FAIL with no exception), (2) whether live or human items are mandatory for this RC, (3) the course questions (deadline, deployment, rubric) or an explicit instruction to proceed without them, and (4) approval of `CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md`. Then a separate wave would, from the then-current merged `main`: run the full regression and a fresh-checkout run on the candidate SHA, optionally spend part of the remaining 15 live calls on the policy re-sample (needs the owner's choice), write `manifest.json` and `gate_results.md` with the failed gate and the PARTIAL criteria stated first, and add `RC_P10_004_RELEASE_CANDIDATE.md`. None of that is started here.

## 7. Proposed manifest content (for the future wave, not created)

`release_candidate_sha` (merged `main`), version identity (Alembic head `0039_speech_governance`, 44 permissions, 8 interface locales, 7 Knowledge Base languages, models), test results, `gate_status` with `product_coverage: FAIL (386/412 developer-local, 258/412 clean checkout, human-qualified 0/412)`, the acceptance ledger link, the deferred register link, the 12 gate states, the live-provider boundary (15 calls remaining, nothing reset), the production-readiness caveats, and the freeze semantics of section 1.
