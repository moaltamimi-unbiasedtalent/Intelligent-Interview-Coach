# P2 + E2 — Account Return Journey + Response Experience Quality

Capstone implementation story. Two tightly-related product-quality objectives, built
on the P1 identity foundation **without** weakening the agent, retrieval, citations,
HITL, tool selection, security or deterministic domain logic.

Base: `main` @ `a8e4697` (P1/E1 merged, PR #74). Branch:
`feature/capstone-p2-e2-return-response-ux`. No historical tag moved.

---

## WHAT problem was solved
1. **Return journey** — a returning authenticated user arrived at a cold home screen as
   if they'd never used Ask4Mo. P2 surfaces, from real persisted data only, what they
   were doing and how to continue (resume Practice, latest report, Progress, History,
   saved Memory).
2. **Response experience (reviewer feedback)** — Mo's answers were long and hard to
   scan. P2 adds an information hierarchy (answer-first, one next step, details/sources
   behind progressive disclosure) and a persisted **Brief/Detailed** preference.

## WHY the return journey mattered
Identity (P1) makes activity durable and owner-scoped; without a return surface that
value is invisible. The active-sessions backbone already existed end-to-end
(`GET /interviews` → `DurableInterviewSessionStore.list_active`) but had **no UI
consumer** — so P2 is mostly wiring real data into a focused continuation card, not a
new persistence system.

## WHY reviewer feedback mattered
It is concrete, external, usability feedback — exactly the iterative-engineering signal
the Capstone should show. It is an information-hierarchy problem, not an intelligence
problem, so the fix belongs in presentation, not in the agent.

## WHY Brief/Detailed is separate from the model profile
Three orthogonal concerns are kept distinct:
* **Fast / Balanced / Advanced** — model/capability profile (cost/quality of reasoning).
* **Brief / Detailed** — presentation depth (how much of the full answer shows first).
* **Personality/tone** — a future, separate concern (explicitly NOT built here).

Brief/Detailed never changes what the agent computes, which tools it picks, or the
evidence it returns; it only changes how the (full) answer is laid out.

## HOW progressive disclosure works
The backend adds a **deterministic, pure** presentation contract to the agent response
(`src/agent/presentation.py` → `AgentRunResponse.presentation`):
`{answer, details, has_details, next_step}`.
* `answer` = the lead block of the full grounded answer; `details` = the remainder —
  a **semantic split at the first paragraph boundary**, never a character/token cut.
  `answer + details` always reconstructs the full text (no truncation, ever).
* `next_step` is derived **only** from real structured state (a gathered preparation
  context → "Start interview practice"); it is never fabricated and is suppressed while
  a run awaits a human decision.
The frontend (`AgentAnswer` + accessible `Disclosure`) renders ANSWER + NEXT STEP
always; in Brief mode DETAILS sit behind "Show more"; in Detailed mode they show
inline. Sources keep their own always-present expandable list, so evidence is
discoverable in both modes. Only the **current** answer uses disclosure; prior turns
render in full.

## HOW active Practice discovery works
`GET /api/v1/interviews` (existing) returns owner-scoped safe summaries
(`session_id`, role, state, progress, `updated_at`) with completed sessions excluded
and no answer/JD content. The new `ReturnJourney` Home component consumes it (plus
History/Progress/Memory) and links to `/practice?session=<id>` to resume. No change to
the Practice state machine.

## HOW authenticated continuity works
History, Progress and Memory were already `user_id`-scoped through the application/repo
layers; P1 made `user_id` come from a trusted session. P2 re-verified each survives
logout/login and stays owner-scoped (tests below), and wired them into the return
surface. No persistence was duplicated or added for continuity.

## HOW Mo's Agent behaviour was preserved
The presentation contract is computed **after** the agent's grounded result, in the
route mapping — it reads the final text and safe structured fields and makes **no**
model/provider call. Tool descriptions, the ReAct loop, retrieval routing, citations,
HITL and the output guard are untouched. The deterministic agent gate
(`scripts/eval_agent.py`) still passes unchanged.

## HOW prompt-tuning risk was avoided
The earlier, reverted prompt-hardening experiment is explicitly **not** repeated. P2
adds **no** verbosity field to the request, graph state or system prompt; Brief/Detailed
is purely presentation. This is the "strongest presentation-layer improvement" path the
phase brief calls for, and it carries no risk of destabilising tool selection.

## HOW response quality was evaluated
`scripts/eval_response_experience.py` (offline, no paid calls, wired into CI) checks the
contract across representative response classes (factual, JD analysis, gap analysis,
plan, questions, retrieval, current-market, unsupported-evidence, trivial) plus the
preference API. Latest run: answer_first 9/9, progressive_disclosure 9/9, no_truncation
9/9, next_step_correctness 9/9, critical_caveat_visible 1/1, source_preservation 1/1,
preference persistence + isolation 1/1 → **all invariants met**.

## WHAT changed after reviewer feedback
Answer-first layout with a single next step; details and sources behind progressive
disclosure; a server-persisted Brief/Detailed preference (default Brief) surfaced in
Settings; a returning-user Home card. No content is hidden or truncated, and critical
qualifications stay visible.

## WHAT remains intentionally deferred
Personality/tone controls; any model-side verbosity control; longitudinal trend charts
(see decision below); Admin/Teams/billing/documents/speech/marketing (later phases).

### Progress trend decision
Progress keeps only defensible persisted metrics (completed sessions, evaluated
answers, average score, focus area, recent sessions). Timestamped records exist, but a
longitudinal **trend chart** is deliberately **not** added in P2: with few data points
it would imply a trend the data cannot support. Documented as a future option to add
only with an honest minimum-sample rule — not "because it looks attractive".

## WHAT was learned
* The cheapest, safest usability win was presentation-layer: a deterministic split +
  progressive disclosure gave "shorter, scannable" answers with zero agent risk.
* A pure backend contract made the UX **testable** (not just screenshots).
* Optional context accessors (`useAuthOptional`) let shared components render in unit
  tests without a provider while the strict `useAuth` still guards auth-only surfaces.

---

## REVIEWER FEEDBACK → ENGINEERING RESPONSE

**Observation:** AI responses were too long and difficult to scan.

**Hypothesis:** Progressive disclosure and a user-controlled response depth can improve
usability without weakening Agent intelligence or hiding evidence.

**Implementation:** A deterministic, pure presentation contract (`answer` / `details` /
`next_step`) computed after the grounded result — no extra model call, no prompt change,
no truncation. An accessible "Show more" disclosure. A server-persisted, per-account
Brief/Detailed preference (default Brief), available to every tier, distinct from the
model profile. Sources remain in an always-present expandable list.

**Evaluation:** `scripts/eval_response_experience.py` — answer-first, progressive
disclosure availability, no-truncation, next-step correctness, critical-caveat
visibility, source preservation, and preference persistence/isolation all pass (rates
1.0). The deterministic agent gate and retrieval gates are unchanged. Frontend unit +
Playwright e2e cover the disclosure and preference UX.

**Outcome:** Answers lead with the key point and one next step; supporting detail and
sources are one interaction away; users can set Brief or Detailed and it persists across
sign-outs and devices. Agent behaviour, evidence and safety are unchanged.
