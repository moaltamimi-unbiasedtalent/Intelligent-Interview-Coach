"""P10B-W9.10 - the product claim guard runs green and actually catches violations (0 paid/live calls)."""

import re

from scripts import eval_product_positioning as guard


def test_guard_passes_on_the_repository():
    results = guard.run()
    failed = {k: v for k, (ok, v) in results.items() if not ok}
    assert not failed, failed


def test_guard_patterns_catch_prohibited_claims_and_competitors():
    bad = ["We are GDPR compliant", "100% secure", "bias-free coaching", "better than ChatGPT",
           "guarantees interview success", "human reviewed", "a revolutionary tool"]
    for phrase in bad:
        assert any(re.search(p, phrase.lower()) for p in guard.PROHIBITED), phrase
    assert any(re.search(r"\b%s\b" % c, "ask4mo vs yoodli".lower()) for c in guard.COMPETITORS)


def test_guard_does_not_flag_legitimate_documentation_discussing_prohibited_claims():
    claims = guard.read("docs/product/PRODUCT_CLAIMS.md").lower()
    assert any(re.search(p, claims) for p in guard.PROHIBITED)  # the register names them...
    assert not any(re.search(p, guard.public_copy().lower()) for p in guard.PROHIBITED)  # ...copy never does
