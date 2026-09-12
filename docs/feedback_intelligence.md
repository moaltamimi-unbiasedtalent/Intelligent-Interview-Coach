# Feedback Intelligence (Phase 7G)

An **offline** engineering/admin workflow that turns SAFE, structured product and evaluation
signals into findings, human-reviewed recommendations and experiment proposals. It is a **safe
learning loop** — it analyses and recommends; a human decides; an engineer implements separately.

## What "learning" means here — and what it does NOT

It means: aggregate structured signals → detect recurring patterns → assess evidence strength →
propose measurable, guardrailed experiments → **stop for human review**. It does **not** mean a
self-modifying or self-improving system. Feedback Intelligence NEVER automatically rewrites
prompts, edits code, changes LangGraph, tool schemas, retrieval weights, source ranking, the
vector index, the knowledge base, canonical mappings, model config, evaluation cases, thresholds,
security policies or allowlists; and it never creates commits/PRs, deploys, or tunes models. There
is no automatic arrow back into production.

## Boundaries

- **Not candidate-facing**, not part of Home → Ask Mo → Prepare → Practise → Progress, and **not**
  a seventh Agent tool. The candidate Agent keeps its **6** tools.
- A separate, bounded, deterministic pipeline (`src/copilot/feedback_intelligence/`) — not the
  candidate LangGraph.

## Signal sources (safe, structured only)

`user_feedback` (surface + rating only — never the free-text comment), `retrieval_evaluation`,
`ragas_evaluation`, `knowledge_coverage`, `external_research_evaluation`, `error_category`,
operational aggregates. Missing/absent sources are reported, never fatal; a malformed artifact
yields a source-specific warning, never silent zeros.

## Privacy (§8/§10)

`FeedbackSignal` is `extra="forbid"` — it structurally rejects any raw-content/candidate field
(CV, JD, answers, memory, email, name, phone, comment). Correlation uses opaque/pseudonymous ids
only; aggregation is never by candidate identity. No candidate content ever reaches an LLM.

## Evidence discipline

- **Minimum support** (§17): `support < 3` → OBSERVATION_ONLY; `≥ 3` → pattern; `≥ 5` →
  recommendation-eligible (configurable).
- **Honest sample sizes** (§18): every finding reports `support_count` / `sample_size` / `rate`;
  a "50%" from 1/2 is never presented as strong evidence. Unique **runs** are counted, not raw
  events (§68); duplicates are de-duplicated (§11/§67).
- **Confidence ≠ severity** (§19/§21): a potential secret leak can be `severity=CRITICAL`,
  `confidence=LOW`. An optional Wilson lower bound is available (§20).
- **Positive findings** (§22): it reports what is working (citation 1.0, unknown-role safety 1.0,
  consistently helpful operations), not just complaints.
- **Compatible-only drift** (§24/§63): metrics compare only when dataset hash + version match;
  RAGAS `NOT_RUN` / `NOT_APPLICABLE` / `None` are never scored as 0 (§26).

## Safety escalation & benchmark-gaming protection

Safety-metric shortfalls (citation/geography/unknown-role/SSRF/prompt-injection < 1.0) escalate to
CRITICAL even from small support (§28). Recommendations can **never** propose weakening a safety
control, deleting/altering test cases, or lowering thresholds — such text is filtered out (§27/§70).

## Recommendations & experiments

Each recommendation answers: what problem, what evidence, how many signals, expected benefit, what
could regress, how to validate, what would trigger rollback (§69) — phrased as things to
investigate/test, never "change line X and deploy" (§33). Every experiment carries mandatory
guardrails (citation/geography/unknown-role/SSRF/injection stay at target, cross-user leakage 0,
P0/P1 remain 0, §34) and references existing datasets **without editing them** (§71).

## Human review (§35/§36)

The workflow terminates at `awaiting_review`. `python scripts/review_feedback_recommendation.py
--run <dir> --recommendation <id> --decision approve|reject|defer` appends an **immutable** decision.
**APPROVE means "approved for an engineer to consider" — it executes nothing**: no code, prompt,
config, KB or Git change. History is append-only.

## Self-modification guards (§37/§38/§78/§79)

READ access to approved signal artifacts; WRITE access ONLY under
`evaluations/feedback_intelligence/` or `data/feedback_intelligence/` (`safe_output_path` rejects
anything else). The package imports no `httpx`/`requests`/`socket`, has no shell execution and no
git-write capability (the only `subprocess` use is a read-only `git rev-parse`/`status` for
provenance). An architectural test proves no forbidden capability exists.

## Optional LLM synthesis (off by default)

`--synthesize --allow-paid` adds a narrative summary over SAFE aggregate summaries (finding
IDs/counts/labels only — never raw data). It requires explicit `--allow-paid` (credentials alone
are insufficient, §44); `--estimate-only` reports scope with no call. Synthesis can ONLY add
narrative — a fingerprint over the deterministic fields is asserted unchanged before/after (§47).

## Provenance (§53/§54)

Each run records full git SHA, `git_dirty`, generated-at, analysis version and input-artifact
hashes in an immutable snapshot, so recommendations are reproducible. A committed reviewed baseline
would follow the Phase 7E two-commit rule (clean checkout → `git_dirty=false`).

## Commands

```bash
python scripts/run_feedback_intelligence.py                     # deterministic, offline
python scripts/run_feedback_intelligence.py --synthesize --estimate-only
python scripts/run_feedback_intelligence.py --synthesize --allow-paid   # opt-in narrative
python scripts/review_feedback_recommendation.py --run <dir> --recommendation R001 --decision approve
python scripts/eval_feedback_intelligence.py    # 33 deterministic cases
python scripts/audit_feedback_intelligence.py   # capability + safety audit
```

## Limitations

Signals are not controlled experiments; feedback is self-selected; no candidate content is
analysed; recommendations are advisory and require human implementation; the paid RAGAS judge and
live research are not invoked here. Findings surface only from real audit/evaluation evidence — no
gap is hard-coded as a permanent finding.
