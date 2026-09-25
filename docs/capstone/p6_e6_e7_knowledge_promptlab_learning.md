# P6 + E6 + E7 — Knowledge Governance, Prompt Lab & Feedback Learning

_Capstone P6 (knowledge governance + K1–K4), E6 (Prompt Lab), E7 (feedback learning +
retention). Builds on the merged P5/E4 baseline. No production prompt/code/model/routing is
auto-modified; no paid/live calls. Alembic head unchanged (`0010_candidate_documents`; no
migration added). Backend suite: 2334 passed, 3 skipped._

## 1. Knowledge architecture (recap) & governance additions

The governed Career-Intelligence KB (structured SQLite stores + Chroma vector index, a
deterministic router, hybrid vector+BM25 retrieval, geography precedence, citations) is
**unchanged**. P6 adds a governance layer ON TOP:
- `src/copilot/knowledge/governance.py` — a first-class **Knowledge Manifest**,
  **deterministic readiness** state machine, **source health**, **coverage matrix** and the
  **7-language boundary**.
- `src/copilot/knowledge/governed_datasets.py` + `data/knowledge/governed/*.json` — the
  K1–K4 curated, committed, reviewed datasets with abstention-first access.

## 2. K1–K4 closure

| Req | Acceptance (EX) | Implementation | Abstention / safety | Evidence |
|---|---|---|---|---|
| **K1** German occupation compensation | EX-13 | `k1_de_compensation.json` (declared occupation set: currency EUR, pay unit gross_annual, reference year, source authority) + `lookup_compensation` | Abstains outside the set/jurisdiction; **never invents a salary** | `test_knowledge_governance_p6.py`, `eval_knowledge_governance.py` |
| **K2** Credentials / regulated professions | EX-14 | `k2_credentials.json` (declared profession/jurisdiction matrix; REQUIRED vs PREFERRED; authority lineage + dates) + `lookup_credentials` | Abstains outside the matrix | same |
| **K3** Emerging roles / aliases | EX-15 | `k3_role_aliases.json` (versioned aliases + confidence) + `resolve_alias` | Confident exact match only; never overrides existing resolution; unknown/ambiguous stay unresolved | same |
| **K4** Additional Adzuna capabilities | EX-16 | `k4_adzuna_capabilities.json` (allow-listed ops, param bounds, entitlement, safe-output) + `validate_adzuna_operation` | Bounds/entitlement/allow-list enforced; **no live call — UNVALIDATED, cost-gated**; self-reported labelling | same |

All figures are **engineering-draft** pending human data review; the delivered capability is
the governance *mechanism* (provenance, pay units, abstention, no-invention, bounds), not a
claim that numbers are authority-verified.

## 3. Knowledge manifest, readiness, source health, coverage

- **Readiness** (`ReadinessState`: NOT_CONFIGURED / SOURCE_MISSING / INDEX_MISSING / STALE /
  PARTIAL / READY / ERROR) is computed from **deterministic checks**: source manifest
  integrity (loads + unique ids), governed-dataset presence, structured-store files +
  build counts, vector-index presence, build-metadata provenance. READY never means "folder
  exists": on a fresh clone the generated stores correctly report SOURCE_MISSING /
  INDEX_MISSING while committed governed datasets report READY.
- **Manifest** unifies governed datasets + a safe projection of the curated source register +
  build provenance — auditable without opening embeddings.
- **Source health** per store: configured/present/size/record-count/last-build/warnings.
- **Coverage matrix** states, per domain, jurisdiction/language/authority/readiness and a
  known limitation, with an explicit disclaimer: **no universal-coverage claim**; the known
  German-compensation-depth gap is surfaced.

## 4. Governed vs current-market vs private vs model (evidence boundary preserved)

The four provenance types stay distinct: **governed KB** (curated, official authority) ·
**current market** (Adzuna, advertised & self-reported — K4) · **private candidate
evidence** (owner-scoped, P4/P5) · **model inference**. The coverage matrix and K4 labelling
keep governed compensation (official) separate from advertised market data.

## 5. Retrieval evaluation, RAGAS, multilingual

- Existing deterministic suites are preserved (11R / 11R-A / KB-2 / product coverage /
  quality_v2 / faithfulness_v2); citations, geography, unknown-role/unsupported-geography
  safety are covered there and by `knowledge_service` diagnostics.
- **RAGAS**: the committed **deterministic** baseline (ID context precision **0.6757**,
  recall **0.5161**, `evaluations/ragas/deterministic_baseline.json`) is **preserved,
  untouched**. Deterministic retrieval metrics and **model-judged** RAGAS are clearly
  separated; the paid judge is **NOT RUN** (UNVALIDATED) — never called by default.
- **Multilingual**: `evaluations/knowledge/multilingual_cases.json` holds the same semantic
  career question in all 7 languages. `eval_knowledge_governance.py` checks fixture
  completeness (bounded handling), not parity. Live multilingual retrieval quality is
  **UNVALIDATED**; the language boundary table states, per language, that UI support ≠ KB
  content coverage.

## 6. Prompt Lab (E6)

`src/application/prompt_lab/` — a bounded, human-reviewed experiment framework, admin-only
(`/api/v1/reviewer/prompt-lab/*`).
- **Model**: Experiment / Variant / EvaluationSet / ExperimentRun / MetricResult /
  HumanReview / PromotionDecision (all `extra="forbid"`; no secrets; variant configs are
  bounded PARAMETERS, never live prompt text).
- **Deterministic evaluators** (`model_policy_floors`, `specialist_evidence_limit`) run
  variants against a FIXED evaluation set with **no live model / no cost**. A run snapshots
  the **production config versions** (`src/config_versions.py`: prompt/model-policy/
  specialist/knowledge versions) for attribution (§16).
- **Guarantees** (enforced + tested): production isolation (a run never mutates the model
  policy — asserted byte-identical after runs), **no auto-promotion** (a PromotionDecision
  always has `applied_to_production=False`), **human decision required** (promotion before a
  review is refused), model-policy boundary (§31), specialist boundary (§32), private-data
  boundary (extra=forbid rejects smuggled candidate fields, §17).
- Evidence: `eval_prompt_lab.py`, `test_prompt_lab_p6.py`.

### Failed-experiment evidence (§19)
The repository already preserves a reverted prompt experiment
(`evaluations/security_classifier_experiment.json` + `scripts/security_classifier_experiment.py`,
`src/prompt_registry.py`): hypothesis → change → evaluation → regression → **decision to
revert**. It is left intact as first-class evidence of evidence-based engineering.

## 7. Feedback learning (E7)

Builds on the existing offline Feedback Intelligence (7G) — findings, recommendations
(`requires_human_approval=True`), experiment proposals and review decisions
(`executed=False` **always**).
- **Taxonomy** (`src/feedback_taxonomy.py`): a closed 11-category vocabulary (incorrect,
  irrelevant, too_verbose, too_brief, missing_evidence, poor_source, tool_choice,
  language_quality, retrieval_problem, practice_quality, other) mapped to change areas.
- **Improvement candidates** (`src/copilot/feedback_intelligence/improvement.py`): negative,
  category-classified signals aggregate into PROPOSED candidates carrying only safe
  aggregate metadata (category, counts, surface, opaque refs) — never candidate content.
- **Lifecycle**: PROPOSED → TRIAGED → EXPERIMENTING → ACCEPTED → IMPLEMENTED (or REJECTED).
  Every transition needs a human actor; **IMPLEMENTED is reachable only from ACCEPTED and
  is never set by an automated step**. Candidates link to a Prompt Lab experiment plan.
- **No auto-change** (§23/§42): nothing here edits a prompt, routing, model policy,
  knowledge or code. Evidence: `eval_feedback_learning.py`, `test_feedback_learning_p6.py`.
- Response-UX feedback (§33): the taxonomy carries `too_verbose` / `too_brief` /
  `missing_evidence` / `poor_source`; a candidate's Brief/Detailed preference is **never**
  auto-changed. Candidate-facing category *selection* in the UI is a carried follow-up
  (needs a DB column + i18n).

## 8. Retention (E7 / C9)

- **Inventory** (`src/application/retention_service.retention_inventory`): classifies every
  relevant store (application-required / user-controlled / temporary / operational /
  audit-security / external-provider-governed) with its deletion path — **no legal periods
  invented**, only technical defaults where known.
- **Safe temporary cleanup** (`TemporaryArtifactCleaner`): dry-run by default; only ever
  touches files **under one configured root** (a path escaping the root is refused, so a
  foreign/private artifact can never be deleted); preserves committed evidence
  (README/.gitkeep); **idempotent**. Existing `scripts/cleanup_runtime_data.py` (stale
  interview sessions, dry-run default) is unchanged and preserved.
- Evidence: `eval_retention.py` (fixture-only, no live deletion), `test_retention_p6.py`.

## 9. Reproducibility & demo readiness

- `scripts/demo_readiness.py` (§29) answers whether the KB is present, the index is
  compatible, sources are healthy, a retrieval smoke passes and required fixtures exist;
  it exits **non-zero** when a critical prerequisite is missing (`--governance-only` checks
  only committed artifacts). This prevents a demo from discovering a missing KB mid-question.
- `eval_knowledge_governance.py` gates governance LOGIC on committed artifacts and **reports**
  (does not gate) the generated-KB state — while `demo_readiness.py` is the hard gate. Fresh
  clone: `demo_readiness.py` fails clearly; after the knowledge build it passes.

## 10. Reviewer surface, authorization, security

- Admin-gated `/api/v1/reviewer/*` (knowledge readiness/manifest/coverage/source-health/
  language-boundary, config-versions, retention inventory, Prompt Lab experiments) —
  `Depends(require_platform_admin)`. NOT a full admin console; candidates cannot access it.
- Security (tested): candidate → 403 on every reviewer route; unauthenticated → 401/403;
  platform admin → 200 with **no secret/embedding/prompt/CoT leakage**; Prompt Lab cannot
  auto-promote or mutate production; retention cleanup cannot delete outside its root; K4
  rejects unentitled/out-of-bounds/unknown operations; feedback cannot cause a mutation.

## 11. Evaluation summary (all offline, 0 paid calls)

| Script | Gates |
|---|---|
| `eval_knowledge_governance.py` | manifest_integrity, source_health, readiness, retrieval_smoke, citation_integrity, geography, unsupported_query, domain_separation, multilingual_query_handling, artifact_readiness |
| `eval_prompt_lab.py` | experiment_isolation, variant_versioning, fixed_eval_set, metric_capture, no_auto_promotion, human_decision_required, production_config_unchanged, model_policy_boundary, specialist_boundary, private_data_boundary |
| `eval_feedback_learning.py` | feedback_capture, taxonomy, aggregation, privacy, improvement_candidate_creation, human_triage, experiment_link, no_auto_change, status_lifecycle |
| `eval_retention.py` | dry_run_mode, production_safety, temp/ocr cleanup, artifact_preservation, idempotent, owner_scope, expired-session interface, inventory_complete |

All four are wired into CI alongside the existing gates; the existing `eval_agent` /
`eval_multi_agent` etc. remain green.

## 12. No self-modifying system (§42)

Ask4Mo may OBSERVE, MEASURE, AGGREGATE, PROPOSE, EXPERIMENT and COMPARE. It never
autonomously edits production prompts, code, model policy, routing or knowledge, and never
deploys or promotes. Human engineering review is the final control — enforced by
`applied_to_production=False`, `executed=False`, the improvement lifecycle, and production
isolation, and asserted by the P6 evals.

## 13. Limitations & live-validation status
- K1/K2 figures are engineering-draft (human data/legal review carried).
- K4 live Adzuna calls UNVALIDATED / cost-gated (spec + validation only).
- Multilingual retrieval quality UNVALIDATED; KB native content is English (+ some German).
- BM25 degrades to empty without the `[rag]` extra.
- Bulk age-based checkpoint cleanup remains a gap (no safe bulk-list saver API).
- Model-judged RAGAS NOT RUN (paid).
- Reviewer surface is API-only (no admin-console UI); candidate-facing feedback category
  selection is a carried follow-up.
