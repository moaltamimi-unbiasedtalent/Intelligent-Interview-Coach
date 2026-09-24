"""Deterministic response presentation contract (Capstone P2/E2).

The split is semantic, non-truncating, and next_step is derived only from real state.
"""

from __future__ import annotations

from src.agent.presentation import build_presentation


def test_short_single_paragraph_has_no_details():
    p = build_presentation("A concise, complete answer.")
    assert p.answer == "A concise, complete answer."
    assert p.details == ""
    assert p.has_details is False
    assert p.next_step is None


def test_multi_paragraph_splits_answer_and_details():
    text = "Lead answer paragraph.\n\nSupporting detail one.\n\nSupporting detail two."
    p = build_presentation(text)
    assert p.answer == "Lead answer paragraph."
    assert "Supporting detail one." in p.details
    assert "Supporting detail two." in p.details
    assert p.has_details is True


def test_no_content_is_lost_in_the_split():
    text = "Lead.\n\nMiddle.\n\nEnd."
    p = build_presentation(text)
    # answer + details reconstruct the full text (nothing truncated/deleted).
    assert f"{p.answer}\n\n{p.details}" == text


def test_heading_only_lead_folds_next_block_into_answer():
    p = build_presentation("# Summary\n\nThe real answer.\n\nThe details.")
    assert "Summary" in p.answer and "The real answer." in p.answer
    assert p.details == "The details."


def test_next_step_present_when_preparation_context_exists():
    p = build_presentation("Answer.\n\nDetails.", preparation_context={"target_role": "PM"})
    assert p.next_step == {"label": "Start interview practice", "kind": "start_practice"}


def test_next_step_absent_without_preparation_context():
    p = build_presentation("Answer.\n\nDetails.")
    assert p.next_step is None


def test_next_step_suppressed_while_awaiting_human_input():
    p = build_presentation(
        "Answer.\n\nDetails.", preparation_context={"x": 1}, awaiting_human_input=True
    )
    assert p.next_step is None


def test_empty_response_is_safe():
    p = build_presentation("")
    assert p.answer == "" and p.details == "" and p.has_details is False and p.next_step is None


def test_to_dict_shape():
    d = build_presentation("A.\n\nB.").to_dict()
    assert set(d) == {"answer", "details", "has_details", "next_step"}
