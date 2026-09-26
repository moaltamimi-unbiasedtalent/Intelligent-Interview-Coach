# Pilot Issue Log (template)

_One row per distinct issue observed across sessions. A participant suggestion is **evidence,
not a command** — record it, decide deliberately (§ Fix decision), and only then act._

| Field | Value |
|---|---|
| Pilot issue ID | PI-001 |
| Participant(s) | e.g. P01, P03 |
| Surface | e.g. Prepare / Documents / Practice / Trust / Voice |
| Observation | what happened (factual, anonymized) |
| Type | DEFECT / USABILITY / CONTENT / TRUST / ACCESSIBILITY / ENVIRONMENT / OTHER |
| Impact | P0–P3 (defect) or U1–U4 (usability) |
| Reproducible? | yes / no / unknown |
| Frequency | e.g. 3/5 participants |
| Proposed action | short description |
| Decision | FIX / DEFER / NO CHANGE / NEEDS MORE EVIDENCE |
| Reason | why (frequency, severity, strategy fit, risk, preference?) |
| Regression needed? | yes / no |
| New RC required? | yes / no (material runtime change → new RC) |
| Status | OPEN / IN PROGRESS / FIXED / DEFERRED / CLOSED |

## Severity / impact reference
- **Defects:** P0 security/data-loss/blocker · P1 major core-flow · P2 material w/ workaround · P3 minor.
- **Usability (non-defect):** U1 prevents completion / severe misunderstanding · U2 meaningful
  friction or repeated help · U3 noticeable but proceeds · U4 preference/polish.

## Fix decision (evaluate before acting)
frequency · severity · task impact · strategy fit · security/privacy impact · accessibility
impact · complexity/risk · is it just a personal preference? → record the decision + reason.

## Consequential-fix rule (AC-24)
For every **P0/P1/P2** fix from pilot evidence: reproduce → smallest root-cause fix →
add/extend regression coverage → run affected eval(s) + release gate → record under a **new RC**
(never attach RC-P9-001 proof to changed runtime code).

## Rows
_(none yet — populated during the real pilot / P10B)_
