"""Guarded live runners for P10E. They only run inside ``guard.live_session`` (the durable ledger, exclusive lock and HTTP guard are active), so every provider request is checked and
reserved before it is sent. ``build`` is injectable so the whole path is tested with a mock transport and no network.

A refusal by the guard inside the OpenAI SDK may surface as ``APIConnectionError`` (the SDK wraps and may retry unknown exceptions); runners therefore detect refusals from the
guard's own record (``http_guard.refused``), never from the exception type.
"""

from __future__ import annotations

import json
import os
import re
from decimal import Decimal
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


def models_requested(session: G.LiveSession, run_id: str | None = None) -> dict[str, int]:
    """The models this session's requests actually asked for, straight from the durable ledger (so nested helper calls are included)."""
    rid = run_id or session.run_id
    with session.ledger._mutex:
        return dict(session.ledger.conn.execute("SELECT model, COUNT(*) FROM entries WHERE run_id=? GROUP BY model", (rid,)).fetchall())


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


def classify_kb_case(case: dict) -> str:
    """Classify a corpus case from ITS OWN pinned tags and expectations (never from the model output): a case designed so that no supporting evidence exists (the correct behaviour is to
    abstain), one designed with supporting evidence (a citation is expected), or neither."""
    tags = case.get("tags") or []
    e = case.get("expect") or {}
    if any(t.startswith(("grounding:unsupported", "citation:unavailable_evidence")) for t in tags) or e.get("citations_max") == 0:
        return "designed_unsupported"
    if e.get("citations_min", 0) >= 1 or e.get("citation_sources"):
        return "designed_supported"
    return "unclassified"


def rescore_kb_run(run_dir: Path) -> dict:
    """Offline re-score of a saved KB run (no provider call): add each case's design class and the deterministic observation that is meaningful for it. A designed-unsupported case with
    NO citation is an appropriate abstention at the structural level (still PENDING_HUMAN_REVIEW for whether the wording is right); the structural ``answer_grounded`` proxy is only
    meaningful for designed-supported cases. No threshold is applied and no human rating is implied."""
    from src.copilot.knowledge import requalification as Q

    run_dir = Path(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    by_id = {c["id"]: c for c in Q.load_corpus()["cases"]}
    rows = []
    for c in summary["results"]["cases"]:
        if c["status"] != "COMPLETE":
            rows.append({"case": c["case"], "status": c["status"]})
            continue
        kind = classify_kb_case(by_id[c["case"]])
        obs = {"designed_unsupported": {"no_citation_invented": c["citations"] == 0}, "designed_supported": {"answer_grounded_structural": c["answer_grounded"], "citations": c["citations"]}}.get(kind, {"citations": c["citations"]})
        rows.append({"case": c["case"], "design": kind, "observation": obs})
    tally = {k: {"cases": sum(1 for r in rows if r.get("design") == k)} for k in ("designed_supported", "designed_unsupported", "unclassified")}
    tally["designed_supported"]["structurally_grounded"] = sum(1 for r in rows if r.get("design") == "designed_supported" and r["observation"]["answer_grounded_structural"])
    tally["designed_unsupported"]["no_citation_invented"] = sum(1 for r in rows if r.get("design") == "designed_unsupported" and r["observation"]["no_citation_invented"])
    out = {"run_id": summary["run_id"], "model": summary["results"]["model"], "profile": summary["results"]["profile"], "rescored_offline": True, "per_case": rows, "tally": tally,
           "pending_human_review": list(PENDING_HUMAN), "thresholds": "none: no pass or fail is declared"}
    with open(run_dir / "rescore.json", "x", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    return out


def run_auth_failure_probe(session: G.LiveSession, *, base: Path = G.LIVE_DIR, build: Callable[[str], Any] | None = None) -> dict:
    """ONE request with a deliberately invalid credential to a priced model: observes the provider's real rejection and the ledger's rule (dollars released, the call still counted).
    The invalid key is a fixed dummy, never a real credential."""
    from langchain_openai import ChatOpenAI

    from src.llm.models import ModelProfile, model_id

    slug = model_id(ModelProfile.FAST)
    rec = G.LiveRunRecorder("auth-failure-probe", provider="OpenRouter", model=slug, profile="fast", base=base, extra=session.evidence_refs())
    if session.http_guard is not None:
        session.http_guard.recorder = rec
    model = build(slug) if build else ChatOpenAI(model=slug, api_key="invalid-p10e-probe-key", base_url="https://openrouter.ai/api/v1", max_tokens=50, timeout=session.limits.request_timeout_s, max_retries=0)
    before = session.ledger.snapshot()
    err = None
    try:
        model.invoke([("human", SMOKE_PROMPT)])
        outcome = "UNEXPECTED_SUCCESS"
    except Exception as exc:  # noqa: BLE001
        err, outcome = type(exc).__name__, "REJECTED_OR_FAILED"
    after = session.ledger.snapshot()
    row = session.ledger.conn.execute("SELECT state, status_code, committed_usd FROM entries ORDER BY seq DESC LIMIT 1").fetchone()
    res = {"outcome": outcome, "error_category": err, "ledger_state": row[0], "http_status": row[1], "committed_usd_for_the_call": row[2],
           "calls_counted": after["calls"] - before["calls"], "usd_added": str(Decimal(after["committed_usd"]) - Decimal(before["committed_usd"]))}
    rec.finish(session.budget.summary(), res)
    if session.http_guard is not None:
        session.http_guard.recorder = None
    return res


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


def _calls_since(rec: Any, already: int) -> list[dict]:
    """The sanitized request records written for the current run after the first ``already`` lines (status, tokens, cost; never content)."""
    try:
        lines = (rec.dir / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []
    return [json.loads(x) for x in lines[already:]]


def refine_case(classified_case: dict, calls: list[dict], reason: str | None, reasons: list[str]) -> tuple[dict, dict]:
    """Refine the terminal status from facts the runner owns and build the sanitized per-case evidence: a guard refusal or a provider failure is never reported as a normal agent outcome."""
    provider_failures = [c for c in calls if c.get("error") or (c.get("status") not in (None, 200))]
    if reason:
        classified_case["terminal_status"], classified_case["completed"] = "GUARD_REFUSED", False
    elif provider_failures and classified_case["terminal_status"] != "COMPLETED":
        classified_case["terminal_status"], classified_case["completed"] = "PROVIDER_ERROR", False
    reported = [c["provider_cost_usd"] for c in calls if c.get("provider_cost_usd") is not None]
    evidence = {**classified_case, "provider_calls": len(calls), "provider_failures": len(provider_failures), "guard_refusal_reasons": sorted(set(reasons)),
                "provider_reported_cost_usd": str(sum((Decimal(str(x)) for x in reported), Decimal(0))) if reported else None}
    return classified_case, evidence


def run_agent(session: G.LiveSession, profile: str, *, limit: int | None = None, only: list[str] | None = None, base: Path = G.LIVE_DIR, build: Callable[[str], Any] | None = None, isolate: bool = True) -> dict:
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
    if only:
        cases = [c for c in cases if c["id"] in set(only)]
    if limit:
        cases = cases[:limit]
    slug = model_id(prof)
    rec = G.LiveRunRecorder("agent-live", provider="OpenRouter", model=slug, profile=profile, dataset_version=f"{len(cases)} held-out cases", base=base, extra=session.evidence_refs())
    if session.http_guard is not None:
        session.http_guard.recorder = rec
    career = _default_career_service()
    results, stopped, packet = [], None, []
    calls_before = 0
    for case in cases:
        before = len(session.http_guard.refused) if session.http_guard else 0
        before_n = before
        # The PRODUCT's own default model factory (profile resolved through the canonical registry, governed tunables) is used unless a test injects one: this is the real path.
        svc = AgentApplicationService(model_factory=(lambda p=None: build(slug)) if build is not None else None, career_service=career)
        t0 = time.perf_counter()
        res = svc.run(AgentRunRequest(goal=case["goal"], user_id="p10e-live-eval", profile=prof.value))
        latency = int((time.perf_counter() - t0) * 1000)
        reason = _refused_since(session, before)
        reasons = list(session.http_guard.refused[before_n:]) if session.http_guard else []
        calls = _calls_since(rec, calls_before)
        calls_before += len(calls)
        obs = observation_from_result(case["id"], profile, res, latency)
        classified_case, evidence = refine_case(classify(case, obs), calls, reason, reasons)
        from src.p10e import r1_evals as _E          # deterministic, content-free response flags (synthetic held-out goals only)
        text = obs.response_text or ""
        evidence["response_flags"] = {"chars": len(text), "money_figure": _E.has_money_figure(text), "states_insufficient_evidence": _E.states_insufficient_evidence(text), "has_citation_marker": bool(re.search(r"\[\d+\]", text))}
        packet.append({"case": case["id"], "goal": case["goal"], "terminal_status": classified_case["terminal_status"], "tools_used": classified_case["tools_used"], "response_excerpt": text[:700],
                       "human_review": {"response_appropriate_without_retrieval": "PENDING_HUMAN_REVIEW", "unsupported_claim": "PENDING_HUMAN_REVIEW"}})
        results.append({"classified": classified_case, "evidence": evidence, "guard_refusal": reason, "guard_refusal_reasons": reasons, "case": case["id"], "latency_ms": latency})
        if reason in ("spend_ceiling", "call_limit"):
            stopped = reason
            break
    after_fp = protected_store_fingerprint()
    classified = [r["classified"] for r in results if not r["guard_refusal"]]
    metrics = aggregate(classified) if classified else {}
    out = {"profile": profile, "model": slug, "cases_planned": len(cases), "cases_completed": len(classified), "cases_refused": [r["case"] for r in results if r["guard_refusal"]], "guard_refusal_reasons": {r["case"]: sorted(set(r["guard_refusal_reasons"])) for r in results if r["guard_refusal"]}, "stopped_by_guard": stopped,
           "metrics": metrics, "per_case": [r["evidence"] for r in results], "per_case_evidence_version": "2 (P10E-R1 correction: sanitized per-case classification; strict completion)", "per_case_latency_ms": {r["case"]: r["latency_ms"] for r in results}, "protected_stores_unchanged": before_fp == after_fp,
           "models_requested": models_requested(session), "expected_model": slug,
           "unexpected_models": sorted(m for m in models_requested(session) if m != slug), "cases_attempted": len(results),
           "note": "PARTIAL: the guard stopped the run; metrics cover only the completed cases" if stopped else "Complete over the planned cases. Metrics measure the model's decisions on a bounded held-out sample; not an accuracy score."}
    d = rec.finish(session.budget.summary(), out)
    (d / "review_packet.json").write_text(json.dumps({"reviewer": None, "note": "synthetic held-out goals only; excerpts are the model's own text for human review", "cases": packet}, indent=1, ensure_ascii=False), encoding="utf-8")
    if session.http_guard is not None:
        session.http_guard.recorder = None
    if iso.get("tmp"):
        shutil.rmtree(iso["tmp"], ignore_errors=True)
    return {"run_dir": str(d), "results": out, "budget": session.budget.summary()}
