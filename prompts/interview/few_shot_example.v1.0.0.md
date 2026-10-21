---
id: interview.few_shot_example
family: interview/few_shot_example
version: 1.0.0
variables: []
compatible_with: [interview.prompts]
description: Profession-neutral worked example (literal braces escaped)
status: approved
sha256: 965dcff004fd2c2516243e776619ecb9abf6ff2d411fb4289631c605b16b75de
---
WORKED EXAMPLE (profession-neutral, for pattern only)
Example question: Tell me about a time you improved a process.

Weak answer:
I'm a hard worker and I always do my best. I improved things at my last job and everyone was happy with the results.

Structured evaluation of the weak answer:
{{
  "overall_score": 38,
  "relevance": 5,
  "structure": 4,
  "evidence": 3,
  "role_knowledge": 5,
  "problem_solving": 4,
  "communication": 5,
  "credibility": 4,
  "strengths": [
    "Shows a positive, willing attitude"
  ],
  "improvement_areas": [
    "Describe one specific situation",
    "Explain the concrete actions you personally took",
    "Show the measurable outcome"
  ],
  "missing_evidence": [
    "No specific example or context",
    "No description of the candidate's own contribution",
    "No measurable result"
  ],
  "stronger_answer_structure": "Situation, Task, Action, Result: set the context, your specific responsibility, the actions you personally took, and the measurable outcome.",
  "improved_example_answer": "Example \u2014 personalise with your own real details: In my previous role our intake process caused repeated delays. I mapped each step, removed two redundant approvals, and introduced a shared checklist. Over the following quarter average turnaround fell noticeably and rework dropped.",
  "follow_up_question": "What was the biggest obstacle you faced, and how did you handle it?"
}}

Improved answer (an example, not the candidate's real experience):
Example answer to personalise: 'In my last role our intake process caused delays. I was asked to reduce turnaround. I mapped the steps, removed two redundant approvals and added a shared checklist. Average turnaround then dropped and rework fell.' Replace every detail with your own real experience.