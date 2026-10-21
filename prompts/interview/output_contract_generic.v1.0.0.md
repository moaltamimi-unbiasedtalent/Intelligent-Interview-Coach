---
id: interview.output_contract_generic
family: interview/output_contract_generic
version: 1.0.0
variables: [schema_name, schema_description]
compatible_with: [interview.prompts]
description: Strict-JSON output contract for any task schema
status: approved
sha256: f0d7ebec9b0ebbd8cbc070018236b2f2d7481db0a12d0f97ea531257c3b30aa5
---
OUTPUT CONTRACT
Return exactly one JSON object that conforms strictly to the {schema_name} schema and nothing else — no markdown, no code fences, no commentary before or after. Use these exact keys:
{schema_description}
Formatting rules: use only the keys listed; integer fields are integers and score fields stay within their stated ranges; list fields hold short, concrete, evidence-based items; any example answer must be labelled as an example the candidate must personalise, and you must not invent achievements, metrics or experience.