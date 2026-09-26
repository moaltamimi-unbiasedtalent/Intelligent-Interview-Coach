# Pilot Lessons — template

_Each lesson is traceable: observation → evidence → interpretation → decision → action →
regression. Fill in only from real participant evidence. Distinguish **participant findings**
from **internal/developer observations** (AC-24 requires this separation)._

## Lesson format (repeat per lesson)
```
Lesson ID:        L-01
Observation:      <what was seen, factual>
Evidence:         <participant IDs + task refs, e.g. P01/T4, P03/T4; issue PI-002>
Source:           PARTICIPANT | INTERNAL   (keep these separate)
Interpretation:   <what it means>
Decision:         FIX | DEFER | NO CHANGE
Reason:           <frequency, severity, strategy fit, risk, preference?>
Action:           <if FIX: what changed, smallest root cause>
Regression:       <if fixed: test(s) added/extended + eval/gate rerun + new RC id>
Status:           OPEN | ACTIONED | DEFERRED
```

## Summary tables (fill after synthesis)
### Participant-sourced lessons
| ID | Observation | Evidence | Decision | Action | RC |
|---|---|---|---|---|---|

### Internal/developer observations (kept separate from participant findings)
| ID | Observation | Decision | Action |
|---|---|---|---|

## Unresolved / disclosed
List issues **not** fixed for this candidate and why (AC-24 requires disclosing unresolved
issues). Carry into the quality register.

## AC-24 completion checklist (verify before claiming PASS in P10B)
- [ ] ≥ 3 actual human participants observed
- [ ] sessions used an identified RC
- [ ] observations recorded (anonymized)
- [ ] participant findings distinguished from internal observations
- [ ] lessons synthesized
- [ ] consequential fixes regression-tested (new RC if runtime changed)
- [ ] unresolved issues disclosed
- [ ] no fabricated / LLM-generated participant responses used
