"""Guarded live runners for P10E. Every provider call goes through ``guard.GuardCallback``; nothing here runs unless ``guard.require_live`` returned approved limits.

``build`` is injectable so the whole path (admission, ceiling, accounting, evidence) is tested with fake LangChain models and no network.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any, Callable

from src.p10e import guard as G

SMOKE_PROMPT = "Reply with the single word: ok"


def guarded_model(profile: str, limits: G.LiveLimits, budget: G.LiveBudget, recorder: G.LiveRunRecorder | None = None, *, build: Callable[[str], Any] | None = None):
    """A chat model for a typed profile (Fast/Balanced/Advanced) with the approved timeout, output cap and retries, and the budget callback attached. No raw model name is accepted."""
    from src.llm.models import ModelProfile, model_id

    slug = model_id(ModelProfile(profile))
    if build is None:
        from src.copilot.config import load_config
        from src.copilot.llm.openrouter import build_chat_model

        def build(s: str):  # noqa: ANN001
            return build_chat_model(load_config(), model=s, max_tokens=limits.max_output_tokens_per_request, timeout_s=limits.request_timeout_s, max_retries=limits.max_retries)
    model = build(slug)
    cb = G.make_guard_callback(budget, slug, recorder)
    model.callbacks = list(getattr(model, "callbacks", None) or []) + [cb]
    return model, slug


def run_smoke(profiles: list[str], limits: G.LiveLimits, *, prices: dict | None = None, build: Callable[[str], Any] | None = None, base: Path = G.LIVE_DIR) -> dict:
    """One tiny request per profile. Verifies authentication, schema, usage and latency reporting and that the answering model is the requested one. NOT a quality result."""
    budget = G.new_budget(limits, prices, base)
    out = {}
    for profile in profiles:
        rec = G.LiveRunRecorder("smoke", provider="OpenRouter", model="(resolved below)", profile=profile, base=base)
        status, detail = "FAILED", {}
        try:
            model, slug = guarded_model(profile, limits, budget, rec, build=build)
            rec.meta["model"] = slug
            t0 = time.perf_counter()
            msg = model.invoke([("human", SMOKE_PROMPT)])
            latency = int((time.perf_counter() - t0) * 1000)
            content = (getattr(msg, "content", "") or "").strip()
            meta = getattr(msg, "response_metadata", None) or {}
            answered_by = meta.get("model_name") or meta.get("model")
            usage = getattr(msg, "usage_metadata", None)
            detail = {"model": slug, "answered_by": answered_by, "non_empty": bool(content), "usage_reported": isinstance(usage, dict) and "input_tokens" in usage, "latency_ms": latency,
                      "unexpected_fallback": bool(answered_by and not str(answered_by).startswith(slug.split(":")[0])) if answered_by else "UNKNOWN"}
            status = "OK" if detail["non_empty"] and detail["unexpected_fallback"] is not True else "FAILED"
        except G.LiveRunRefused as exc:
            status, detail = "REFUSED", {"reason": exc.reason}
        except Exception as exc:  # noqa: BLE001 - a provider failure is a controlled category, never a fabricated success and never the raw message (it could echo request data)
            status, detail = "FAILED", {"error_category": type(exc).__name__}
        out[profile] = {"status": status, **detail}
        rec.finish(budget.summary(), {"smoke": out[profile], "note": "A successful smoke test is not quality qualification."})
    return {"results": out, "budget": budget.summary()}


def _live_responder(model: Any, slug: str):
    from src.copilot.rag.responder import ModelReply, usage_from_lc

    role_map = {"system": "system", "user": "human", "assistant": "ai"}

    def respond(messages: list[dict]):
        result = model.invoke([(role_map.get(m["role"], "human"), m["content"]) for m in messages])
        return ModelReply(content=getattr(result, "content", "") or "", usage=usage_from_lc(result, slug))

    return respond


# Metrics from the P10D contract that have a DETERMINISTIC observation in the existing answer path. Everything else is not computed here and stays pending: no threshold is
# invented and no human metric is fabricated.
DETERMINISTIC_NOW = {"answer_grounded": "every [n] marker in the answer is an evidence marker and at least one citation exists (a structural proxy, not a claim-support judgement)"}
PENDING_HUMAN = ("citation_supports_claim", "language_consistency", "abstains_when_unsupported")
NOT_COMPUTED = {"no_cross_country_claim": "needs a per-case country expectation that the existing answer cases do not carry; PENDING_HUMAN_REVIEW", "injection_resistance": "the corpus has no injection answer case in the selected set; NOT COMPUTED"}


def run_kb_quality(profile: str, limits: G.LiveLimits, *, prices: dict | None = None, build: Callable[[str], Any] | None = None, base: Path = G.LIVE_DIR,
                   contract_path: Path | None = None) -> dict:
    """Real-model answers for the selected ANSWER cases of the P10D contract over the synthetic fixture corpus. The 11 selected evidence cases need a synthesis harness that does
    not exist and are reported NOT RUN. Case expectations are never edited after seeing output."""
    from src.copilot.knowledge import requalification as Q

    contract = json.loads((contract_path or Path(G.ROOT) / "evaluations/kb_requalification/model_quality_contract.json").read_text(encoding="utf-8"))
    corpus = Q.load_corpus()
    by_id = {c["id"]: c for c in corpus["cases"]}
    selected = [by_id[i] for i in contract["case_selection"]["case_ids"]]
    answer_cases = [c for c in selected if c["kind"] == "answer"]
    budget = G.new_budget(limits, prices, base)
    rec = G.LiveRunRecorder("kb-quality", provider="OpenRouter", model="(resolved below)", profile=profile, dataset_version=corpus["version"], base=base)
    model, slug = guarded_model(profile, limits, budget, rec, build=build)
    rec.meta["model"] = slug
    live = _live_responder(model, slug)
    cases_out, packet = [], []
    stopped = None
    with Q.temp_world(corpus) as world:
        for case in answer_cases:
            refusals_before = len(budget.refusals)
            try:
                spy = Q.Spy(live)
                res = world.service(responder=spy, retriever=bool(case.get("needs_retriever"))).answer(case["query"])
                if len(budget.refusals) > refusals_before:
                    # The answer service catches provider-path exceptions and degrades to a fallback answer; a guard refusal must never be reported as a model answer.
                    raise G.BudgetExceeded(budget.refusals[-1], "stopped by the budget guard")
                answer = res.response.answer or ""
                n_ev = len(res.response.evidence)
                used = set(re.findall(r"\[(\d+)\]", answer))
                grounded = bool(res.response.citations) and used <= {str(i) for i in range(1, n_ev + 1)}
                cases_out.append({"case": case["id"], "status": "COMPLETE", "citations": len(res.response.citations), "answer_grounded": grounded, "degraded": list(res.trace.degraded), "answer_chars": len(answer)})
                packet.append({"case": case["id"], "query": case["query"], "evidence_titles": [getattr(e, "title", None) for e in res.response.evidence], "citations": [c.doc_id for c in res.response.citations],
                               "model_answer": answer, "human_ratings": {m: "PENDING_HUMAN_REVIEW" for m in PENDING_HUMAN}})
            except G.BudgetExceeded as exc:
                stopped = exc.reason
                cases_out.append({"case": case["id"], "status": "NOT RUN (stopped by the budget guard)", "reason": exc.reason})
                break
            except Exception as exc:  # noqa: BLE001
                cases_out.append({"case": case["id"], "status": "FAILED", "error_category": type(exc).__name__})
    not_run = [c["id"] for c in selected if c["kind"] != "answer"] + [c["case"] for c in cases_out if c["status"].startswith("NOT RUN")]
    results = {"profile": profile, "model": slug, "cases": cases_out, "evidence_cases_not_run": [c["id"] for c in selected if c["kind"] != "answer"], "stopped_by_guard": stopped,
               "metrics": {"deterministic_computed": DETERMINISTIC_NOW, "pending_human_review": list(PENDING_HUMAN), "not_computed": NOT_COMPUTED, "thresholds": "none: the owner has not set any; no pass or fail is declared"},
               "language_note": "the selected answer cases carry no language tag; per-language results cannot be derived from them"}
    d = rec.finish(budget.summary(), results)
    (d / "review_packet.json").write_text(json.dumps({"rubric": "see model_quality_contract.json metrics; ratings must name the reviewer, date and explanation", "reviewer": None, "cases": packet}, indent=1), encoding="utf-8")
    return {"run_dir": str(d), "results": results, "budget": budget.summary(), "not_run": not_run}
