"""System-prompt library: five prompt-engineering techniques.

Every technique produces a *system* prompt for the same task — evaluating a
candidate's answer to an interview question and returning a single
``AnswerEvaluation`` JSON object. Keeping the task and the output schema
constant across all five techniques is deliberate: it is what makes the
prompt-comparison experiment fair (only the technique changes, never the job).

Message separation and trust boundaries
---------------------------------------
* The **system** message carries only trusted, repository-authored
  instructions plus the session parameters that come from fixed dropdown
  vocabularies (career level, interview types, persona, difficulty, response
  detail, number of questions). These are safe to embed because they cannot
  contain free-form injected instructions.
* The **user** message carries every piece of free text the candidate typed
  (target role, sector, company context, job description, background, the
  interview question and the answer). It is wrapped in explicit delimiters and
  labelled as untrusted reference data.

The shared guardrails instruct the model to treat that reference data as data
only, never to follow instructions embedded inside it, never to reveal the
system prompt or any hidden reasoning, and never to fabricate candidate
achievements. Improved example answers are always labelled as examples that
require personalisation.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

from pydantic import BaseModel

from src.locales import LANGUAGE_NAMES
from src.prompt_assets import render, table

from src.models import (
    AnswerEvaluation,
    BranchQuestion,
    FinalInterviewReport,
    InterviewConfiguration,
    InterviewQuestion,
    InterviewStrategy,
)

__all__ = [
    "ANSWER_EVALUATION_KEYS",
    "TARGET_SCHEMA_NAME",
    "SYSTEM_PROMPT_BUILDERS",
    "build_system_prompt",
    "build_user_message",
    "build_messages",
    # Task-aware API (Phase 6)
    "TASK_STRATEGY",
    "TASK_QUESTION",
    "TASK_EVALUATION",
    "TASK_REPORT",
    "TASK_BRANCH",
    "TASK_SCHEMAS",
    "build_task_system_prompt",
    "build_task_user_message",
    "build_task_messages",
]

# The schema every technique targets. Exposed so the registry, the tests and
# the documentation all agree on which structured output is produced.
TARGET_SCHEMA_NAME = AnswerEvaluation.__name__
ANSWER_EVALUATION_KEYS: tuple[str, ...] = tuple(AnswerEvaluation.model_fields)


# --- Reference-data delimiters ----------------------------------------------
# Distinctive markers make it easy for the model (and the reader) to see where
# untrusted content starts and stops.

_REF_OPEN = "<<<UNTRUSTED_REFERENCE_DATA>>>"
_REF_CLOSE = "<<<END_UNTRUSTED_REFERENCE_DATA>>>"


# --- Shared prompt building blocks ------------------------------------------

# Every prompt text below is a versioned, integrity-checked asset under prompts/interview/ (package
# 01B). Code keeps only the assembly (order, conditionals, allow-lists) and the trusted values
# substituted into declared placeholders; each render is byte-equal to the former f-string output.
_CONSUMER = "interview.prompts"

_MISSION = render("interview/mission", _CONSUMER)

# Numbered so the rules are easy to cite in a review, and so tests can assert
# specific guardrails are present.
_GUARDRAILS = render("interview/guardrails", _CONSUMER, ref_open=_REF_OPEN, ref_close=_REF_CLOSE)

# Per-value guidance that lets a single system prompt adapt to the chosen
# session parameters. Keys are the fixed vocabularies from src.constants.
_PERSONA_TONE = table("interview/persona_tone", _CONSUMER)
_DIFFICULTY_RIGOUR = table("interview/difficulty_rigour", _CONSUMER)
_RESPONSE_DETAIL_LENGTH = table("interview/response_detail_length", _CONSUMER)


def _schema_description() -> str:
    """Render the target schema from the model so prompts stay in sync.

    Listing every field name means each technique's system prompt literally
    references the correct schema keys.
    """
    lines = []
    for name, field in AnswerEvaluation.model_fields.items():
        description = field.description or ""
        lines.append(f"  - {name}: {description}")
    return "\n".join(lines)


def _output_contract() -> str:
    """The strict-JSON output contract shared by every technique."""
    return render(
        "interview/output_contract_evaluation", _CONSUMER,
        schema_name=TARGET_SCHEMA_NAME, schema_description=_schema_description(),
    )


def _session_parameters(config: InterviewConfiguration) -> str:
    """Trusted, dropdown-sourced parameters — safe to place in the system prompt."""
    interview_types = ", ".join(config.interview_types)
    persona_tone = _PERSONA_TONE.get(config.interviewer_persona, "professional")
    rigour = _DIFFICULTY_RIGOUR.get(config.difficulty, "")
    length = _RESPONSE_DETAIL_LENGTH.get(config.response_detail, "")
    return render(
        "interview/session_parameters", _CONSUMER,
        career_level=config.career_level, interview_types=interview_types,
        interviewer_persona=config.interviewer_persona, persona_tone=persona_tone,
        difficulty=config.difficulty, rigour=rigour,
        response_detail=config.response_detail, length=length,
        number_of_questions=config.number_of_questions,
    )


# Candidate conversation language (P10B Wave 4). Bounded to the 8 product locales; the
# language NAME comes only from this allow-list, never from the code string itself, so no
# untrusted text can reach the model. This mirrors the agent path's response_language_directive
# and sets ONLY the language of the generated prose — it never changes scoring, evidence,
# grounding, or the labour-market/geography of the interview content.
_CONVERSATION_LANGUAGE_NAMES: dict[str, str] = dict(LANGUAGE_NAMES)  # single copy: src/locales.py


def _coaching_directive(config: InterviewConfiguration) -> str | None:
    """Return the trusted coaching-tone directive for the config's bounded coaching_style, or None.

    Delegates to the shared allow-list mapping in `src/coaching_style.py`; the raw code never
    reaches the model. Applied by the caller ONLY to feedback/report tasks, never to scoring.
    """
    from src.coaching_style import coaching_style_directive

    return coaching_style_directive(getattr(config, "coaching_style", "") or "")


def _language_directive(config: InterviewConfiguration) -> str | None:
    """Return a trusted 'write in <language>' directive, or None for English/unknown."""
    code = getattr(config, "conversation_language", "") or ""
    name = _CONVERSATION_LANGUAGE_NAMES.get(code.strip().lower())
    if not name or name == "English":
        return None
    return render("interview/language_directive", _CONSUMER, language_name=name)


_TASK = render("interview/task_evaluation", _CONSUMER)


def _assemble(config: InterviewConfiguration, method: str) -> str:
    """Compose a full system prompt from the shared blocks plus a method block."""
    return "\n\n".join(
        [
            _MISSION,
            _GUARDRAILS,
            _session_parameters(config),
            _TASK,
            method,
            _output_contract(),
        ]
    )


# --- The five techniques -----------------------------------------------------


def _zero_shot(config: InterviewConfiguration) -> str:
    """Technique 1 — Zero-shot instruction: direct task, no examples."""
    return _assemble(config, render("interview/method_zero_shot", _CONSUMER))


def _role_persona(config: InterviewConfiguration) -> str:
    """Technique 2 — Role and persona prompting: adopt an expert interviewer."""
    method = render(
        "interview/method_role_persona", _CONSUMER,
        interviewer_persona=config.interviewer_persona,
    )
    return _assemble(config, method)


def _few_shot_example() -> str:
    """The profession-neutral worked example used by few-shot prompting (static asset)."""
    return render("interview/few_shot_example", _CONSUMER)


def _few_shot(config: InterviewConfiguration) -> str:
    """Technique 3 — Few-shot prompting: one weak answer, its evaluation, one improved answer."""
    method = render(
        "interview/method_few_shot", _CONSUMER, worked_example=_few_shot_example()
    )
    return _assemble(config, method)


def _structured_procedure(config: InterviewConfiguration) -> str:
    """Technique 4 — Structured analytical procedure: a visible six-step method."""
    return _assemble(config, render("interview/method_structured_procedure", _CONSUMER))


def _rubric_json(config: InterviewConfiguration) -> str:
    """Technique 5 — Rubric-constrained structured-output prompting."""
    return _assemble(config, render("interview/method_rubric_json", _CONSUMER))


# Stable mapping from technique ID (src.constants.PROMPT_TECHNIQUES) to builder.
SYSTEM_PROMPT_BUILDERS: dict[str, Callable[[InterviewConfiguration], str]] = {
    "zero_shot": _zero_shot,
    "role_persona": _role_persona,
    "few_shot": _few_shot,
    "structured_procedure": _structured_procedure,
    "rubric_json": _rubric_json,
}


def build_system_prompt(
    technique_id: str, config: InterviewConfiguration
) -> str:
    """Return the system prompt for ``technique_id`` adapted to ``config``.

    Raises ``ValueError`` for any unsupported technique ID (fails safely
    instead of silently picking a default).
    """
    builder = SYSTEM_PROMPT_BUILDERS.get(technique_id)
    if builder is None:
        raise ValueError(
            f"Unknown prompt technique {technique_id!r}; "
            f"supported IDs are {list(SYSTEM_PROMPT_BUILDERS)}"
        )
    return builder(config)


def _reference_block(label: str, value: str) -> str:
    """Render one labelled section of untrusted reference data, if present."""
    value = value.strip()
    if not value:
        return ""
    return f"[{label}]\n{value}"


def build_user_message(
    config: InterviewConfiguration,
    question: str | None = None,
    candidate_answer: str | None = None,
) -> str:
    """Assemble the user message: all free-text content as untrusted data.

    Every candidate-supplied string lives here, inside the reference-data
    delimiters — never in the system prompt.
    """
    sections = [
        _reference_block("target_role", config.target_role),
        _reference_block("industry_or_sector", config.industry_or_sector),
        _reference_block("company_context", config.company_context),
        _reference_block("job_description", config.job_description),
        _reference_block("candidate_background", config.candidate_background),
    ]
    if question is not None:
        sections.append(_reference_block("interview_question", question))
    if candidate_answer is not None:
        sections.append(_reference_block("candidate_answer", candidate_answer))

    body = "\n\n".join(section for section in sections if section)
    return render(
        "interview/user_frame_evaluation", _CONSUMER,
        ref_open=_REF_OPEN, ref_close=_REF_CLOSE, body=body,
    )


def build_messages(
    technique_id: str,
    config: InterviewConfiguration,
    question: str | None = None,
    candidate_answer: str | None = None,
) -> list[dict[str, str]]:
    """Build the full, role-separated message list for one request.

    Returns a ``[system, user]`` list. The system message holds only trusted
    instructions and parameters; the user message holds all untrusted content.
    """
    return [
        {"role": "system", "content": build_system_prompt(technique_id, config)},
        {
            "role": "user",
            "content": build_user_message(config, question, candidate_answer),
        },
    ]


# =============================================================================
# Task-aware API (Phase 6)
# =============================================================================
#
# The five techniques above all target the evaluation task (they demonstrate
# prompt-engineering variety on one job). The application services, however,
# drive four distinct structured outputs. The task-aware builders below reuse
# the same mission, guardrails and session parameters, but swap in a
# task-specific instruction, a short technique directive, and the correct
# schema — so system/user separation and every safety rule still hold.

TASK_STRATEGY = "strategy"
TASK_QUESTION = "question"
TASK_EVALUATION = "evaluation"
TASK_REPORT = "report"

TASK_BRANCH = "branch"

TASK_SCHEMAS: dict[str, type[BaseModel]] = {
    TASK_STRATEGY: InterviewStrategy,
    TASK_QUESTION: InterviewQuestion,
    TASK_EVALUATION: AnswerEvaluation,
    TASK_REPORT: FinalInterviewReport,
    TASK_BRANCH: BranchQuestion,
}

_TASK_INSTRUCTIONS = {
    TASK_STRATEGY: render("interview/task_strategy", _CONSUMER),
    TASK_QUESTION: render("interview/task_question", _CONSUMER),
    TASK_EVALUATION: _TASK,
    TASK_REPORT: render("interview/task_report", _CONSUMER),
    TASK_BRANCH: render("interview/task_branch", _CONSUMER),
}

# Task-agnostic one-line approach per technique (the evaluation method blocks
# above are rubric-specific, so the task API uses these instead).
_TECHNIQUE_DIRECTIVES = table("interview/technique_directives", _CONSUMER)


def _schema_description_for(model: type[BaseModel]) -> str:
    """List a model's field names and descriptions (keeps prompts in sync)."""
    lines = []
    for name, field in model.model_fields.items():
        lines.append(f"  - {name}: {field.description or ''}")
    return "\n".join(lines)


def _output_contract_for(model: type[BaseModel]) -> str:
    """A generic strict-JSON output contract for any target schema."""
    return render(
        "interview/output_contract_generic", _CONSUMER,
        schema_name=model.__name__, schema_description=_schema_description_for(model),
    )


def _validate_task(task: str) -> type[BaseModel]:
    schema = TASK_SCHEMAS.get(task)
    if schema is None:
        raise ValueError(
            f"Unknown prompt task {task!r}; supported tasks are {list(TASK_SCHEMAS)}"
        )
    return schema


def build_task_system_prompt(
    task: str, technique_id: str, config: InterviewConfiguration
) -> str:
    """Build a task-specific system prompt using the chosen technique.

    Raises ``ValueError`` for an unknown task or technique ID.
    """
    schema = _validate_task(task)
    if technique_id not in SYSTEM_PROMPT_BUILDERS:
        raise ValueError(
            f"Unknown prompt technique {technique_id!r}; "
            f"supported IDs are {list(SYSTEM_PROMPT_BUILDERS)}"
        )
    directive = render(
        "interview/task_method", _CONSUMER,
        technique_id=technique_id, directive=_TECHNIQUE_DIRECTIVES[technique_id],
    )
    # Conversation-language directive (P10B Wave 4): prose-only, trusted, allow-listed. Placed
    # in the system prompt alongside the other trusted session parameters; omitted for English.
    language = _language_directive(config)
    blocks = [
        _MISSION,
        _GUARDRAILS,
        _session_parameters(config),
        _TASK_INSTRUCTIONS[task],
        directive,
        _output_contract_for(schema),
    ]
    if language:
        blocks.insert(3, language)  # after session parameters, before task instructions
    # Coaching-style directive (P10B Wave 2): applied ONLY to FEEDBACK wording — the evaluation
    # and the report — never to question/strategy generation (so it cannot change difficulty), and
    # never to scoring. Trusted, allow-list-only; balanced/unknown → omitted.
    if task in (TASK_EVALUATION, TASK_REPORT):
        style = _coaching_directive(config)
        if style:
            blocks.insert(3, style)
    return "\n\n".join(blocks)


def build_task_user_message(
    task: str,
    config: InterviewConfiguration,
    *,
    question: str | None = None,
    candidate_answer: str | None = None,
    previous_questions: Sequence[str] | None = None,
    previous_answers: Sequence[str] | None = None,
    previous_evaluation_summaries: Sequence[str] | None = None,
    current_question_number: int | None = None,
    branch_mode: str | None = None,
    branch_depth: int | None = None,
) -> str:
    """Assemble the user message for a task, with all free text as untrusted data."""
    _validate_task(task)
    sections = [
        _reference_block("target_role", config.target_role),
        _reference_block("industry_or_sector", config.industry_or_sector),
        _reference_block("company_context", config.company_context),
        _reference_block("job_description", config.job_description),
        _reference_block("candidate_background", config.candidate_background),
    ]

    for index, text in enumerate(previous_questions or [], start=1):
        sections.append(_reference_block(f"previous_question_{index}", text))
    for index, text in enumerate(previous_answers or [], start=1):
        sections.append(_reference_block(f"previous_answer_{index}", text))
    for index, text in enumerate(previous_evaluation_summaries or [], start=1):
        sections.append(
            _reference_block(f"previous_evaluation_summary_{index}", text)
        )

    if question is not None:
        sections.append(_reference_block("interview_question", question))
    if candidate_answer is not None:
        sections.append(_reference_block("candidate_answer", candidate_answer))

    body = "\n\n".join(section for section in sections if section)

    closing = {
        TASK_STRATEGY: lambda: render("interview/closing_strategy", _CONSUMER),
        TASK_QUESTION: lambda: render(
            "interview/closing_question", _CONSUMER,
            question_number=current_question_number or len((previous_questions or [])) + 1,
        ),
        TASK_EVALUATION: lambda: render("interview/closing_evaluation", _CONSUMER),
        TASK_REPORT: lambda: render("interview/closing_report", _CONSUMER),
        TASK_BRANCH: lambda: render(
            "interview/closing_branch", _CONSUMER,
            branch_depth=branch_depth or 1, branch_mode=branch_mode or "deepen_reasoning",
        ),
    }[task]()

    return render(
        "interview/user_frame_task", _CONSUMER,
        ref_open=_REF_OPEN, ref_close=_REF_CLOSE, body=body, closing=closing,
    )


def build_task_messages(
    task: str,
    technique_id: str,
    config: InterviewConfiguration,
    **user_message_kwargs: Any,
) -> list[dict[str, str]]:
    """Build role-separated messages for a task using the chosen technique."""
    return [
        {
            "role": "system",
            "content": build_task_system_prompt(task, technique_id, config),
        },
        {
            "role": "user",
            "content": build_task_user_message(task, config, **user_message_kwargs),
        },
    ]


# --- Prompt asset attribution (package 01B) ---------------------------------------------------------
# The asset families that compose a given system prompt, so a caller (the registry, the prompt
# comparison, the Prompt Lab) can attribute a result to the exact declared versions and hashes
# without exposing any prompt text. Conditional families (language directive, coaching wrapper) are
# included only when the config actually causes them to be rendered.

_EVALUATION_SHARED = (
    "interview/mission", "interview/guardrails", "interview/session_parameters",
    "interview/persona_tone", "interview/difficulty_rigour", "interview/response_detail_length",
)
_EVALUATION_METHODS: dict[str, tuple[str, ...]] = {
    "zero_shot": ("interview/method_zero_shot",),
    "role_persona": ("interview/method_role_persona",),
    "few_shot": ("interview/method_few_shot", "interview/few_shot_example"),
    "structured_procedure": ("interview/method_structured_procedure",),
    "rubric_json": ("interview/method_rubric_json",),
}


def prompt_families(
    technique_id: str, config: InterviewConfiguration | None = None, task: str | None = None
) -> tuple[str, ...]:
    """Asset families composing the system prompt for a technique (and optionally a task).

    ``task=None`` is the five-technique evaluation path (``build_system_prompt``); a task name is the
    task-aware path (``build_task_system_prompt``). ``config`` decides whether the conversation-language
    and coaching-style families are in effect. Raises ``ValueError`` for an unknown technique or task.
    """
    if technique_id not in SYSTEM_PROMPT_BUILDERS:
        raise ValueError(f"Unknown prompt technique {technique_id!r}")
    if task is None:
        families = [
            *_EVALUATION_SHARED, "interview/task_evaluation", *_EVALUATION_METHODS[technique_id],
            "interview/output_contract_evaluation",
        ]
    else:
        _validate_task(task)
        families = [
            *_EVALUATION_SHARED, f"interview/task_{task}", "interview/task_method",
            "interview/technique_directives", "interview/output_contract_generic",
        ]
    if config is not None:
        if _language_directive(config) is not None:
            families.append("interview/language_directive")
        if task in (TASK_EVALUATION, TASK_REPORT) and _coaching_directive(config) is not None:
            families += ["coaching/wrapper", "coaching/directives"]
    return tuple(families)
