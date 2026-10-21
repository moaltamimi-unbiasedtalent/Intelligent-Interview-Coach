---
id: interview.session_parameters
family: interview/session_parameters
version: 1.0.0
variables: [career_level, interview_types, interviewer_persona, persona_tone, difficulty, rigour, response_detail, length, number_of_questions]
compatible_with: [interview.prompts]
description: Trusted dropdown-sourced session parameters block
status: approved
sha256: 96b937214a0c44c9737c3fa6ff103d3d2720b9f08add46c48eb61c88598b54d1
---
SESSION PARAMETERS (trusted, chosen from fixed options):
- Career level: {career_level}
- Interview type(s) to focus on: {interview_types}
- Interviewer persona: {interviewer_persona} — adopt a tone that is {persona_tone}.
- Difficulty: {difficulty} — {rigour}
- Feedback detail: {response_detail} — {length}
- Planned number of questions this session: {number_of_questions}
The target role, sector, company context, job description and candidate background appear in the untrusted reference data in the user message. Adapt your questioning and evaluation to them.