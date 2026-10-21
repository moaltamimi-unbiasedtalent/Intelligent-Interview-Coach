---
id: interview.technique_directives
family: interview/technique_directives
version: 1.0.0
variables: []
compatible_with: [interview.prompts]
description: Task-agnostic one-line approach per technique (table asset)
status: approved
sha256: c818c99e2598e8c59953e40e37356e5fb3fb00c75aa5918d786e43896535d511
---
zero_shot: Work directly from the instructions and reference data, without worked examples.
role_persona: Adopt the perspective of an experienced interviewer for the target role and sector while carrying out the task.
few_shot: Follow the structure and standard implied by well-formed professional examples, without copying any specific example's content.
structured_procedure: Work through the task methodically before producing the output; report only the final result, never your private reasoning.
rubric_json: Adhere strictly to the required JSON schema and to the stated criteria.