"""Domain system prompt and message assembly for the baseline RAG chain.

The system prompt encodes the grounding rules that keep answers evidence-based.
It is never shown in the UI (see the RAG Inspector, which deliberately omits it).
"""

from __future__ import annotations

from src.copilot import constants
from src.prompt_assets import render, template

__all__ = ["system_prompt", "build_messages"]


# The grounding prompt and the user-message frames are versioned assets under prompts/rag/
# (package 01B); ``_SYSTEM_PROMPT`` stays the unrendered template for callers that format it.
_CONSUMER = "rag.prompts"
_SYSTEM_PROMPT = template("rag/baseline_system", _CONSUMER)


def system_prompt() -> str:
    """Return the domain system prompt (never displayed in the UI)."""
    return render("rag/baseline_system", _CONSUMER, insufficient=constants.INSUFFICIENT_EVIDENCE_MESSAGE)


def build_messages(question: str, context_text: str) -> list[dict[str, str]]:
    """Assemble system + user messages for the chat model.

    The retrieved context is placed in the user turn (clearly delimited) so the
    model treats it as reference data, not as further instructions.
    """
    if context_text.strip():
        user_content = render(
            "rag/baseline_user_context", _CONSUMER, context_text=context_text, question=question
        )
    else:
        user_content = render("rag/baseline_user_no_context", _CONSUMER, question=question)
    return [
        {"role": "system", "content": system_prompt()},
        {"role": "user", "content": user_content},
    ]
