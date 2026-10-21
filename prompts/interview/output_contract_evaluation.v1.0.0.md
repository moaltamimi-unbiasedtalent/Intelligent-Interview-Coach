---
id: interview.output_contract_evaluation
family: interview/output_contract_evaluation
version: 1.0.0
variables: [schema_name, schema_description]
compatible_with: [interview.prompts]
description: Strict-JSON output contract for the evaluation schema
status: approved
sha256: 367712a6fb72ace661d0075f754517c4a83cd6e496e949485e0865f01f61679e
---
OUTPUT CONTRACT
Return exactly one JSON object that conforms strictly to the {schema_name} schema and nothing else — no markdown, no code fences, no commentary before or after. Use these exact keys:
{schema_description}
Formatting rules: scores are integers; overall_score is 0-100; the seven criterion scores (relevance, structure, evidence, role_knowledge, problem_solving, communication, credibility) are each 1-10; list fields hold short, concrete, evidence-based points; stronger_answer_structure and improved_example_answer are plain text; improved_example_answer must be an illustrative example the candidate must personalise and must not invent achievements or metrics.