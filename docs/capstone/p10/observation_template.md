# Per-Task Observation Template

_Copy one block per task, per participant, into the participant's `sessions/PXX.md`. Record only
what actually happened — no fabrication. Paraphrase comments; never store identifiable text._

```
participant_id:        P0X
release_candidate:     RC-P9-001
task_id:               T1..T9
completion:            COMPLETED_UNASSISTED | COMPLETED_WITH_HINT | COMPLETED_WITH_HELP | NOT_COMPLETED | NOT_RUN
moderator_help_level:  L0 | L1 | L2 | L3 | L4
duration_rough:        e.g. ~2 min (optional)
observed_confusion:    <what confused them, where they paused / looked>
participant_comment:   <paraphrase — no PII, no verbatim personal data>
expected_but_missing:  <what they expected to happen that didn't>
flags:
  defect_suspected:               yes | no
  usability_issue:                yes | no
  trust_comprehension_issue:      yes | no
  accessibility_issue:            yes | no
  environment_provider_limit:     yes | no
issue_ids:             <link to issue_log IDs if any, e.g. PI-003>
notes:                 <anything else observable>
```

Guidance:
- If Mo/LLM output is unavailable because no provider key is configured, set
  `environment_provider_limit: yes` and judge the surrounding UX, not the missing answer.
- `moderator_help_level` is the **highest** level used to unblock that task.
- A preference is not a defect — use `usability_issue` and the U1–U4 scale in the issue log.
