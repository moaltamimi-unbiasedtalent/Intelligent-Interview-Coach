# Ask4Mo Capstone — Definition of Done & Phase-Report Template

Reusable standard for every Capstone implementation phase (P1+). Code existing is **not** done.

## Definition of Done (apply where applicable)
1. Requirement implemented (matches the requirements matrix ID).
2. Backend wired (service + API).
3. Frontend wired (real data source; empty/loading/error states).
4. Persistence wired (migration if needed; single Alembic head).
5. Authorization verified (ownership + role + entitlement + flag; server-side).
6. Privacy impact addressed (inventory updated; export/delete where relevant).
7. Empty / loading / error states present.
8. Tests added (unit + e2e as applicable).
9. Existing regression suite green (pytest, frontend, e2e).
10. Security tests green (authz/injection/SSRF/uploads as relevant).
11. Evaluation completed (per the evaluation plan; paid runs only if authorized).
12. Documentation updated (architecture/requirements/reviewer).
13. Reviewer evidence updated (current evidence index, honest modes).
14. Implementation story recorded (see presentation standard).
15. Presentation evidence recorded.
16. Known limitations documented.
17. Git clean; only intended files changed.
18. Branch pushed.
19. No automatic merge.
20. Explicit human review before merge.

## Non-negotiables carried from Sprint 4
Private-by-default; server-side enforcement; no fabricated citations/data/compliance; no CoT/prompt/
secret exposure; deterministic Practice authority; HITL for side effects; no autonomous self-
modification; paid/live calls only with explicit authorization; preserve historical tags.

## Phase-report template (paste at end of each phase)
```
ASK4MO — CAPSTONE <PHASE> REPORT
Baseline: branch, base SHA, git status, tags unchanged (Y/N)
Objective: <one line>
Scope delivered: <IDs>   Scope deferred/blocked: <IDs + reason>
Changes: <files/subsystems>
Backend / Frontend / Persistence / Authorization / Privacy: <status each>
States (empty/loading/error): <status>
Tests: pytest <n>/<skip>; frontend <n>; e2e <n>; new tests: <list>
Security tests: <status>
Evaluation: <metric = result, det/judge, paid? auth?>
Regression: <PASS/FAIL, deltas explained>
Quality gates: ruff / typecheck / build / OpenAPI contract / secret scan
Paid LLM: 0 (or authorized detail)  Live provider: 0 (or authorized detail)
Docs updated: <files>   Implementation story: <link>
Known limitations: <list>
Defects (P0/P1/P2/P3): <counts + detail>
Commit(s): <sha>   Pushed: Y   Merged: N
DoD checklist: <which of 1–20 met / not-applicable / outstanding>
STOP condition met: <Y>   Next phase preconditions: <list>
VERDICT: PASS / PARTIAL / BLOCKED
```
