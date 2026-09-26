# Pilot Presentation — slide-ready template (§36)

_Structure for the capstone slides. **Do not populate participant results until the real pilot
is conducted.** Placeholders below stay empty until P10B._

## Flow
```
3–5 real participants
        ↓
same release candidate (RC-P9-001, 319759d)
        ↓
task-based moderated pilot (T1–T9)
        ↓
observations (anonymized)
        ↓
issues (defect P0–P3 / usability U1–U4)
        ↓
engineering decisions (FIX / DEFER / NO CHANGE)
        ↓
regression-tested repairs (new RC if runtime changed)
        ↓
lessons
```

## Slide placeholders (fill in P10B)
1. **Method** — n=__ participants; environment; RC-P9-001; qualitative, not statistical.
2. **What we tested** — T1–T9 candidate journey (not admin/reviewer surfaces).
3. **What worked** — top positive evidence (__/N).
4. **Where people struggled** — top U1/U2 findings (__/N) + task refs.
5. **Trust / AI comprehension** — did people know AI vs sources, Memory, workspace privacy?
6. **Defects found** — P0/P1/P2 with issue IDs (or "none").
7. **Decisions** — what we fixed / deferred / left unchanged, and why.
8. **Regression** — tests added + gates rerun + RC id for each fix.
9. **Lessons** — 3–5 traceable lessons (observation → decision → action).
10. **Honest limits** — unresolved issues; live-provider portions NOT RUN; EX-12 still BLOCKED.

## Rules
- Report counts ("3/5 …"), never population percentages or significance.
- Show negatives honestly; do not overclaim.
- No fabricated or LLM-generated participant quotes.
