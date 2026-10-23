"""Agent policies: bounded-loop limit and the concise system prompt."""

from __future__ import annotations

from src.locales import LANGUAGE_NAMES
from src.prompt_assets import effective_versions, render

# Consumer contract id the agent assets declare in ``compatible_with``.
AGENT_CONSUMER = "agent.policies"

# The bounded loop can take at most this many agent steps before terminating
# safely. Kept small on purpose — the foundation needs only a couple of steps.
MAX_AGENT_STEPS = 6

def system_prompt(registry, exclude: set[str] | None = None) -> str:
    """Render the approved asset with the actual registry's available tools.

    Historical 1.0.0 remains immutable and compatible for an explicit reviewed rollback.
    """
    from src.prompt_assets import asset

    current = asset("agent/system", AGENT_CONSUMER)
    variables = {"tool_catalogue": registry.prompt_catalogue(exclude)} if "tool_catalogue" in current.variables else {}
    return render("agent/system", AGENT_CONSUMER, **variables)


# Compatibility constant used by prompt-version diagnostics; execution renders its actual registry.
from src.agent.registry import career_tool_registry  # noqa: E402

SYSTEM_PROMPT = system_prompt(career_tool_registry(None))

# Prompt families that make up Mo's effective prompt (recorded on every run result, 01B R6).
AGENT_PROMPT_FAMILY = "agent/system"
AGENT_LANGUAGE_PROMPT_FAMILY = "agent/response_language"


# --- Mo conversation language (Capstone P3.5) --------------------------------
# A bounded allow-list mapping the supported locale codes to their English language
# names. The response-language directive is built ONLY from this map, so a
# candidate-supplied value can never inject prompt text — an unknown code yields no
# directive at all. This sets the language of Mo's prose only; it never changes
# retrieval geography, tool selection or grounding.
RESPONSE_LANGUAGE_NAMES: dict[str, str] = dict(LANGUAGE_NAMES)  # single copy: src/locales.py


def response_language_directive(code: str | None) -> str | None:
    """Return a safe 'respond in <language>' directive, or None.

    Returns None for an unknown/blank code or for English (the default needs no
    directive). The language name comes only from the allow-list, never from the code
    string itself, so no untrusted text reaches the model.
    """
    if not code:
        return None
    name = RESPONSE_LANGUAGE_NAMES.get(str(code).strip().lower())
    if not name or name == "English":
        return None
    return render(AGENT_LANGUAGE_PROMPT_FAMILY, AGENT_CONSUMER, language_name=name)


# Prompt families a model-backed tool adds to a run's effective prompts, keyed by registered tool name.
# Tools that use no prompt (retrieval, deterministic tools, human-action tools) are absent. The
# specialist and registry code is owned by other packages and is not touched here.
TOOL_PROMPT_FAMILIES: dict[str, tuple[str, ...]] = {
    "AnalyzeJobDescription": ("career/job_analysis",),
    "GenerateInterviewQuestions": ("career/question_generation",),
}


def effective_agent_prompt_versions(
    language_code: str | None = None, extra_families: tuple[str, ...] = ()
) -> dict[str, dict[str, str]]:
    """Declared version and body hash of every prompt asset in effect for a run.

    ``agent/system`` always; ``agent/response_language`` only when a language directive is actually
    added for ``language_code``; plus ``extra_families`` (prompts of tools the run executed).
    Identifiers and hashes only, never prompt text.
    """
    families = [AGENT_PROMPT_FAMILY, *extra_families]
    if response_language_directive(language_code) is not None:
        families.append(AGENT_LANGUAGE_PROMPT_FAMILY)
    return effective_versions(families)


def run_prompt_versions(
    language_code: str | None,
    tools_used: list[str] | tuple[str, ...],
    coaching_style: str | None = None,
) -> dict[str, dict[str, str]]:
    """Effective prompt versions for one run.

    Mo's system prompt, plus (only when actually applied) the response-language directive, the
    coaching-style wrapper and directive table, and the prompts of the tools the run executed.
    """
    from src.coaching_style import coaching_style_directive

    extra = [
        family for tool in dict.fromkeys(tools_used) for family in TOOL_PROMPT_FAMILIES.get(tool, ())
    ]
    if coaching_style_directive(coaching_style) is not None:
        extra += ["coaching/wrapper", "coaching/directives"]
    return effective_agent_prompt_versions(language_code, tuple(extra))
