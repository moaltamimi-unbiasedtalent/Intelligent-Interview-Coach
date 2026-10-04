# P10B-W10.7 - AI and Model Administration

**Status:** COMPLETE. Merged in PR #124 (`43fbf65`) with green CI. W10.11 (feature flags and safe platform configuration) follows.
One additive migration (`0022_ai_model_admin`). No new dependency. 0 paid/live calls. Permission registry stays at 43.

**The invariant:** an AI configuration is never active without a PASSED evaluation of its exact content (hash) and a DISTINCT second approver. There is no force parameter, no bypass route, no self-approval and no candidate- or admin-supplied provider slug.

## 1. Audit of the existing model layer
- `src/llm/models.py`: three profiles (`ModelProfile` fast/balanced/advanced) resolve to OpenRouter slugs `openai/gpt-5.6-luna|terra|sol`, overridable with `OPENROUTER_MODEL_FAST|BALANCED|ADVANCED`; capability metadata (tools, structured output, no temperature); `Workload` -> profile for registry-selected workloads; Interview workloads are session-selected.
- `src/llm/policy.py`: `OPERATION_POLICY` for eight operations (orchestration, three specialists, final response, structured generation, evaluation, realtime voice), `resolve_policy(operation, user_profile)`, bounded fallback chains.
- Import-time constants (`constants.DEFAULT_MODEL`, `copilot.constants.DEFAULT_MODEL`, `ApprovedModel`) call `model_id()` once at import. They stay as static legacy/validation values and are no longer the authoritative runtime selection. A governed configuration acts through `model_id`/`spec`, `resolve_policy` and the runtime consumers in `src/llm/runtime.py` (section 9A), including Interview Practice (section 19). Where Practice froze the slug: the `ModelSettings()` default at session creation, persisted in the session payload and read by `interview_service._generate`.

## 2. Approved catalogue (`src/ai_admin/catalogue.py`)
Code-defined, versioned (`CATALOGUE_VERSION`). Three entries mirroring the registry, no new model or provider:

| id | tier | may serve | cost class |
|---|---|---|---|
| luna | fast | fast, balanced | 1 |
| terra | balanced | fast, balanced, advanced | 2 |
| sol | advanced | balanced, advanced | 3 |

Slugs come from the registry's code defaults. `cost_class` is a relative ordinal, not a price.

## 3. Fast / Balanced / Advanced assignments
Baseline (the code as shipped): Fast = luna, Balanced = terra, Advanced = sol. A configuration may reassign a profile to any catalogue entry the entry is approved for, provided tiers stay monotonic (Fast <= Balanced <= Advanced) and cost class never decreases.

## 4. Environment-override compatibility
Precedence is: an ACTIVE governed configuration for this process's own environment, else the environment override (`OPENROUTER_MODEL_*`), else the code default. With nothing active the result is byte-identical to pre-W10.7 (`model_id == code_model_id`; proven by test and evaluator). The runtime diagnostic labels each profile `governed_configuration`, `environment_override` or `code_default`.

## 5. Schema (migration `0022_ai_model_admin`)
Four tables, schema only, nothing seeded (the migration changes no behaviour):
`ai_config_versions` (hash-pinned content, state, validation result), `ai_config_evaluations` (bound to one hash, `live_calls` CHECK = 0), `ai_config_approvals` (CHECK approver <> requester, one pending per version), `ai_config_activations` (append-only; partial unique index: one open row per environment). Fresh-DB and upgrade-from-0021 tests plus a downgrade round trip pass.

## 6. Lifecycle
DRAFT -> VALIDATE (frozen) -> EVALUATE (W10.9 job) -> APPROVE (second administrator) -> ACTIVATE (staging, then production) -> ROLLBACK / REVERT TO CODE / RETIRE. Version states: draft, validated, evaluated, evaluation_failed, approved, rejected, retired.

## 7. Hash strategy
SHA-256 over canonical JSON (sorted keys, fully expanded) plus the catalogue version. Key order and number spelling cannot change the hash; a catalogue change can never re-attribute an old hash. An INHERIT tunable is stored as JSON `null` and an explicit override as a number, so inherit and any number (even one equal to a code policy value) always hash differently.

## 8. Immutability
Only a draft is editable. Validation freezes it. A change is a new version (optionally based on an old one). Evaluations, approvals and activations are never edited; activations are append-only.

## 9. Tunable vs code-defined (inherit vs override)
Each retained tunable of a configurable operation is EITHER `null` (INHERIT: the real consumer keeps exactly its pre-W10.7 default) OR an explicit number (OVERRIDE: that exact value is forced into every consumer of the operation). There is no inference from equality with any baseline number.
Bounds apply only to explicit numbers: `max_output_tokens` 256..4096, `timeout_s` 10..180, `max_retries` 0..3. Time budget: `timeout x (retries + 1) <= 600 s`; an inherited timeout or retry count is evaluated at the LARGEST real default of any consumer of that operation (conservative, never skipped).
Only operations with a REAL, distinct runtime consumer are tunable: orchestration, structured_generation, evaluation. Specialist coaching (no shipped model call path), the role specialist (shares the structured-generation producer) and the final response (produced by the orchestration model) are NOT configurable.
Code-defined and not configurable: capability, minimum tier, fallback floor, structured-output and tool flags, temperature, deterministic (`NONE`) and realtime operations, the three specialists, the Interview session profile, prompts, secrets. Unknown keys are rejected.
`baseline_config()` is literally the code as shipped: every tunable `null`. A baseline governed configuration changes no runtime value (test-proven).
API/UI: an update sends `settings` with explicit `null` to clear an override back to inherit (the route uses `exclude_unset`, not `exclude_none`, so a deliberate null survives); an absent field is also inherit because `settings` replaces the whole configuration. The UI shows "Inherit runtime default: <real values>" or "Override: N" per field, never a number that is not enforced.

### 9A. Real pre-W10.7 consumer defaults and the code policy table
| Operation | Consumer | Default tokens | Default timeout | Default retries | Code policy table (advisory only) |
|---|---|---|---|---|---|
| orchestration | Mo agent chat model (`_default_model_factory`) | 1024 | 60 s | 1 | 1536 / 60 s / 2 |
| structured_generation | Career structured tools (`build_structured_producer`) | 4096 | 60 s | 1 | 1024 / 45 s / 1 |
| structured_generation | Practice strategy, question, branch (`_generate`) | 3072 | 60 s | 1 | 1024 / 45 s / 1 |
| evaluation | Practice answer evaluation and report (`_generate`) | 3072 | 60 s | 1 | 2048 / 90 s / 2 |
Confirmed: the policy table differs from the real runtime defaults for most fields (e.g. orchestration tokens 1024 vs 1536, evaluation retries 1 vs 2). That is exactly why equality with the table cannot mean "inherit"; `OPERATION_POLICY` numbers are advisory and are not what any consumer applies. final_response, specialist_role_analysis, specialist_coaching: no separate runtime path (not tunable). Deterministic and realtime operations: not applicable. Career chat synthesis follows the governed model slug but has no tunable.

## 10. Validation checks (deterministic)
catalogue membership, no raw provider slug anywhere, profile allowed for entry, tier monotonic, cost ordering, tunable bounds, time budget, capability support (tools/structured) for every operation and profile, floors preserved, code-defined operations untouched.

## 11. Evaluation
`ai_evaluate_config` is a W10.9 job (id-only payload, idempotent: a terminal evaluation is a no-op). The evaluator installs the candidate as a temporary snapshot and drives the REAL `resolve_policy` and registry for every operation x profile (24 cases), then checks: effective profile = max(user, floor), slug is the catalogue slug of the effective profile, fallbacks stay inside floors and the catalogue, tunables applied exactly, code-defined fields unaltered, deterministic operations model-free, realtime has no chat slug, Interview session slugs keep their profile meaning, exactly three specialists, a raw slug is still rejected at the boundary. Versioned (`ai-eval-1`); a changed evaluator or catalogue invalidates earlier evaluations.

## 12. Hash attribution
The version, the evaluation, the approval and each activation all store the same hash. Approval and activation re-compute the hash from the stored content and refuse on any mismatch.

## 13. Live call count and quality-evidence boundary
0 live calls (DB CHECK, evaluator test with sockets and HTTP disabled). The evaluation is deterministic contract evidence. It is NOT a measure of live answer quality; the UI and API say so. Live quality remains a separate, human-owned evidence class this wave does not produce.

## 14. Second-approver semantics
The approver must be an active account holding `platform.ai.activate`, different from the person who requested approval AND different from the configuration's author. Enforced in the service, by a DB CHECK (requester) and again at activation and in the resolver (distinct-approval re-check). Self-approval returns 403.

## 15. Activation rules
`activate` re-derives from stored facts: state approved, latest evaluation passed by the current evaluator for this exact hash with 0 live calls, an approved record whose decider is neither requester nor author. The target is ALWAYS this server's own environment (section 16). Production additionally requires a prior STAGING activation of the same version with the same content hash; a development activation never satisfies it. Activating the already-active version is refused.

## 16. Environment model (server-authoritative)
Three activation environments: `development`, `staging`, `production`. The deployment's `API_ENV` decides which one a process belongs to (aliases follow the repository vocabulary: `development`/`dev`/`local`/`test`/`testing` -> development; `staging`; `production`/`prod`). An UNRECOGNISED value is unsupported: the process resolves the code defaults and refuses governed activation and rollback (it never becomes staging or production).
There is no environment field in the activation or rollback requests and no environment in the rollback URL: a browser cannot nominate a target. A staging process can only write staging; a production process can only write production, and only after a staging record for the same hash exists in the shared control plane. Development and test activations are real but are never promotion evidence. Fixtures may inject the environment into the service for deterministic tests; HTTP callers cannot.

## 17. Runtime resolver, cache and convergence
`src/ai_admin/resolver.py` installs through the single seam `src/llm/governed.py` (set at repository construction in the API and worker). Per-process snapshot with a 5 s TTL. Activation and rollback are immediate in the control plane and invalidate the cache of the SAME process at once; OTHER processes (for example the worker or a second API replica) converge within the bounded TTL (at most about 5 s). There is no broadcast and no external cache, so cross-process effect is NOT instant. It re-verifies hash, approved state, passed evaluation and distinct approval at load and FAILS CLOSED to code defaults (reasons: version_not_approved, hash_mismatch, catalogue_changed, no_passed_evaluation, no_distinct_approval, unsupported_environment, load_failed). A provider exception never reaches the registry.

## 18. Rollback and history
Rollback (this server's environment only) restores the previous activated version (re-verified like any activation) or reverts to the code defaults. It needs `platform.ai.activate`, a reason and no new approval. Same-process effect is immediate; other processes converge within the cache TTL (section 17). History is append-only and visible.

## 19. Boundaries
- Raw slugs: no schema field accepts one; `_resolve_profile` still rejects a candidate slug; `known_profile_for_slug` never turns an unknown string into a profile and the governed mapping never remaps one.
- Interview Practice stays SESSION-PROFILE selected: one profile for all of its operations (no per-operation routing). The Next.js flow sends no model at all (`CreateInterviewRequest` has no model field; an extra field is ignored) and creates `ModelSettings()` (Balanced). `ModelSettings.model` is kept only as a compatibility marker of the profile (historical sessions persist the slug); at execution `interview_service._generate` resolves it with `governed_slug(...)`: profile -> the model the ACTIVE configuration assigns to that profile. Activating a configuration that maps Balanced to another catalogue entry therefore changes the model a Balanced session uses on its next call, while the session stays Balanced. Legacy slugs (`gpt-5-mini`, `-nano`, `gpt-5`) and the current Luna/Terra/Sol slugs keep their profile. Where the slug used to freeze: `ModelSettings()` default at session creation, serialised in the session payload, read by `_generate`; it is now only a marker. Streamlit (legacy) selects from the import-time list and is governed the same way at the same boundary.
- The import-time constants (`DEFAULT_MODEL`, `LOW_COST_MODEL`, `HIGH_CAPABILITY_MODEL`, `APPROVED_MODELS`, `ApprovedModel`) remain for validation and legacy compatibility only; they are no longer the authoritative runtime selection path. `ApprovedModel` also accepts the catalogue default slugs so a record naming the model that actually served a request validates.
- Deterministic operations stay model-free; realtime resolves no chat slug; exactly three specialists; no evaluation specialist; candidate answer evaluation stays LLM-backed with no deterministic scorer.
- Prompt Lab stays offline; there is no prompt CMS; no secret handling here (W10.6 owns it).
- Candidates still choose only fast, balanced or advanced (and today the Next.js candidate chooses none).

## 20. Permissions, roles and ROLE-W10-01
`platform.ai.read` (read), `platform.ai.manage` (draft/validate/evaluate/request approval/retire), `platform.ai.activate` (approve/reject/activate/rollback). Only `platform_admin` holds manage and activate. Permission count stays 43. ROLE-W10-01 (no dedicated AI/Operations activator separation) is noted: separation is enforced by the distinct-approver rule rather than a new role.

## 21. Admin UI
`/admin/ai` (what this server resolves, environments, versions, new draft, approvals, history, catalogue, code-defined behaviour) and `/admin/ai/[id]` (edit draft with catalogue ids and bounded numbers, frozen settings, changes from baseline, checks, evaluations with hash match, approval, activation). English-only, VerifiedLink, `ActionDialog` with a required reason. No provider-name input exists.

## 22. Audit
Eleven canonical events (`admin.ai_config_created|updated|validated`, `ai_evaluation_requested|completed`, `ai_approval_requested`, `ai_approved|rejected`, `ai_activated`, `ai_rolled_back`, `ai_retired`), written in the same transaction as the change. Payloads: ids, hash, environment, states. Never a prompt or candidate content.

## 23. Verification evidence (measured)
Measured on the latest correction commit: backend 2942 passed, 4 skipped; vitest 722 passed; Playwright 213 passed; all 36 CI evaluators pass (including `eval_admin_ai_models.py`, now with the environment, Practice and tunable-consumer checks); ruff, compileall, tsc, lint, build and the i18n scanner clean; dev DB, schema, checkpoint, Chroma, cache and `evaluations/` fingerprints unchanged; manual QA with a separate worker (22 original checks plus 14 environment, Practice and tunable checks, re-run after the inherit/override change) all pass; 0 paid/live calls. Test files: `tests/test_ai_admin_w10_7.py` (lifecycle, environments, resolver, boundaries, migration), `tests/test_ai_runtime_w10_7.py` (Practice governance, legacy compatibility, tunable propagation to the real call sites), vitest `tests/ai-w10-7.test.tsx`, the Playwright journey in `e2e/admin.spec.ts`, and the CI gate `scripts/eval_admin_ai_models.py`.

## 24. Known limits
Cross-process convergence is TTL-based (at most about 5 s), never instant. The catalogue has three entries; adding a model is a code change. Live model quality is not evaluated here. Governed tunables are absolute when changed from the code policy value. Staging-to-production promotion assumes staging and production share the control-plane database (or a staging record exists in the production one). ROLE-W10-01 stays open for W10.14.
