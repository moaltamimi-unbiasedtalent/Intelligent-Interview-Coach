---
id: interview.method_rubric_json
family: interview/method_rubric_json
version: 1.0.0
variables: []
compatible_with: [interview.prompts]
description: Rubric-constrained JSON evaluation method block
status: approved
sha256: 72610ec4fefb08e9e13f17d4302e8e22d6f3ef07ecd21064e00680138b1db8fc
---
METHOD — Rubric-constrained structured output
Score strictly against this rubric, where 1 is very weak and 10 is excellent for the target role and difficulty:
- relevance: how directly the answer addresses the question.
- structure: how clearly the answer is organised.
- evidence: use of concrete, verifiable examples and detail.
- role_knowledge: demonstrated understanding relevant to the role.
- problem_solving: quality of reasoning and approach.
- communication: clarity and delivery.
- credibility: internal consistency and believability.
Then set overall_score (0-100) consistent with the criterion scores. Adherence to the JSON schema is mandatory: emit only the JSON object, with exactly the required keys and valid value types.