"""Job Description Analyzer — LLM structured output.

Extracts structured role requirements from a pasted job description. It must not
invent requirements: anything not explicitly stated goes into
``interpretation_notes`` (reasonable interpretation), kept separate from the
explicit requirement lists.
"""

from __future__ import annotations

from src.copilot.config import CopilotConfig
from src.prompt_assets import render
from src.copilot.tools.schemas import JobAnalyzerArgs, RoleRequirements
from src.copilot.tools.structured import StructuredProducer, build_structured_producer

__all__ = ["analyze_job", "SYSTEM_PROMPT"]

# Versioned assets (prompts/career/job_analysis*, package 01B).
_CONSUMER = "career.tools"
SYSTEM_PROMPT = render("career/job_analysis", _CONSUMER)


def _messages(args: JobAnalyzerArgs) -> list[dict]:
    focus = render("career/job_analysis_focus", _CONSUMER, focus=args.focus) if args.focus else ""
    return [
        {"role": "system", "content": SYSTEM_PROMPT + focus},
        {"role": "user", "content": f"JOB DESCRIPTION:\n{args.job_description}"},
    ]


def analyze_job(
    args: JobAnalyzerArgs,
    *,
    producer: StructuredProducer | None = None,
    config: CopilotConfig | None = None,
) -> RoleRequirements:
    """Analyse a job description into :class:`RoleRequirements`."""
    producer = producer or build_structured_producer(config, RoleRequirements)
    result = producer(_messages(args))
    if not isinstance(result, RoleRequirements):
        result = RoleRequirements.model_validate(result)
    return result
