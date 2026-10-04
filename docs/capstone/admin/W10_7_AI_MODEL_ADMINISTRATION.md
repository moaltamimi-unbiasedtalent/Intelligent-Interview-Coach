# P10B-W10.7 - AI and Model Administration

**Status:** implemented on branch `feat/p10b-w10-7-ai-model-admin`; **complete when merged to `main`**. **W10.11 is NOT STARTED.**
One additive migration (`0022_ai_model_admin`). No new dependency. 0 paid/live calls. Permission registry stays at 43.

**The invariant:** an AI configuration is never active without a PASSED evaluation of its exact content (hash) and a DISTINCT second approver. There is no force parameter, no bypass route, no self-approval and no candidate- or admin-supplied provider slug.

## 1. Audit of the existing model layer
- `src/llm/models.py`: three profiles (`ModelProfile` fast/balanced/advanced) resolve to OpenRouter slugs `openai/gpt-5.6-luna|terra|sol`, overridable with `OPENROUTER_MODEL_FAST|BALANCED|ADVANCED`; capability metadata (tools, structured output, no temperature); `Workload` -> profile for registry-selected workloads; Interview workloads are session-selected.
- `src/llm/policy.py`: `OPERATION_POLICY` for eight operations (orchestration, three specialists, final response, structured generation, evaluation, realtime voice), `resolve_policy(operation, user_profile)`, bounded fallback chains.
- Import-time constants (`constants.DEFAULT_MODEL`, `copilot.constants.DEFAULT_MODEL`, `ApprovedModel`) call `model_id()` once at import. They stay static. The runtime resolvers (`spec(profile)` in the Agent factory, `resolve_policy`, `model_id`) are what a governed configuration affects.

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
Precedence is: an ACTIVE governed configuration for the process environment, else the environment override (`OPENROUTER_MODEL_*`), else the code default. With nothing active the result is byte-identical to pre-W10.7 (`model_id == code_model_id`; proven by test and evaluator). The runtime diagnostic labels each profile `governed_configuration`, `environment_override` or `code_default`.

## 5. Schema (migration `0022_ai_model_admin`)
Four tables, schema only, nothing seeded (the migration changes no behaviour):
`ai_config_versions` (hash-pinned content, state, validation result), `ai_config_evaluations` (bound to one hash, `live_calls` CHECK = 0), `ai_config_approvals` (CHECK approver <> requester, one pending per version), `ai_config_activations` (append-only; partial unique index: one open row per environment). Fresh-DB and upgrade-from-0021 tests plus a downgrade round trip pass.

## 6. Lifecycle
DRAFT -> VALIDATE (frozen) -> EVALUATE (W10.9 job) -> APPROVE (second administrator) -> ACTIVATE (staging, then production) -> ROLLBACK / REVERT TO CODE / RETIRE. Version states: draft, validated, evaluated, evaluation_failed, approved, rejected, retired.

## 7. Hash strategy
SHA-256 over canonical JSON (sorted keys, fully expanded defaults) plus the catalogue version. Key order and number spelling cannot change the hash; a catalogue change can never re-attribute an old hash.

## 8. Immutability
Only a draft is editable. Validation freezes it. A change is a new version (optionally based on an old one). Evaluations, approvals and activations are never edited; activations are append-only.

## 9. Tunable vs code-defined
Tunable (per model-backed operation, bounded): `max_output_tokens` 256..4096, `timeout_s` 10..180, `max_retries` 0..3, and `timeout x (retries + 1) <= 600 s`. Code-defined and not configurable: capability, minimum tier, fallback floor, structured-output and tool flags, temperature, deterministic (`NONE`) and realtime operations, the three specialists, the Interview session profile, prompts, secrets. Unknown keys are rejected, never ignored.

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
`activate` re-derives from stored facts: state approved, latest evaluation passed by the current evaluator for this exact hash with 0 live calls, an approved record whose decider is neither requester nor author. Production additionally requires a prior staging activation of the same version. Activating the already-active version is refused.

## 16. Environment model
Two environments, `staging` and `production`. A process maps `API_ENV=production` to production and everything else (staging, development, test) to staging. One open activation per environment.

## 17. Runtime resolver and cache
`src/ai_admin/resolver.py` installs through the single seam `src/llm/governed.py` (set at repository construction in API and in the worker). Per-process snapshot with a 5 s TTL plus explicit invalidation on activate/rollback in the same process; other processes converge within the TTL (no broadcast, no external cache). It re-verifies hash, approved state, passed evaluation and distinct approval at load and FAILS CLOSED to code defaults (reasons: version_not_approved, hash_mismatch, catalogue_changed, no_passed_evaluation, no_distinct_approval, load_failed). A provider exception never reaches the registry.

## 18. Rollback and history
Rollback restores the previous activated version (re-verified like any activation) or reverts to the code defaults. It needs `platform.ai.activate`, a reason and no new approval (only an already approved, previously activated version is eligible). History is append-only and visible.

## 19. Boundaries
- Raw slugs: no schema field accepts one; `_resolve_profile` still rejects a candidate slug.
- Interview Practice keeps one session-selected profile for its four operations; its slugs come from the import-time approved list and are NOT changed by activation.
- Deterministic operations stay model-free; realtime resolves no chat slug; exactly three specialists; no evaluation specialist; candidate answer evaluation stays LLM-backed with no deterministic scorer.
- Prompt Lab stays offline; there is no prompt CMS; no secret handling here (W10.6 owns it).
- Candidates still choose only fast, balanced or advanced.

## 20. Permissions, roles and ROLE-W10-01
`platform.ai.read` (read), `platform.ai.manage` (draft/validate/evaluate/request approval/retire), `platform.ai.activate` (approve/reject/activate/rollback). Only `platform_admin` holds manage and activate. Permission count stays 43. ROLE-W10-01 (no dedicated AI/Operations activator separation) is noted: separation is enforced by the distinct-approver rule rather than a new role.

## 21. Admin UI
`/admin/ai` (what this server resolves, environments, versions, new draft, approvals, history, catalogue, code-defined behaviour) and `/admin/ai/[id]` (edit draft with catalogue ids and bounded numbers, frozen settings, changes from baseline, checks, evaluations with hash match, approval, activation). English-only, VerifiedLink, `ActionDialog` with a required reason. No provider-name input exists.

## 22. Audit
Eleven canonical events (`admin.ai_config_created|updated|validated`, `ai_evaluation_requested|completed`, `ai_approval_requested`, `ai_approved|rejected`, `ai_activated`, `ai_rolled_back`, `ai_retired`), written in the same transaction as the change. Payloads: ids, hash, environment, states. Never a prompt or candidate content.

## 23. Verification evidence (measured)
- Backend `pytest`: 2898 passed, 4 skipped (baseline 2829; +69 in `tests/test_ai_admin_w10_7.py`). Frontend vitest 719 passed (16 new). `tsc`, lint, production build, i18n scanner (0 offenders) clean. Playwright 213 passed (212 + the W10.7 lifecycle journey). `ruff check .` clean.
- CI evaluators: all 36 pass, including the new `scripts/eval_admin_ai_models.py` (32 checks including a real lifecycle on a temp database). `evaluations/` is untouched and the dev DB, schema, checkpoint, Chroma and cache fingerprints are identical before and after.
- Routes: 19 new `/admin/ai` routes, 120 admin routes in total, 0 ungated; permission registry stays 43.
- Manual QA (real API routes, separate worker process, temp DB, no provider key): 22 of 22 checks pass, including self-approval 403, activation before approval 409, production before staging 409, runtime governed with the tunable applied and realtime/deterministic untouched, rollback to code defaults and append-only history.
- Performance: `model_id` costs 0.44 us with no provider and 0.68 us with the cached resolver; 200,000 calls caused one database load; a cold load is about 0.4 ms. New admin pages are about 4 kB each (116 to 120 kB first load).

## 24. Known limits
Interview Practice and import-time constants are unaffected by activation (documented, deliberate). Multi-process convergence is TTL-based. The catalogue has three entries; adding a model is a code change. Live model quality is not evaluated here.
