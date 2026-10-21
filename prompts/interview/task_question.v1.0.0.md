---
id: interview.task_question
family: interview/task_question
version: 1.0.0
variables: []
compatible_with: [interview.prompts]
description: Question task instruction
status: approved
sha256: cb6c4da186eb587e23603d9c9c0e92e85a0caa047a94ec2ac96ac8ddd4406350
---
TASK
Generate the single next interview question. Adapt to the profession, seniority and selected interview type(s), and to the job description when present. Do not repeat any previous question listed in the reference data. Never assume experience the candidate has not stated.
Set 'question_type' to one of the interview type(s) listed in SESSION PARAMETERS, written in lowercase with underscores (e.g. behavioural, technical, case_study). Set 'difficulty' to exactly one of: easy, moderate, hard.