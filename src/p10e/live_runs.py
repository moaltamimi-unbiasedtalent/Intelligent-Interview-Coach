"""Guarded live runners for P10E. They only run inside ``guard.live_session`` (the durable ledger, exclusive lock and HTTP guard are active), so every provider request is checked and
reserved before it is sent. ``build`` is injectable so the whole path is tested with a mock transport and no network.

A refusal by the guard inside the OpenAI SDK may surface as ``APIConnectionError`` (the SDK wraps and may retry unknown exceptions); runners therefore detect refusals from the
guard's own record (``http_guard.refused``), never from the exception type.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from src.p10e import guard as G

SMOKE_PROMPT = "Reply with the single word: ok"
ROOT = G.ROOT


def chat_model(profile: str, limits: G.LiveLimits, *, build: Callable[[str], Any] | None = None):
    """A chat model for a typed profile (Fast/Balanced/Advanced) carrying the approved timeout, output cap and retries. No raw model name is accepted. The budget is enforced at the HTTP layer."""
    from src.llm.models import ModelProfile, model_id

    slug = model_id(ModelProfile(profile))
    if build is not None:
        return build(slug), slug
    from src.copilot.config import load_config
    from src.copilot.llm.openrouter import build_chat_model

    return build_chat_model(load_config(), model=slug, max_tokens=limits.max_output_tokens_per_request, timeout_s=limits.request_timeout_s, max_retries=limits.max_retries), slug


def _refused_since(session: G.LiveSession, before: int) -> str | None:
    g = session.http_guard
    return g.refused[-1] if g is not None and len(g.refused) > before else None


def protected_store_fingerprint(root: Path = ROOT) -> dict:
    out: dict[str, tuple[int, int]] = {}
    data = root / "data"
    candidates = list(data.glob("*.db")) + list(data.glob("*.sqlite*")) + list(data.glob("*.db-*"))
    for sub in ("chroma", "cache", "knowledge", "feedback_intelligence"):
        d = data / sub
        if d.exists():
            candidates += [p for p in d.rglob("*") if p.is_file()]
    for p in candidates:
        try:
            st = p.stat()
            out[str(p.relative_to(root))] = (st.st_size, st.st_mtime_ns)
        except OSError:
            continue
    return out


def run_smoke(session: G.LiveSession, profiles: list[str], *, build: Callable[[str], Any] | None = None, base: Path = G.LIVE_DIR) -> dict:
    """One tiny request per profile. Verifies authentication, schema, usage and latency reporting and that the answering model is the requested one. NOT a quality result."""
    out = {}
    for profile in profiles:
        rec = G.LiveRunRecorder("smoke", provider="OpenRouter", model="(resolved below)", profile=profile, base=base, extra=session.evidence_refs())
        if session.http_guard is not None:
            session.http_guard.recorder = rec
        before = len(session.http_guard.refused) if session.http_guard else 0
        anomalies_before = len(session.http_guard.anomalies) if session.http_guard else 0
        status, detail = "FAILED", {}
        try:
            model, slug = chat_model(profile, session.limits, build=build)
            rec.meta["model"] = slug
            t0 = time.perf_counter()
            msg = model.invoke([("human", SMOKE_PROMPT)])
            latency = int((time.perf_counter() - t0) * 1000)
            content = (getattr(msg, "content", "") or "").strip()
            meta = getattr(msg, "response_metadata", None) or {}
            answered_by = meta.get("model_name") or meta.get("model")
            usage = getattr(msg, "usage_metadata", None)
            fallback = bool(session.http_guard and len(session.http_guard.anomalies) > anomalies_before) or bool(answered_by and not str(answered_by).startswith(slug.split(":")[0]))
            detail = {"model": slug, "answered_by": answered_by, "non_empty": bool(content), "finish_reason": meta.get("finish_reason"), "usage_reported": isinstance(usage, dict) and "input_tokens" in usage,
                      "input_tokens": (usage or {}).get("input_tokens"), "output_tokens": (usage or {}).get("output_tokens"), "latency_ms": latency, "unexpected_fallback": fallback}
            status = "OK" if detail["non_empty"] and not fallback else "FAILED"
        except Exception as exc:  # noqa: BLE001 - a provider failure is a controlled category, never a fabricated success and never the raw message (it could echo request data)
            reason = _refused_since(session, before)
            status, detail = ("REFUSED", {"reason": reason}) if reason else ("FAILED", {"error_category": type(exc).__name__})
        out[profile] = {"status": status, **detail}
        rec.finish(session.budget.summary(), {"smoke": out[profile], "note": "A successful smoke test is not quality qualification."})
        if session.http_guard is not None:
            session.http_guard.recorder = None
    return {"results": out, "budget": session.budget.summary()}


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


def run_kb_quality(session: G.LiveSession, profile: str, *, build: Callable[[str], Any] | None = None, base: Path = G.LIVE_DIR, contract_path: Path | None = None) -> dict:
    """Real-model answers for the selected ANSWER cases of the P10D contract over the synthetic fixture corpus. The 11 selected evidence cases need a synthesis harness that does
    not exist and are reported NOT RUN. Case expectations are never edited after seeing output."""
    from src.copilot.knowledge import requalification as Q

    contract = json.loads((contract_path or ROOT / "evaluations/kb_requalification/model_quality_contract.json").read_text(encoding="utf-8"))
    corpus = Q.load_corpus()
    by_id = {c["id"]: c for c in corpus["cases"]}
    selected = [by_id[i] for i in contract["case_selection"]["case_ids"]]
    answer_cases = [c for c in selected if c["kind"] == "answer"]
    rec = G.LiveRunRecorder("kb-quality", provider="OpenRouter", model="(resolved below)", profile=profile, dataset_version=corpus["version"], base=base, extra=session.evidence_refs())
    if session.http_guard is not None:
        session.http_guard.recorder = rec
    model, slug = chat_model(profile, session.limits, build=build)
    rec.meta["model"] = slug
    live = _live_responder(model, slug)
    cases_out, packet = [], []
    stopped = None
    with Q.temp_world(corpus) as world:
        for case in answer_cases:
            before = len(session.http_guard.refused) if session.http_guard else 0
            try:
                spy = Q.Spy(live)
                res = world.service(responder=spy, retriever=bool(case.get("needs_retriever"))).answer(case["query"])
                reason = _refused_since(session, before)
                if reason:
                    # The answer service catches provider-path exceptions and degrades to a fallback answer; a guard refusal must never be reported as a model answer.
                    raise G.BudgetExceeded(reason, "stopped by the budget guard")
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
    d = rec.finish(session.budget.summary(), results)
    (d / "review_packet.json").write_text(json.dumps({"rubric": "see model_quality_contract.json metrics; ratings must name the reviewer, date and explanation", "reviewer": None, "cases": packet}, indent=1), encoding="utf-8")
    if session.http_guard is not None:
        session.http_guard.recorder = None
    return {"run_dir": str(d), "results": results, "budget": session.budget.summary(), "not_run": not_run}


def isolate_agent_stores() -> dict:
    """Redirect everything the agent path could write to disposable storage: a COPY of the knowledge vector store, the research cache and the database settings. The protected
    developer stores are only fingerprinted (before and after), never opened by the run."""
    tmp = Path(tempfile.mkdtemp(prefix="p10e_agent_"))
    src_chroma = ROOT / "data" / "chroma"
    if src_chroma.exists():
        shutil.copytree(src_chroma, tmp / "chroma")
    os.environ["COPILOT_CHROMA_DIR"] = str(tmp / "chroma")
    os.environ["DATABASE_URL"] = f"sqlite:///{tmp / 'p10e.db'}"
    os.environ.pop("AGENT_CHECKPOINT_DATABASE_URL", None)
    from src.copilot.research import cache

    orig_read, orig_write = cache.read, cache.write
    cdir = tmp / "research_cache"
    cache.read = lambda key, **kw: orig_read(key, **{"cache_dir": cdir, **kw})
    cache.write = lambda key, payload, **kw: orig_write(key, payload, **{"cache_dir": cdir, **kw})
    return {"tmp": str(tmp)}


def run_agent(session: G.LiveSession, profile: str, *, limit: int | None = None, base: Path = G.LIVE_DIR, build: Callable[[str], Any] | None = None, isolate: bool = True) -> dict:
    """The existing held-out agent benchmark against a real model, every request guarded. Case expectations are never edited after seeing output."""
    from src.agent.live_eval import aggregate, classify, load_live_cases, observation_from_result
    from src.agent.models import AgentRunRequest
    from src.application.agent_service import AgentApplicationService, _default_career_service
    from src.llm.models import ModelProfile, model_id, spec

    prof = ModelProfile(profile)
    if not spec(prof).supports_tools:
        return {"status": "FAILED", "reason": "profile does not support tool calling"}
    before_fp = protected_store_fingerprint()
    iso = isolate_agent_stores() if isolate else {}
    cases = load_live_cases()
    if limit:
        cases = cases[:limit]
    slug = model_id(prof)
    rec = G.LiveRunRecorder("agent-live", provider="OpenRouter", model=slug, profile=profile, dataset_version=f"{len(cases)} held-out cases", base=base, extra=session.evidence_refs())
    if session.http_guard is not None:
        session.http_guard.recorder = rec
    career = _default_career_service()
    results, stopped = [], None
    for case in cases:
        before = len(session.http_guard.refused) if session.http_guard else 0
        svc = AgentApplicationService(model_factory=lambda: chat_model(profile, session.limits, build=build)[0], career_service=career)
        t0 = time.perf_counter()
        res = svc.run(AgentRunRequest(goal=case["goal"], user_id="p10e-live-eval", profile=prof.value))
        latency = int((time.perf_counter() - t0) * 1000)
        reason = _refused_since(session, before)
        results.append({"classified": classify(case, observation_from_result(case["id"], profile, res, latency)), "guard_refusal": reason, "case": case["id"], "latency_ms": latency})
        if reason in ("spend_ceiling", "call_limit"):
            stopped = reason
            break
    after_fp = protected_store_fingerprint()
    classified = [r["classified"] for r in results if not r["guard_refusal"]]
    metrics = aggregate(classified) if classified else {}
    out = {"profile": profile, "model": slug, "cases_planned": len(cases), "cases_completed": len(classified), "cases_refused": [r["case"] for r in results if r["guard_refusal"]], "stopped_by_guard": stopped,
           "metrics": metrics, "per_case_latency_ms": {r["case"]: r["latency_ms"] for r in results}, "protected_stores_unchanged": before_fp == after_fp,
           "note": "PARTIAL: the guard stopped the run; metrics cover only the completed cases" if stopped else "Complete over the planned cases. Metrics measure the model's decisions on a bounded held-out sample; not an accuracy score."}
    d = rec.finish(session.budget.summary(), out)
    if session.http_guard is not None:
        session.http_guard.recorder = None
    if iso.get("tmp"):
        shutil.rmtree(iso["tmp"], ignore_errors=True)
    return {"run_dir": str(d), "results": out, "budget": session.budget.summary()}
