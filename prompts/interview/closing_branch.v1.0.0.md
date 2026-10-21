---
id: interview.closing_branch
family: interview/closing_branch
version: 1.0.0
variables: [branch_depth, branch_mode]
compatible_with: [interview.prompts]
description: Deep-dive closing instruction
status: approved
sha256: 385d34f1f2ef3372ab4c11c8737a56d1f777c8988eb1e0624cf790c971d43516
---
Using only the reference data above, return the required JSON for a single level-{branch_depth} deep-dive question in the '{branch_mode}' style. Build on the candidate_answer to the interview_question; do not repeat any previous_question.