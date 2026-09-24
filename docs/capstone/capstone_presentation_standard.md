# Ask4Mo Capstone — Presentation & Reporting Standard

Reusable across Sprints and the Capstone. Every deliverable explains **what, how and why** — not just
that it shipped. Evidence over claims; honest about limitations; no fabricated readiness.

## Per-deliverable capture (the "deliverable story")
- Requirement (matrix ID)
- Status (DELIVERED / PARTIAL / ABSENT / UNVALIDATED / BLOCKED / OUT_OF_SCOPE)
- Problem / why it matters
- What was implemented
- Why this architecture was chosen
- How it works (data/control flow)
- Key technologies
- Agent-vs-deterministic boundary
- Security / privacy consideration
- Evaluation / test evidence (with mode: mock/local/CI/live/human)
- Result / metric (with sample size)
- Limitation
- Engineering decision / what I learned

## Standard requirement table (presentations)
| # | Requirement | Status | How implemented | Evidence |
|---|---|---|---|---|

## Standard optional-task table
| # | Optional task | Status | How implemented | Evidence / limitation |

## Reusable presentation sections
1. Problem  2. Requirements  3. Architecture  4. User journey  5. Agent design
6. RAG / knowledge  7. Key implementation decisions  8. Security/privacy  9. Evaluation
10. What worked  11. What did not work / root causes  12. Remediation  13. Demo
14. Limitations  15. Lessons learned  16. Next steps

## Evidence-integrity rules
- Label every metric with code SHA/date/environment/mode/sample size.
- Keep historical evidence as historical; add a single current evidence index rather than overwriting.
- Distinguish deterministic results from model-judged; note paid/live vs free/mocked.
- Never present model inference as verified candidate fact; never present a plan as an implementation.
- Preserve the original golden record + tag; new code needs new evidence.
