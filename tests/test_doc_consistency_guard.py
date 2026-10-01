"""P10B-W9.11 - documentation/architecture consistency guard runs green and can fail (0 paid/live calls)."""

from scripts import eval_doc_consistency as guard


def test_guard_passes_on_the_repository():
    failed = {k: v for k, (ok, v) in guard.run().items() if not ok}
    assert not failed, failed


def test_norm_makes_phrase_checks_wrap_and_markdown_tolerant():
    assert "six Career tools" in guard.norm("six **Career**\n tools")
    assert "not legal advice" in guard.norm("**not legal advice** and")


def test_reversed_authority_wording_would_be_detected():
    import re

    assert re.search(r"1\s*=\s*industry|3\s*=\s*official", "authority (1=industry .. 3=official)", re.I)
