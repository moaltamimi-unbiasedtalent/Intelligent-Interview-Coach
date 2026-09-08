# Sprint 4 — Demo Script (5–8 minutes)

A guided walkthrough of the Intelligent Interview Coach. Assumes the Next.js frontend
and FastAPI backend are running with `AGENT_COACH_ENABLED=true` and an
`OPENROUTER_API_KEY` set (see README quick start).

> Ports: use free ports if :3000 is occupied (e.g. frontend on :3200, backend on
> :8000). The frontend's API base defaults to `http://localhost:8000/api/v1`.

## Main path

1. **Open the Agent Coach** — go to `/prepare`. The heading "Your interview coach"
   confirms the LangGraph-backed coach is active.
2. **Ask for preparation** — e.g. *"I have a Senior Product Manager interview at a
   fintech next week — help me prepare for the behavioral and product-sense rounds."*
   Click **Start preparing**.
3. **Show a Career tool** — ask a follow-up that needs analysis, e.g. paste a short JD
   or *"generate practice questions for this role"* — the coach calls a controlled
   Career tool (`AnalyzeJobDescription` / `GenerateInterviewQuestions`).
4. **Show retrieval + citations** — ask a knowledge question, e.g. *"What's the typical
   salary range and expectations for this role?"* — the coach calls
   `SearchCareerKnowledge`; point out the evidence/citations surfaced.
5. **HITL (role/memory)** — if an ambiguous role or a memory proposal arises, an
   approval card appears; approve/select it. *(Fallback if none occurs naturally: open
   the Agent Inspector and show a prior run's `human_input_required` / `_resumed`
   events, and explain the interrupt/resume mechanism.)*
6. **Continue the same thread** — send another message; note the conversation continues
   on the same run (multi-turn).
7. **Open the Agent Inspector** — click **View run details**.
8. **Point out the safe trace** — tools used, retrieval, sources, memory use,
   approvals, timing, safe tool-failure categories. Emphasise: **no chain-of-thought,
   no prompts, no raw checkpoint** are shown.
9. **Approve the Practice handoff** — approve moving into Interview Practice (or start
   Practice directly).
10. **Answer one Interview question** — type an answer and submit.
11. **Show the evaluation** — structured feedback (score, what worked, what to improve,
    stronger structure). Note "practice feedback only — not a hiring decision".
12. **Deep Dive** — click **Go deeper**, answer the follow-up, see branch feedback;
    note the main question counter does not change.
13. **Final report** — return to the interview, finish/complete, **Generate
    performance review** — show the readiness score and sections.
14. **Durability (optional, strong)** — refresh the page mid-interview (or point out a
    restart): the same question/state is restored from the durable session store.

## Standalone fallback demo (no coach handoff)

Go to `/practice` with no session → the standalone setup form. Enter target role,
industry, career level → **Start interview** → answer → feedback. This shows Interview
Practice works without the Agent Coach.

## Deterministic Career fallback

Set `AGENT_COACH_ENABLED=false` and reload `/prepare` — the deterministic Career flow
renders instead of the agent. Useful to contrast Sprint 3's deterministic pipeline with
Sprint 4's agentic wrapper.

## If no key is configured

The UI still loads; agent runs and LLM-backed steps return a safe "not configured"
message. Use `python scripts/eval_agent.py` to demonstrate the deterministic
orchestration evaluation with no provider calls.
