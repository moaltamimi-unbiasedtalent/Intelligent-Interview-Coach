# Ask4Mo — Sprint 4 Technical Critique

An honest engineering retrospective: the architecture choices, what worked, what didn't,
the defects found (including after the "final" freeze), and the lessons carried into the
Capstone. Not marketing copy — where a decision was a trade-off, the rejected alternative
and the cost are stated.

## 1. Architecture choices

Ask4Mo is one bounded, stateful **LangGraph ReAct-style agent** ("Mo") over a **FastAPI**
application layer, with a **Next.js** client. Deterministic capabilities (gap analysis,
preparation planning, the retrieval router) live in **tools**, not in the model. Interview
Practice is a **deterministic durable workflow**, not an agent. Feedback Intelligence is an
**offline** analysis pipeline. The through-line: *the model decides whether/when to act; the
system owns how.*

## 2. What worked

- **Tools-as-allowlist.** A strict registry (no dynamic import/eval) made "what can the agent
  do" auditable and testable, and made the capability toggle a one-line exclusion.
- **Deterministic retrieval routing behind an agent decision.** Agentic RAG (agent decides
  *whether*; router decides *which*) kept citations reproducible while letting the model skip
  needless retrieval. Retrieval quality is measurable offline (81-case suite).
- **Durable checkpoints + OCC/lease for Practice.** Refresh/resume "just works" and Q1-without-
  reload survived a live rehearsal.
- **Safety by construction.** `extra="forbid"` signal models, SSRF guards, https-only source
  links, and the no-fabricated-citation guard all held under live testing.

## 3. What did not work (first time)

- The **post-release UI audit** found four surfaces that looked done but weren't wired
  (Progress, History detail, Sources links, Evaluation) — see §5.
- **Live tool-selection** is imperfect (§10): the model often answers well without invoking a
  discrete tool, so the scripted orchestration suite ≠ live behaviour.
- **RAGAS generation-quality numbers are low** (§11) — an honest signal, not hidden.

## 4. Bugs discovered during rehearsal

PROBLEM: the final live golden rehearsal exercised paths unit tests mocked.
RESULT: the run passed end-to-end (0 5xx, 0 product defects) but surfaced (a) a genuine 422 →
graceful "one last detail" setup card when the PreparationContext lacked industry/career-level
(correct fail-safe, not a crash), and (b) the citation-coverage caveat below.
LESSON: a single real end-to-end run finds integration gaps a thousand mocked tests miss.

## 5. Post-release UI audit (the most valuable finding)

PROBLEM: after declaring a submission freeze, a manual walkthrough found Progress empty,
History unopenable, Sources unlinked, and Review/Evaluation blank.
DECISION: treat "looks shipped" as unproven; trace each surface frontend→API→service→store.
RESULT: none were data/security defects — they were **wiring/projection** gaps (e.g. the
`/knowledge/sources` DTO dropped the manifest `source_url`; the History detail endpoint was
orphaned; `dashboard_metrics` had no API). All fixed with tests; then this closure phase
finished the last two (RAG page, Evaluation wiring) and added a capability toggle + Help.
LESSON: "endpoint exists" and "page renders" are not "feature delivered." Add a deterministic
return-journey e2e that clicks the *whole* product, not just the happy authoring path.

## 6. StrictMode defect

PROBLEM: React 18 StrictMode double-invokes effects; an interview session effect fired twice,
risking a duplicated first question / lost mount.
DECISION: a mounted-ref guard + idempotent session creation (`Idempotency-Key`), not disabling
StrictMode. RESULT: Q1 appears once, without reload, verified live and by a regression test.
LESSON: make client effects idempotent; never "fix" StrictMode by turning it off.

## 7. Stale schema / provenance defect

PROBLEM: an early RAGAS baseline was stamped from a dirty tree; and a reviewed report's own
commit was nearly cited as "the code it evaluated." DECISION: a two-commit provenance rule —
validate on a clean SHA, then commit the artifact separately, recording `git_dirty=false`.
RESULT: reproducible baselines with honest provenance. LESSON: an artifact must never claim its
own commit as the tested code.

## 8. Strategy token-budget issue

PROBLEM: interview strategy generation could exceed a comfortable token budget on long JDs.
DECISION: bound inputs (length caps) and keep gap analysis + planning deterministic (no model),
reserving model calls for JD analysis, questions, evaluation and the report.
RESULT: predictable cost; the live golden ran ~14 provider calls / ~32k tokens for a full path.
LESSON: spend model tokens only where judgement is required; make the rest deterministic.

## 9. Citation-resolution issue

PROBLEM: in the live golden, an explicit "show me the evidence" request for a
software-engineering role returned **insufficient evidence** — the KB lacks citable records for
that role family. DECISION: the grounding guard **refused to fabricate** a citation. RESULT: no
made-up sources (the safety property that matters); deterministic citation-completeness stays
1.0 for supported evidence. LESSON: "no citation" is the correct output when evidence is thin —
coverage is a data problem, not a prompting problem.

## 10. Tool-choice ~0.59–0.64 limitation

PROBLEM: the live-model harness shows tool-selection accuracy ~0.59–0.64; the model sometimes
answers correctly *without* the expected discrete tool call. DECISION: do **not** prompt-tune or
force a rigid tool sequence for the benchmark. RESULT: honest, un-gamed behaviour; the scripted
suite validates the graph/tool contract, not live model discipline. LESSON: separate contract
tests from model-behaviour measurement; don't optimise a number at the cost of naturalness.

## 11. RAG coverage limitation

PROBLEM: evidence coverage 0.886 and RAGAS ID precision/recall 0.676/0.516 — mid-range.
DECISION: report them plainly (now visible read-only on the Knowledge & RAG page) and document
the gaps (German occupation-specific compensation, credential fixtures-only, some routing sends
role phrasings to the vector lane). RESULT: a truthful quality picture. LESSON: surface your
weak metrics in-product; a reviewer trusts a system that shows its own gaps.

## 12. Failed prompt-hardening experiment (reverted)

PROBLEM: an attempt to harden the agent prompt for stricter tool-first behaviour was trialled.
DECISION/RESULT: it did not improve measured outcomes and risked over-constraining valid answers,
so it was **reverted** (see `tests/test_prompt_comparison.py`). LESSON: treat prompt changes as
experiments with a measured before/after; revert when the evidence doesn't support them.

## 13. Why single-agent, not multi-agent

PROBLEM: the sprint teaches multi-agent workflows. DECISION: one coherent
candidate-preparation objective did not justify multiple autonomous agents coordinating;
specialised behaviour is deterministic/bounded **tools** instead. RESULT: simpler reasoning,
fewer failure modes, one auditable allowlist. LESSON: multi-agent is a cost (coordination,
non-determinism); adopt it only when the problem is genuinely multi-objective.

## 14. Why Interview Practice stayed deterministic

PROBLEM: could Practice be agent-driven? DECISION: no — predictable state transitions
(question → answer → evaluation → deep dive → report) are safer and more testable than agent
autonomy over a candidate's scored session. RESULT: durable, resumable, idempotent Practice.
LESSON: don't put an agent where a state machine is more appropriate.

## 15. Why autonomous self-modification was rejected

PROBLEM: a feedback loop *could* auto-tune prompts/tools. DECISION: never — feedback →
analysis → recommendation → **human review** → explicit engineer experiment. RESULT: an offline,
non-self-modifying Feedback Intelligence with no git/network/prompt write capability (asserted by
an architectural test). LESSON: keep a human in the loop between signal and system change.

## 16. Why human-reviewed Feedback Intelligence

Same rationale as §15, stated as a positive: it converts safe structured signals into
recommendations a human approves and an engineer implements separately. It is admin/engineering-
only, offline, 0 paid calls by default. LESSON: a "learning loop" can be valuable *and* safe if
it stops at a recommendation.

## 17. Post-release surface remediation (this closure)

Delivered: Progress metrics, History detail, safe Sources links, Evaluation wiring (prior
branch); then the **Knowledge & RAG diagnostics page** (replacing a placeholder), a **Help**
guide, and a **server-enforced current-market-research capability toggle** (#16). One documented
non-fix: no per-user Agent-run browser (would need a new persistence subsystem) — the Inspector
opens from a run link or a pasted id (P3).

## 18. Lessons for the Capstone

1. Ship a **return-journey e2e** from day one — click the whole product, not the happy path.
2. Keep **provenance discipline** (clean-SHA validation, two-commit artifacts).
3. Measure model behaviour separately from contract tests; never game a benchmark.
4. Surface **weak metrics and known gaps in-product** — trust follows honesty.
5. Prefer **deterministic tools + one bounded agent**; add multi-agent only for genuinely
   multi-objective problems.
6. Keep humans between **feedback and self-change**.
