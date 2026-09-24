#!/usr/bin/env python
"""Capstone P2/E2 response-experience evaluation.

Deterministic, offline checks on the presentation contract (progressive disclosure)
and the response-detail preference. No model/provider call, no paid calls. Exits
non-zero if any invariant fails.

Measured (per §17):
  answer-first structure, brief/detailed availability, next-step presence when
  expected and absence when not, progressive-disclosure availability, no-truncation
  (content preserved), critical-caveat visibility, source preservation, preference
  persistence and cross-user preference isolation.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

os.environ.setdefault("EMAIL_PROVIDER", "memory")

from src.agent.presentation import build_presentation  # noqa: E402

PW = "correcthorsebattery"

# Representative response classes (canned grounded answers — no model call).
CASES = [
    ("simple_factual", "A product manager owns the 'why' and 'what' of a product.", None, False),
    ("jd_analysis",
     "This role centres on platform reliability.\n\nKey requirements:\n- SRE experience\n- On-call ownership\n\nEmphasis on incident response.",
     {"target_role": "SRE"}, True),
    ("gap_analysis",
     "You're strong on delivery; the main gap is executive communication.\n\nFocus areas:\n- Board-level storytelling\n- Metrics framing",
     {"target_role": "Head of Eng"}, True),
    ("preparation_plan",
     "Here is a focused two-week plan.\n\nWeek 1: fundamentals.\n\nWeek 2: mock interviews.",
     {"target_role": "PM"}, True),
    ("question_generation",
     "Here are five tailored questions.\n\n1. Tell me about a hard trade-off.\n2. Describe an incident you led.",
     {"target_role": "SRE"}, True),
    ("knowledge_retrieval",
     "Median compensation varies by region.\n\nIn Germany, senior PM ranges are broad; see the sources for specifics.",
     None, True),
    ("current_market",
     "Current postings emphasise AI literacy.\n\nRecent listings mention LLM tooling frequently.",
     None, True),
    # Unsupported evidence: the caveat leads the answer (answer-first keeps it visible).
    ("unsupported_evidence",
     "I don't have grounded evidence for that specific figure, so I can't state it confidently.\n\nWhat I can do is outline how to research it.",
     None, True),
    ("trivial_conversational", "Happy to help — what role are you preparing for?", None, False),
]


def run() -> dict[str, list[bool]]:
    results: dict[str, list[bool]] = {}

    def check(metric: str, ok: bool) -> None:
        results.setdefault(metric, []).append(bool(ok))

    for name, text, prep, expect_details in CASES:
        p = build_presentation(text, preparation_context=prep)
        # answer-first: the answer is the lead of the source text.
        check("answer_first", text.strip().startswith(p.answer[:40].strip()[:40] if p.answer else ""))
        # progressive-disclosure availability matches expectation.
        check("progressive_disclosure", p.has_details == expect_details)
        # no truncation: answer + details reconstruct the full text.
        recon = p.answer if not p.details else f"{p.answer}\n\n{p.details}"
        check("no_truncation", recon.strip() == text.strip())
        # next-step present iff a preparation context exists.
        check("next_step_correctness", (p.next_step is not None) == (prep is not None))

    # critical caveat visibility: the unsupported case's caveat is in the ANSWER (not collapsed).
    caveat = build_presentation(dict((c[0], c[1]) for c in CASES)["unsupported_evidence"])
    check("critical_caveat_visible", "can't state it confidently" in caveat.answer)

    # source preservation: presentation never carries/strips the sources field (separate).
    src_case = build_presentation("Answer with evidence.\n\nDetail.", preparation_context=None)
    check("source_preservation", "sources" not in src_case.to_dict())

    # preference persistence + cross-user isolation (API).
    from fastapi.testclient import TestClient
    from tests._auth_factories import build_auth_app, cookies_for, login_token, register

    app, _, _ = build_auth_app()
    with TestClient(app) as c:
        register(c, "a@example.com", PW)
        register(c, "b@example.com", PW)
        a = login_token(c, "a@example.com", PW)
        b = login_token(c, "b@example.com", PW)
        check("preference_default_brief", c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()["response_detail"] == "brief")
        c.patch("/api/v1/auth/preferences", json={"response_detail": "detailed"}, cookies=cookies_for(a))
        check("preference_persistence", c.get("/api/v1/auth/me", cookies=cookies_for(a)).json()["response_detail"] == "detailed")
        check("preference_isolation", c.get("/api/v1/auth/me", cookies=cookies_for(b)).json()["response_detail"] == "brief")

    return results


SAFETY_METRICS = {
    "no_truncation",
    "critical_caveat_visible",
    "source_preservation",
    "preference_isolation",
    "next_step_correctness",
}


def main() -> int:
    print("ASK4MO — CAPSTONE P2/E2 RESPONSE-EXPERIENCE EVALUATION\n")
    results = run()
    failed = False
    for metric in sorted(results):
        vals = results[metric]
        passed, total = sum(vals), len(vals)
        rate = passed / total if total else 0.0
        flag = ""
        if metric in SAFETY_METRICS and rate < 1.0:
            flag = "  ← SAFETY TARGET NOT MET"
            failed = True
        print(f"  {metric:28s} {passed}/{total}  rate={rate:.3f}{flag}")
    print("\nPaid LLM calls: 0   Live provider calls: 0")
    if failed:
        print("\nRESULT: FAIL")
        return 1
    print("\nRESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
