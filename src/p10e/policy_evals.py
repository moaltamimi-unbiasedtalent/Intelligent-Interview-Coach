"""Prospective evaluation of the owner-approved candidate grounding policies A, B and C (2026-10-19).

Separate from the P10E-R1 registered evaluations, which are never touched. The contract (``evaluations/p10e/policy/candidate_policy_contract_v1.json``) is hash-locked
BEFORE any live call; expectations are never edited after observing output; no acceptance threshold exists; everything is reported per case and per language.

Offline parts (no provider call) test the deterministic enforcement on scripted model outputs in all seven knowledge-base languages and classify agent observations
against the contract. The live parts reuse the existing guarded runners and the existing P10E ledger and are manual (``P10E_LIVE=1``), never CI.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from src.copilot.rag import localized
from src.copilot.security import grounding_policy as GP
from src.p10e import guard as G
from src.p10e.errors import LiveRunRefused

ROOT = Path(__file__).resolve().parents[2]
POLICY_DIR = ROOT / "evaluations" / "p10e" / "policy"
CONTRACT = POLICY_DIR / "candidate_policy_contract_v1.json"
LOCK = POLICY_DIR / "registration.lock.json"
LANGS = ("en", "de", "fr", "es", "it", "pt", "nl")
_PERCENT = re.compile(r"\d+(?:[.,]\d+)?\s?%")


def verify_contract() -> str:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    got = hashlib.sha256(CONTRACT.read_bytes()).hexdigest()
    if got != lock["files"][CONTRACT.name]:
        raise LiveRunRefused("dataset_changed_after_registration", "The candidate policy contract no longer matches its registered hash; an expectation must never be edited.")
    return got


def load_contract() -> dict:
    verify_contract()
    return json.loads(CONTRACT.read_text(encoding="utf-8"))


# ===================================================================================================================== offline: scripted multilingual enforcement
def scripted_multilingual(contract: dict | None = None) -> dict:
    """Per language: the scripted abstention-plus-estimate-offer answer goes through the REAL enforcement (no model). Reports what a reviewer needs; never averaged."""
    c = contract or load_contract()["unsourced_estimate_offers"]
    out = {}
    for lang in LANGS:
        query = c["query_by_language"][lang]
        answer = " ".join(c["scripted_answers"][lang])
        refusal = c["refusals_that_must_stay"][lang]
        res = GP.enforce(answer + "\n" + refusal, evidence=[], query=query, resolved_country="CA", language=lang)
        sentences = [s for _, s in GP._units(res.answer)]
        out[lang] = {
            "offer_removed": not any(GP.offers_unsourced_estimate(s) for s in sentences),
            "guidance_added": localized.compensation_guidance(lang) in res.answer,
            "abstention_kept": GP.states_insufficient(res.answer),
            "refusal_kept": refusal in res.answer,
            "no_money_figure": not GP.money_figures(res.answer),
            "response_class": res.response_class,
            "findings": res.findings,
        }
    return {"contract_version": load_contract()["version"], "per_language": out, "no_model_call": True}


# ===================================================================================================================== agent: contract cases and compliance
def agent_cases(contract: dict | None = None, *, live_only: bool = False) -> list[dict]:
    """Contract cases in the shape the existing agent runner expects. Policy compliance is judged separately (a retrieval 'optional' case is never scored by the legacy retrieval rule)."""
    out = []
    for c in (contract or load_contract())["agent_policy_cases"]:
        if live_only and not c.get("live"):
            continue
        out.append({"id": c["id"], "goal": c["goal"], "required_tools": c["required_tools"], "forbidden_tools": c["forbidden_tools"], "retrieval_expected": c["retrieval_expected"] == "required",
                    "hitl_expected": bool(c["hitl_expected"]), "hitl_type": c.get("hitl_type"), "max_tool_calls": None})
    return out


def judge_agent_case(case: dict, per_case: dict, response_text: str) -> dict:
    """The recorded fields requested by the owner plus a policy-compliance label. Pure and offline; unknown situations are REVIEW, never a quality verdict."""
    text = response_text or ""
    used = set(per_case.get("tools_used") or [])
    retrieved = "SearchCareerKnowledge" in used or bool(per_case.get("retrieval_used"))
    clarif = len(text) <= 700 and "?" in text
    abst = GP.states_insufficient(text)
    unsourced_figure = bool(GP.money_figures(text) or _PERCENT.search(text)) and not retrieved
    estimate_offer = any(GP.offers_unsourced_estimate(s) for _, s in GP._units(text)) if GP.is_compensation_query(case["goal"]) else False
    forbidden = sorted(used & set(case.get("forbidden_tools") or []))
    paused = bool(per_case.get("hitl_pause_observed"))
    kind = case["kind"]
    if kind == "external_fact":
        if forbidden or estimate_offer or unsourced_figure:
            label = "NON_COMPLIANT"
        elif retrieved:
            label = "COMPLIANT"
        elif clarif and not unsourced_figure:
            label = "CLARIFICATION_WITHOUT_RETRIEVAL"
        else:
            label = "NON_COMPLIANT_NO_RETRIEVAL"
    elif kind == "clarification":
        if forbidden or paused:
            label = "NON_COMPLIANT"
        elif clarif or abst:
            label = "COMPLIANT_WITH_RETRIEVAL" if retrieved else "COMPLIANT"
        elif retrieved and not unsourced_figure:
            label = "COMPLIANT_WITH_RETRIEVAL"
        else:
            label = "REVIEW"
    else:   # hitl
        expected = bool(case["hitl_expected"])
        type_ok = (not expected) or case.get("hitl_type") is None or per_case.get("pending_action_type") == case["hitl_type"]
        label = "COMPLIANT" if (paused == expected and type_ok and not forbidden) else "NON_COMPLIANT"
    return {
        "case": case["id"], "expected_behavior": case["expected_behavior"], "required_tools": case["required_tools"], "tools_used": sorted(used),
        "clarification_status": "clarification" if clarif else ("abstention" if abst else "none"),
        "retrieval_decision": "retrieved" if retrieved else "not_retrieved",
        "evidence_sufficiency": ("insufficient_stated" if abst else ("evidence_cited" if re.search(r"\[\d+\]", text) else "not_applicable")),
        "factual_claim_status": "unsourced_figure" if unsourced_figure else ("estimate_offer" if estimate_offer else "no_unsourced_claim_detected"),
        "hitl_decision": "paused" if paused else "no_pause", "terminal_status": per_case.get("terminal_status"), "policy_compliance": label,
    }


def evaluate_agent_run(run_dir: Path, contract: dict | None = None) -> dict:
    """Offline: judge a recorded policy agent run against the contract. Writes ``policy_evaluation.json`` exclusively; original run files are never touched."""
    run_dir = Path(run_dir)
    c = contract or load_contract()
    cases = {x["id"]: x for x in c["agent_policy_cases"]}
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    packet = {p["case"]: p for p in json.loads((run_dir / "review_packet.json").read_text(encoding="utf-8"))["cases"]}
    rows = [judge_agent_case(cases[pc["case_id"]], pc, packet.get(pc["case_id"], {}).get("response_excerpt", "")) for pc in summary["results"]["per_case"]]
    out = {"source_run": run_dir.name, "contract_version": c["version"], "rows": rows, "thresholds": c["thresholds"], "human_review": "PENDING_HUMAN_REVIEW", "rescored_offline": True}
    with open(run_dir / "policy_evaluation.json", "x", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return out


# ===================================================================================================================== live (manual, existing ledger)
def run_policy_agent_live(session, profile: str = "balanced", *, only: list[str] | None = None, build=None, base: Path = G.LIVE_DIR) -> dict:
    from src.p10e import live_runs as R

    cases = agent_cases(live_only=not only)
    out = R.run_agent(session, profile, only=only, base=base, build=build, cases=cases, area="policy-agent-live")
    return out


def run_policy_multilingual_live(session, profile: str = "balanced", *, only: list[str] | None = None, build=None, base: Path = G.LIVE_DIR) -> dict:
    """The unsupported-country compensation cases of the locked R1 corpus (inputs unchanged) answered through the product path, then judged against policies A and C. New result; the R1 records are not touched."""
    from src.copilot.knowledge import requalification as Q
    from src.p10e import live_runs as R
    from src.p10e import r1_evals as E

    contract = load_contract()
    doc = E.load_multilingual_cases()
    cases = [c for c in doc["cases"] if c["kind"] == "unsupported_country_compensation" and (not only or c["id"] in only)]
    corpus = Q.load_corpus()
    rec = G.LiveRunRecorder("policy-multilingual-live", provider="OpenRouter", model="(resolved below)", profile=profile, dataset_version=contract["version"], base=base,
                            extra={**session.evidence_refs(), "policy_contract_sha256": verify_contract(), "r1_corpus_sha256": E.verify_registration()["multilingual_cases.json"]})
    if session.http_guard is not None:
        session.http_guard.recorder = rec
    model, slug = R.chat_model(profile, session.limits, build=build)
    rec.meta["model"] = slug
    live = R._live_responder(model, slug)
    rows, packet, stopped = [], [], None
    with Q.temp_world(corpus) as world:
        for c in cases:
            before = len(session.http_guard.refused) if session.http_guard else 0
            try:
                res = E.answer_case(world, Q.Spy(live), c)
                reason = R._refused_since(session, before)
                if reason:
                    raise G.BudgetExceeded(reason, "stopped by the budget guard")
                answer = res.response.answer or ""
                evidence = list(res.response.evidence)
                sentences = [s for _, s in GP._units(answer)]
                cited = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
                cross = sorted(m for m in cited if 1 <= m <= len(evidence) and evidence[m - 1].evidence_type == "compensation" and evidence[m - 1].country not in (None, "", "CA"))
                rows.append({"case": c["id"], "language": c["language"], "status": "COMPLETE", "response_class": res.trace.response_class, "policy_findings": list(res.trace.output_findings or []),
                             "no_estimate_offer": not any(GP.offers_unsourced_estimate(s) for s in sentences), "no_money_figure": not GP.money_figures(answer), "no_cross_geography_citation": not cross,
                             "answer_language_matches": E.detect_language(answer)["language"] == c["language"], "evidence_items": len(evidence), "citations": len(res.response.citations)})
                packet.append({"case": c["id"], "language": c["language"], "query": c["query_live"], "model_answer": answer,
                               "human_ratings": {m: {"rating": None, "reviewer": None, "status": "PENDING_HUMAN_REVIEW"} for m in doc["pending_human_review"]}})
            except G.BudgetExceeded as exc:
                stopped = exc.reason
                rows.append({"case": c["id"], "language": c["language"], "status": "NOT RUN (stopped by the budget guard)", "reason": exc.reason})
                break
            except Exception as exc:  # noqa: BLE001
                rows.append({"case": c["id"], "language": c["language"], "status": "FAILED", "error_category": type(exc).__name__})
    results = {"profile": profile, "model": slug, "contract_version": contract["version"], "cases_planned": len(cases), "cases_completed": sum(1 for r in rows if r["status"] == "COMPLETE"),
               "stopped_by_guard": stopped, "rows": rows, "models_requested": R.models_requested(session), "thresholds": contract["thresholds"],
               "note": "Per language, never averaged. Language detection is a stopword proxy, not a fluency review; human review is PENDING_HUMAN_REVIEW."}
    d = rec.finish(session.budget.summary(), results)
    (d / "review_packet.json").write_text(json.dumps({"reviewer": None, "cases": packet}, indent=1, ensure_ascii=False), encoding="utf-8")
    if session.http_guard is not None:
        session.http_guard.recorder = None
    return {"run_dir": str(d), "results": results, "budget": session.budget.summary()}
