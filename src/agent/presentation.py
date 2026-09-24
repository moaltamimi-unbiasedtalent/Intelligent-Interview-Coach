"""Deterministic response presentation contract (Capstone P2/E2).

Turns Mo's FULL grounded answer into a candidate-facing information hierarchy —
ANSWER, DETAILS, NEXT STEP — for progressive disclosure. This is a **pure,
presentation-layer** transform:

* It makes **no** model/provider call and does not alter tool selection, the ReAct
  loop, retrieval or citations.
* It **never truncates or deletes** content: ``answer`` + ``details`` always
  reconstruct the full text. Brief mode collapses ``details`` behind "Show more";
  it never removes it.
* The split is **semantic** (paragraph boundaries), never a character/token cut.
* ``next_step`` is derived ONLY from real structured state (a gathered preparation
  context) — it is never fabricated.

Sources/citations are a separate structured field on the response and are rendered
alongside this contract; they are not duplicated here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

__all__ = ["ResponsePresentation", "build_presentation"]

# A conservative floor: answers at or below this length are shown in full with no
# "Show more" affordance (collapsing a short answer adds friction without value).
_SHORT_ANSWER_CHARS = 280


@dataclass(frozen=True)
class ResponsePresentation:
    answer: str
    details: str
    has_details: bool
    # {"label": str, "kind": str} or None — a single, real next action when one exists.
    next_step: dict | None = None

    def to_dict(self) -> dict:
        return {
            "answer": self.answer,
            "details": self.details,
            "has_details": self.has_details,
            "next_step": self.next_step,
        }


@dataclass
class _Signals:
    """Real structured signals used to derive a (non-fabricated) next step."""

    preparation_context: dict | None = None
    awaiting_human_input: bool = False
    handoff_approved: bool = False
    status: str = "completed"
    extra_next_steps: list[dict] = field(default_factory=list)


def _split_answer_details(text: str) -> tuple[str, str]:
    """Split markdown into (lead block, remainder) at the first blank-line boundary.

    The lead block is the first paragraph or list; the remainder is everything after.
    If the lead is a lone short heading, fold the following block into the answer so
    the answer is never just a title.
    """
    stripped = (text or "").strip()
    if not stripped:
        return "", ""
    blocks = re.split(r"\n\s*\n", stripped)
    if len(blocks) == 1:
        return stripped, ""
    answer = blocks[0].strip()
    rest = blocks[1:]
    # If the first block is only a heading line, include the next block in the answer.
    if _is_heading_only(answer) and rest:
        answer = f"{answer}\n\n{rest[0].strip()}"
        rest = rest[1:]
    details = "\n\n".join(b.strip() for b in rest).strip()
    return answer, details


def _is_heading_only(block: str) -> bool:
    lines = [ln for ln in block.splitlines() if ln.strip()]
    return len(lines) == 1 and lines[0].lstrip().startswith("#")


def _derive_next_step(signals: _Signals) -> dict | None:
    """Return one real next action, or None. Never fabricated."""
    # A run still waiting on a human decision surfaces that via its own HITL card;
    # do not also emit a next step (avoid a conflicting instruction).
    if signals.awaiting_human_input:
        return None
    # A gathered preparation context means the candidate can proceed to practice.
    if signals.preparation_context:
        return {"label": "Start interview practice", "kind": "start_practice"}
    return None


def build_presentation(
    response_text: str,
    *,
    preparation_context: dict | None = None,
    awaiting_human_input: bool = False,
    handoff_approved: bool = False,
    status: str = "completed",
) -> ResponsePresentation:
    """Build the presentation contract for one candidate-facing answer."""
    answer, details = _split_answer_details(response_text)

    # Never force a "Show more" on an already-short answer with no real remainder.
    has_details = bool(details)
    if has_details and len((answer or "")) <= _SHORT_ANSWER_CHARS and not details.strip():
        has_details = False

    next_step = _derive_next_step(
        _Signals(
            preparation_context=preparation_context,
            awaiting_human_input=awaiting_human_input,
            handoff_approved=handoff_approved,
            status=status,
        )
    )
    return ResponsePresentation(
        answer=answer,
        details=details,
        has_details=has_details,
        next_step=next_step,
    )
