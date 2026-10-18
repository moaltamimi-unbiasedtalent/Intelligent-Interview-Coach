#!/usr/bin/env python
"""The executable contract for a FUTURE model-quality evaluation of the knowledge-base answer path (P10D, mode C). It is a CONTRACT, not a result.

P10D was not authorised to make paid provider calls, so this script NEVER calls a model: by default it validates the contract against the corpus and prints a dry-run
(the exact prompts the real run would send, their size and the selected cases), then states that the evaluation is NOT AUTHORISED. A real run needs a written owner
authorisation, a maximum spend and an API credential, and is not implemented here (it is a separate, owner-approved wave); the flags below only decide whether the
refusal reasons are reported.

    python scripts/eval_kb_model_quality.py            # validate + dry-run + "NOT AUTHORISED" (exit 3)
    python scripts/eval_kb_model_quality.py --validate # validate only (exit 0 when sound)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import tests.conftest  # noqa: E402,F401

from src.copilot.knowledge import requalification as Q  # noqa: E402

CONTRACT = ROOT / "evaluations/kb_requalification/model_quality_contract.json"


def validate(contract: dict, corpus: dict) -> list[str]:
    errors = []
    if contract.get("schema") != "p10d-model-quality-contract/1" or "NOT AUTHORISED" not in contract.get("status", ""):
        errors.append("the contract must declare that it is not authorised and not run")
    by_id = {c["id"]: c for c in corpus["cases"]}
    for cid in contract["case_selection"]["case_ids"]:
        if cid not in by_id:
            errors.append(f"unknown case {cid}")
        elif by_id[cid]["kind"] not in ("answer", "evidence"):
            errors.append(f"{cid}: only answer and evidence cases may be selected")
    for lang in contract["case_selection"]["languages"]:
        if lang in contract["case_selection"]["excluded_languages"]:
            errors.append(f"language {lang} is both selected and excluded")
    if set(contract["case_selection"]["excluded_languages"]) & {"en", "de", "fr", "es", "it", "pt", "nl"}:
        errors.append("a supported knowledge-base language is excluded")
    if any("threshold" in json.dumps(m).lower() and any(ch.isdigit() for ch in str(m.get("threshold", ""))) for m in contract["metrics"]):
        errors.append("the contract must not carry an engineering-invented threshold")
    if not contract["reporting"]["never_average_across_languages"]:
        errors.append("languages must be reported separately")
    return errors


def dry_run(contract: dict, corpus: dict) -> dict:
    prompts = []
    with Q.temp_world(corpus) as world:
        for cid in contract["case_selection"]["case_ids"]:
            case = next(c for c in corpus["cases"] if c["id"] == cid)
            if case["kind"] == "answer":
                spy = Q._responder("echo_prompt")
                world.service(responder=spy, retriever=bool(case.get("needs_retriever"))).answer(case["query"])
                prompts.append({"case": cid, "chars": len(spy.prompt), "approx_tokens": len(spy.prompt) // 4})
            else:
                prompts.append({"case": cid, "chars": 0, "approx_tokens": 0, "note": "evidence case: the real run would add a synthesis call over this evidence"})
    return {"cases": len(prompts), "approx_input_tokens_per_pass": sum(p["approx_tokens"] for p in prompts), "per_case": prompts}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--validate", action="store_true")
    a = ap.parse_args(argv)
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    corpus = Q.load_corpus()
    errors = validate(contract, corpus)
    if errors:
        print("CONTRACT INVALID:", errors)
        return 1
    print(f"contract v{contract['version']} is sound against corpus v{corpus['version']} ({len(contract['case_selection']['case_ids'])} cases selected).")
    if a.validate:
        return 0
    d = dry_run(contract, corpus)
    print(f"dry run: {d['cases']} cases, about {d['approx_input_tokens_per_pass']} input tokens per pass and profile (no call made).")
    print("NOT AUTHORISED: P10D made no paid provider call and this contract has no owner authorisation, spend limit or credential. No model output exists.")
    return 3


if __name__ == "__main__":
    sys.exit(main())
