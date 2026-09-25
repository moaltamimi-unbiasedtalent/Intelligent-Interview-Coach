# P5 + E4 — Bounded Multi-Agent Architecture & Per-Operation Model Policy

_Capstone P5 (bounded multi-agent) + E4 (central per-operation model policy). Builds on
P1–P4 without changing Mo's ReAct loop, Practice, RAG governance, HITL, identity, privacy,
provenance, i18n (7 locales) or the Brief/Detailed presentation contract._

## 1. Objective & shape

Mo remains the **single candidate-facing orchestrator**. Three **materially distinct,
bounded specialists** sit behind Mo, reached only through allowlisted tools; a **central
per-operation model policy** replaces scattered model selection. No agent-to-agent free
chat, no recursion, bounded budgets, schema-validated structured outputs, and
owner-scoped access to candidate-approved private evidence.

```
candidate ── Mo (ReAct, unchanged) ──▶ tools allowlist
                                         ├─ 6 Career tools (unchanged)
                                         ├─ AnalyzeRoleOpportunity  → Role & Opportunity specialist
                                         ├─ FindCandidateEvidence   → Candidate Evidence specialist (DET, owner-scoped)
                                         ├─ BuildCoachingStrategy   → Interview Strategy / Coach specialist
                                         └─ 2 HITL action tools (unchanged)
     model choice for every operation ── src/llm/policy.py (E4) ──▶ src/llm/models.py registry
```

Design tension (from the decomposition audit) resolved: specialists are **bounded tools**,
not new graph nodes — this preserves the `bind_tools` allowlist, the bounded step budget,
HITL, the output guard, the `retrieval_used` invariant and the deterministic agent eval
automatically, while keeping Mo the orchestrator.

## 2. The three specialists

| Specialist | Module | Model policy operation | Model? | Reads private evidence? |
|---|---|---|---|---|
| Role & Opportunity | `src/agent/specialists/role_specialist.py` | `SPECIALIST_ROLE_ANALYSIS` | yes (reuses governed JD-analysis) | no |
| Candidate Evidence | `src/agent/specialists/evidence_specialist.py` | `SPECIALIST_EVIDENCE_ANALYSIS` | **no (deterministic)** | **yes, owner-scoped** |
| Interview Strategy / Coach | `src/agent/specialists/coaching_specialist.py` | `SPECIALIST_COACHING` | yes (deterministic fallback today) | no (receives the bounded packet only) |

- **Typed contracts** (`specialists/schemas.py`): each specialist has a validated input and
  output model with bounded list lengths — no free-form string channel between specialists.
- **Registry + router** (`specialists/registry.py`, `specialists/router.py`): a closed
  `SpecialistName` allowlist and a pure, bounded, deterministic `recommend_specialists`.
  An unknown specialist name is never valid; the router returns at most the three
  specialists, de-duplicated, and is a pure function (same input → same output).
- **Advisory only**: no side effects, no auto-memory, cannot start Practice, never set
  `retrieval_used`.

### Role & Opportunity specialist
Turns a JD / prior structured analysis / role name into a bounded `RoleBrief` (key
competencies, interview themes, priorities). It **reuses the existing governed,
injection-guarded, usage-captured** `career_service.analyze_job_description` — it opens no
new raw model path. Degrades to a role-name-only or explicit "insufficient" brief.

### Candidate Evidence specialist (deterministic, owner-scoped)
Selects and ranks the owner's **APPROVED** evidence for a stated need by transparent
keyword overlap (`specialists/_matching.py`). It uses **no model** (E4 declares the
operation `capability=NONE`), which makes it **injection-inert and privacy-safe**:
- `user_id` is a **trusted argument from run state**, never a model-supplied id;
- evidence comes only through the owner-scoped `EvidenceAccessService`
  (`src/application/evidence_access_service.py`) →
  `DocumentRepository.approved_claims` (accepted/edited only) +
  `StoryRepository.evidence_stories` (verified / user-authored only);
- rejected / unreviewed claims, `source_revoked` and `model_suggested` stories are
  excluded **at the repository layer**;
- raw uploaded documents are **never** read (documents remain untrusted DATA — P4).

### Interview Strategy / Coach specialist
Maps the role brief + bounded evidence into a `CoachingPlan`: strengths (with supporting
evidence ids), gaps, recommendations, and **CLARIFICATION_NEEDED** prompts wherever a
competency has no supporting evidence — it **never invents metrics/outcomes**. The E4
policy declares it an LLM (STRUCTURED) operation and the runtime accepts an injectable
`reasoner`; because a **live coaching model is UNVALIDATED** in this phase (mirroring the
OCR / OIDC live-path precedent), the **deterministic fallback owns the path today**, so all
tests and the offline eval run with **zero paid calls**. When a reasoner is supplied, its
output is schema-validated **and every model-produced evidence id is re-validated against
the owner-scoped selection** (a model can never introduce or assert an id the selection did
not contain).

## 3. E4 — central per-operation model policy (`src/llm/policy.py`)

One module answers "which model, at what capability, with which structured-output /
timeout / retry / fallback discipline?" for every operation. It is a **pure resolver over
the existing registry** — no provider call, no secret at import or resolution — and does
**not** replace `src/llm/models.py` (the registry stays the single source of truth for
slugs and env overrides).

**Operations** (`ModelOperation`): `ORCHESTRATION`, `SPECIALIST_ROLE_ANALYSIS`,
`SPECIALIST_EVIDENCE_ANALYSIS`, `SPECIALIST_COACHING`, `FINAL_RESPONSE`,
`STRUCTURED_GENERATION`, `EVALUATION`.

Each `OperationPolicy` declares: capability (`tool_calling` / `structured` / `text` /
**`none`**), a `min_capability` floor, a `fallback_floor`, `structured_output`,
`requires_tools`, `temperature` (None ⇒ omit for the reasoning family), `max_output_tokens`,
`timeout_s`, `max_retries`, and a rationale. **No secret lives in a policy.**

### Resolution algorithm (two orthogonal dimensions)
- **User profile** (Fast/Balanced/Advanced) = the candidate's cost/latency **envelope**
  (validated Literal; a raw slug is rejected upstream and here — see below).
- **Operation policy** = the **minimum capability** the operation needs.
- **Effective tier = max(user_profile, min_capability)**, capped at Advanced. So an
  operation never runs below the capability it needs (e.g. `ORCHESTRATION` on a Fast user
  clamps **up** to Balanced because tool calling is mandatory); `capability_capped` records
  when the floor raised the user's tier.
- **Fallback chain** = the tiers strictly **below** the effective tier down to the
  operation's `fallback_floor` (bounded, monotone) — graceful degradation on provider
  failure that never drops below a safe floor (orchestration/`FINAL_RESPONSE` never degrade
  to Fast).
- A **deterministic** operation (`capability=NONE`) resolves to **no model** (`uses_model`
  False, `model_id` None); callers must not build a client.

These are independent of Brief/Detailed and of interface/conversation/dictation language —
**none of those ever change the model, and the model never changes them.**

### Raw-slug rejection (defence in depth)
`resolve_policy` accepts only a `ModelProfile` or `None`. A raw provider slug is not a
`ModelProfile`, so it can never *select* that slug's model — it falls back to the safe
Balanced default. Combined with `AgentApplicationService._resolve_profile` (which rejects
anything but fast|balanced|advanced), the browser can never choose a model.

## 4. Preserved invariants

- **Mo's ReAct loop / graph / nodes**: unchanged. Specialists are tools, not nodes.
- **RAG governance**: `SearchCareerKnowledge` still solely owns `retrieval_used`; no
  specialist sets it (the deterministic agent eval's `retrieval_sequence_validity` gate
  stays 1.0).
- **HITL / memory / Practice**: unchanged; specialists are advisory (no side effects).
- **Identity & isolation**: cross-user access denied through the agent service; the evidence
  specialist is owner-scoped end to end.
- **Privacy / provenance**: approved-only evidence, safe projections, no raw documents in a
  prompt, no CoT / secret / private content in events, results or the diagnostic.
- **i18n (7 locales)** & **Brief/Detailed**: no new candidate-facing strings were added
  (specialist output is reviewer/diagnostic data surfaced through the existing safe
  `AgentRunResult`), so the language and presentation dimensions are untouched.

## 5. Observability & the reviewer diagnostic

`AgentRunResult.specialist_outputs` carries a safe projection: which specialists ran plus
their bounded structured outputs (role brief / owner-scoped evidence selection / coaching
plan). `ResolvedModelPolicy.to_dict()` is a safe projection (operation, capability, public
slug, bounded numeric policy) with **no secret, prompt, candidate content or CoT**. No new
candidate chat surface is added.

## 6. Evaluation (deterministic, offline, zero paid calls)

`scripts/eval_multi_agent.py` → `src/agent/multi_agent_eval.py`. Gates (all must pass):

| Metric | Gate |
|---|---|
| `policy_pass_rate` (resolution, floors, fallback, deterministic op) | == 1.0 |
| `router_valid_rate` / `router_bounded_rate` / `router_deterministic_rate` | == 1.0 |
| `injection_inert_rate` (7 languages EN/DE/FR/ES/IT/PT/NL) | == 1.0 |
| `uncovered_yield_clarifications` (no fabrication) | == 1 |
| `recommendation_ids_valid` / `reasoner_bogus_ids_sanitised` | == 1 |
| `no_owner_returns_empty` | == 1 |
| `specialists_completed` / `specialist_packet_present` / `coaching_present` | == 1 |
| `unknown_specialist_rejected` | == 1 |
| **Hard zero invariants**: `cross_user_evidence_leaks`, `other_user_content_leaks`, `cross_user_access_failures` | == 0 |

The existing `scripts/eval_agent.py` gate still passes unchanged (56 cases; required-tool
recall 1.0, retrieval-sequence validity 1.0, HITL 1.0, cross-user 0). Pytest:
`tests/test_model_policy.py` (11) + `tests/test_multi_agent_specialists.py` (15).

## 7. Files

**New**: `src/llm/policy.py`; `src/agent/specialists/` (`__init__`, `schemas`, `_matching`,
`role_specialist`, `evidence_specialist`, `coaching_specialist`, `registry`, `router`);
`src/agent/specialist_tools.py`; `src/application/evidence_access_service.py`;
`src/agent/multi_agent_eval.py`; `scripts/eval_multi_agent.py`; `tests/test_model_policy.py`;
`tests/test_multi_agent_specialists.py`; these two docs.

**Modified**: `src/documents/repository.py` (owner-scoped `approved_claims` /
`evidence_stories`); `src/agent/registry.py` (register specialist tools);
`src/agent/tooling.py` + `src/agent/nodes.py` (trusted `user_id` + specialist context);
`src/agent/state.py` + `src/agent/models.py` + `src/application/agent_service.py`
(specialist outputs, `evidence_service` wiring); `src/api/dependencies.py` (wire owner-scoped
evidence service); `src/agent/policies.py` (system prompt: specialist tools);
`.github/workflows/ci.yml`; the requirements matrix; `CLAUDE.md`.

## 8. Risks & limits

- The coaching **live model path is UNVALIDATED** (no paid call authorised); the
  deterministic fallback is the shipped path. When a reasoner is wired, its ids are already
  server-validated.
- Keyword-overlap matching is intentionally simple (transparent, reproducible, injection
  inert); it is a ranking heuristic, not semantic retrieval.
- No live/paid comparative benchmark was executed (consistent with prior phases).
- Migrations: none added (no schema change); Alembic head stays `0010_candidate_documents`.
