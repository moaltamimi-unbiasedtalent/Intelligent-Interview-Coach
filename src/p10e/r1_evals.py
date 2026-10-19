"""P10E-R1 evaluations: the interview-quality harness and the multilingual knowledge-base evaluation.

Both reuse the EXISTING product services (``InterviewService``, ``EvaluationService``, the knowledge-base answer service) and the P10E live session: no second model client, no
second budget. The datasets are pre-registered (``evaluations/p10e/r1/*.json``, hash-locked in ``registration.lock.json``): expectations were fixed before any live call and a test
fails if a file changes. Deterministic checks are proxies and are named as such; every subjective metric is PENDING_HUMAN_REVIEW and no threshold exists.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from src.p10e import guard as G
from src.p10e import live_runs as R

R1_DIR = G.ROOT / "evaluations" / "p10e" / "r1"
LOCK = R1_DIR / "registration.lock.json"
RESPONSE_DETAIL = "standard"          # the product's mid level; a fixed code constant so the registered dataset is untouched


def verify_registration() -> dict[str, str]:
    """The pre-registered datasets must hash to the locked values; otherwise an expectation was edited after registration."""
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    out = {}
    for name, expected in lock["files"].items():
        got = hashlib.sha256((R1_DIR / name).read_bytes()).hexdigest()
        if got != expected:
            raise G.LiveRunRefused("dataset_changed_after_registration", f"{name} no longer matches its registered hash; a pre-registered expectation must never be edited.")
        out[name] = got
    return out


# ================================================================================================================================== interview quality
def load_interview_cases() -> dict:
    verify_registration()
    doc = json.loads((R1_DIR / "interview_cases.json").read_text(encoding="utf-8"))
    ids = [c["id"] for c in doc["cases"]]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate interview case id")
    return doc


def interview_configuration(case: dict):
    from src.models import InterviewConfiguration

    return InterviewConfiguration(target_role=case["target_role"], industry_or_sector=case["industry_or_sector"], career_level=case["career_level"], job_description=case["job_description"],
                                  candidate_background=case["candidate_background"], interview_types=case["interview_types"], interviewer_persona=case["interviewer_persona"],
                                  difficulty=case["difficulty"], number_of_questions=case["number_of_questions"], response_detail=RESPONSE_DETAIL)


def _text(*parts: Any) -> str:
    return " ".join(str(p) for p in parts if p).lower()


def check_question(case: dict, q: Any) -> dict[str, bool]:
    body = q.question or ""
    return {"question_is_a_question": "?" in body and 15 <= len(body) <= 900,
            "question_type_requested": q.question_type in case["interview_types"],
            "question_role_keyword": any(k in _text(q.question, q.competency, q.interviewer_intent) for k in case["role_keywords"])}


def check_evaluation(case: dict, doc: dict, ev: Any) -> dict[str, bool]:
    grounded_fields = _text(" ".join(ev.strengths), " ".join(ev.improvement_areas), " ".join(ev.missing_evidence))
    everything = _text(ev.strengths, ev.improvement_areas, ev.missing_evidence, ev.stronger_answer_structure, ev.improved_example_answer, ev.follow_up_question, getattr(ev, "overall_summary", ""))
    bias = {t.strip() for t in doc["bias_terms"]}
    return {"evaluation_has_missing_evidence_when_gap_designed": (bool(ev.missing_evidence) if case["answer_has_evidence_gap"] else True),
            "evaluation_references_answer_content": any(f.lower() in grounded_fields for f in case["answer_facts"]),
            "no_invented_candidate_experience": not any(t in grounded_fields for t in case["forbidden_inventions"]),
            "follow_up_is_a_question": bool(ev.follow_up_question) and "?" in ev.follow_up_question,
            "no_hiring_decision": not any(p in everything for p in doc["hiring_decision_phrases"]),
            "no_biased_wording": not any(re.search(rf"\b{re.escape(t)}\b", everything) for t in bias)}          # whole words only (the registered "he " means the word "he", never the end of "the")


def run_interview_quality(session: G.LiveSession, profile: str = "balanced", *, only: list[str] | None = None, services: tuple | None = None, base: Path = G.LIVE_DIR) -> dict:
    """Two real calls per case (generate the question, evaluate the fixed synthetic answer) with the product's own services and ONE selected profile (the documented interview policy)."""
    from src.llm.models import ModelProfile, model_id
    from src.models import ModelSettings

    doc = load_interview_cases()
    cases = [c for c in doc["cases"] if not only or c["id"] in only]
    slug = model_id(ModelProfile(profile))
    rec = G.LiveRunRecorder("interview-quality", provider="OpenRouter", model=slug, profile=profile, dataset_version=doc["version"], base=base,
                            extra={**session.evidence_refs(), "dataset_sha256": verify_registration()["interview_cases.json"], "calls_per_case_planned": doc["calls_per_case"]})
    if session.http_guard is not None:
        session.http_guard.recorder = rec
    client = None
    if services is None:
        from src.application.factories import build_interview_services
        from src.config import load_config

        interview, evaluation, _report, client = build_interview_services(load_config())
    else:
        interview, evaluation = services
    settings = ModelSettings(model=slug, max_tokens=session.limits.max_output_tokens_per_request)
    out, packet = [], []
    stopped = None
    try:
        for case in cases:
            before = len(session.http_guard.refused) if session.http_guard else 0
            row: dict[str, Any] = {"case": case["id"], "role_family": case["role_family"]}
            try:
                cfg = interview_configuration(case)
                q, _ = interview.generate_next_question(cfg, settings, current_question_number=1)
                ev, _ = evaluation.evaluate_answer(cfg, q.question, case["candidate_answer"], settings)
                row.update(status="COMPLETE", checks={**check_question(case, q), **check_evaluation(case, doc, ev)})
                packet.append({"case": case["id"], "role_family": case["role_family"], "scenario": {k: case[k] for k in ("target_role", "industry_or_sector", "career_level", "job_description", "candidate_background", "interview_types")},
                               "generated_question": q.model_dump(), "synthetic_candidate_answer": case["candidate_answer"], "evaluation": ev.model_dump(),
                               "human_ratings": {m: {"rating": None, "reviewer": None, "date": None, "comment": None, "status": "PENDING_HUMAN_REVIEW"} for m in doc["pending_human_review"]}})
            except Exception as exc:  # noqa: BLE001 - controlled category only; provider text is never recorded
                reason = R._refused_since(session, before)
                row.update(status="REFUSED_BY_GUARD" if reason else "FAILED", reason=reason, error_category=type(exc).__name__)
                if reason in ("spend_ceiling", "call_limit"):
                    stopped = reason
            out.append(row)
            if stopped:
                break
    finally:
        if client is not None:
            client.close()
    done = [r for r in out if r["status"] == "COMPLETE"]
    names = sorted({k for r in done for k in r["checks"]})
    summary = {"checks": {n: {"passed": sum(1 for r in done if r["checks"][n]), "of": len(done)} for n in names},
               "failed_cases_by_check": {n: [r["case"] for r in done if not r["checks"][n]] for n in names if any(not r["checks"][n] for r in done)}}
    results = {"profile": profile, "model": slug, "dataset_version": doc["version"], "cases_planned": len(cases), "cases_completed": len(done), "cases_not_completed": [r for r in out if r["status"] != "COMPLETE"],
               "stopped_by_guard": stopped, "models_requested": R.models_requested(session), "per_case": out, "deterministic_summary": summary, "pending_human_review": doc["pending_human_review"],
               "thresholds": doc["thresholds"], "note": "Deterministic checks are proxies, not quality judgements; every subjective metric is PENDING_HUMAN_REVIEW and no human or AI judge has rated anything."}
    d = rec.finish(session.budget.summary(), results)
    (d / "review_packet.json").write_text(json.dumps({"rubric": doc["pending_human_review"], "reviewer": None, "cases": packet}, indent=1), encoding="utf-8")
    if session.http_guard is not None:
        session.http_guard.recorder = None
    return {"run_dir": str(d), "results": results, "budget": session.budget.summary()}


# ================================================================================================================================== multilingual
STOPWORDS = {
    "en": "the and of to is in for that with are what does do it as this an a not on be or".split(),
    "de": "der die das und ist nicht mit für ein eine einen zu von auf den dem des sich es sind wird".split(),
    "fr": "le la les des et est pour une un que qui dans en au aux du sur pas ne se ce son sont".split(),
    "es": "el la los las de que y es para una un por con del se en no lo al sus como".split(),
    "it": "il lo la gli le di che è per una un con del della dei delle non si in al come sono".split(),
    "pt": "o a os as de que e é para uma um com do da dos das não se em no na como são".split(),
    "nl": "de het een en van is niet voor met dat op te zijn er ook aan om bij door worden".split(),
}
DISTINCTIVE = {"en": {"the", "does", "what", "are", "with"}, "de": {"der", "und", "nicht", "ist", "ein", "eine", "für"}, "fr": {"les", "des", "est", "une", "dans", "pour"},
               "es": {"los", "las", "del", "una", "para", "con"}, "it": {"gli", "della", "dei", "delle", "è", "sono"}, "pt": {"os", "as", "não", "uma", "são", "dos", "das"}, "nl": {"het", "een", "van", "niet", "voor", "zijn"}}


def detect_language(text: str) -> dict:
    """A stopword-profile heuristic with a double weight for distinctive words. A PROXY validated only on fixed sentences; it is not native-speaker validation."""
    tokens = re.findall(r"[^\W\d_]+", (text or "").lower())
    scores = {l: sum((2 if t in DISTINCTIVE[l] else 1) for t in tokens if t in set(words)) for l, words in STOPWORDS.items()}
    ranked = sorted(scores.items(), key=lambda kv: -kv[1])
    best, second = ranked[0], ranked[1]
    return {"language": best[0] if best[1] >= 3 and best[1] - second[1] >= 2 else None, "scores": scores}


def load_multilingual_cases() -> dict:
    verify_registration()
    doc = json.loads((R1_DIR / "multilingual_cases.json").read_text(encoding="utf-8"))
    problems = validate_multilingual(doc)
    if problems:
        raise ValueError("; ".join(problems))
    return doc


def validate_multilingual(doc: dict) -> list[str]:
    errs = []
    supported = {"en", "de", "fr", "es", "it", "pt", "nl"}
    if set(doc["languages"]) != supported or "ru" in doc["languages"] or "ru" not in doc["excluded_languages"]:
        errs.append("the language set must be exactly the seven knowledge-base languages with Russian excluded")
    ids = [c["id"] for c in doc["cases"]]
    if len(ids) != len(set(ids)):
        errs.append("duplicate case id")
    for lang in supported:
        kinds = {c["kind"] for c in doc["cases"] if c["language"] == lang}
        if kinds != {"supported_occupation_definition", "unsupported_country_compensation"}:
            errs.append(f"{lang}: both case kinds are required")
    for c in doc["cases"]:
        for f in ("language", "kind", "query_native", "query_live", "geography", "evidence_availability", "expected_behaviour", "acceptable_outcomes", "citation_boundary"):
            if not c.get(f):
                errs.append(f"{c.get('id')}: missing {f}")
    if not set(doc["priority_languages"]) <= supported:
        errs.append("priority languages must be supported")
    return errs


def multilingual_offline(doc: dict | None = None) -> dict:
    """Free, deterministic: for each case, does the NATIVE phrasing retrieve the fixture role document, and is a country-specific compensation item retrievable? No model call."""
    from src.copilot.knowledge import requalification as Q

    doc = doc or load_multilingual_cases()
    corpus = Q.load_corpus()
    rows = []
    with Q.temp_world(corpus) as world:
        for c in doc["cases"]:
            obs = Q._evidence_observed(world, c["query_native"])
            rows.append({"case": c["id"], "language": c["language"], "kind": c["kind"], "sources": obs["sources"], "n_evidence": obs["n_evidence"], "insufficient": obs["insufficient"], "clarify": obs["clarify"],
                         "resolved_country": obs["country"], "retrieved_role_document": "fx_roles" in obs["sources"], "retrieved_compensation_for_canada": "CA" in (obs["structured_countries"] + obs["evidence_countries"])})
    by_lang = {}
    for r in rows:
        by_lang.setdefault(r["language"], {})[r["kind"]] = {k: r[k] for k in ("retrieved_role_document", "retrieved_compensation_for_canada", "n_evidence", "insufficient", "clarify", "resolved_country")}
    return {"corpus_version": doc["version"], "per_language": by_lang, "no_model_call": True}


_CURRENCY = r"(?:[$€£¥]|\b(?:usd|cad|eur|gbp|chf)\b|dollars?|euros?|pounds?|dólares|dollar)"
_ESTIMATE_WORDS = ("estimat", "estimación", "estimacion", "estimation", "schätzung", "schatzung", "schatting", "stima", "estimativa", "range", "spanne", "fourchette", "rango", "intervallo", "intervalo", "bandbreedte", "marge")


def has_money_figure(text: str) -> bool:
    """A money figure: a currency marker next to a number, a thousands-separated number, or a number followed by k. A bare year (1900 to 2100) is NOT a money figure unless a currency marker is adjacent (P10E-R1 correction of the French false positive)."""
    t = text or ""
    if re.search(rf"{_CURRENCY}\s?\d|\d\s?{_CURRENCY}", t, re.IGNORECASE):
        return True
    if re.search(r"\b\d{1,3}(?:[.,\u202f\u00a0 ]\d{3})+\b", t):
        return True
    if re.search(r"\b\d+(?:[.,]\d+)?\s?[kK]\b", t):
        return True
    for m in re.finditer(r"\b(\d{4,})\b", t):
        n = int(m.group(1))
        if len(m.group(1)) == 4 and 1900 <= n <= 2100:
            continue                      # a year
        return True
    return False


def _insufficient_sentences() -> list[str]:
    from src.copilot.rag import localized
    return [re.sub(r"\W+", " ", v).strip().lower() for v in localized.INSUFFICIENT.values()]


def states_insufficient_evidence(text: str) -> bool:
    flat = re.sub(r"\W+", " ", text or "").strip().lower()
    return any(sent in flat for sent in _insufficient_sentences())


CLASSES = ("ANSWERED_WITH_EVIDENCE", "ABSTAINED", "CLARIFICATION_REQUESTED", "UNSUPPORTED_FACTUAL_RESPONSE", "UNCERTAIN_REQUIRES_REVIEW")


def classify_answer(case: dict, answer: str, n_evidence: int, n_citations: int) -> dict:
    """Deterministic outcome class from facts only (evidence count, markers, the localized insufficient-evidence sentence, money figures). It never infers a successful abstention from the citation count alone; what it cannot decide it sends to review."""
    markers = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
    bad_markers = sorted(m for m in markers if not 1 <= m <= max(n_evidence, 0))
    money = has_money_figure(answer)
    insufficient = states_insufficient_evidence(answer)
    short_question = len(answer) <= 500 and "?" in answer
    reasons = []
    if bad_markers:
        reasons.append(f"citation marker without evidence: {bad_markers}")
    if money:
        reasons.append("money figure present")
    if n_evidence > 0 and n_citations > 0 and not bad_markers:
        cls = "UNSUPPORTED_FACTUAL_RESPONSE" if (money and case["kind"] == "unsupported_country_compensation") else "ANSWERED_WITH_EVIDENCE"
    elif bad_markers or money:
        cls = "UNSUPPORTED_FACTUAL_RESPONSE"
    elif insufficient and n_citations == 0:
        cls = "ABSTAINED"
        reasons.append("states insufficient evidence")
    elif n_evidence == 0 and short_question:
        cls = "CLARIFICATION_REQUESTED"
    elif n_evidence > 0 and n_citations == 0 and not insufficient:
        cls = "UNSUPPORTED_FACTUAL_RESPONSE"
        reasons.append("evidence was available but the answer carries no citation")
    elif len(answer) > 600 and not insufficient:
        cls = "UNSUPPORTED_FACTUAL_RESPONSE"
        reasons.append("substantive answer with no evidence, no citation and no insufficient-evidence statement")
    else:
        cls = "UNCERTAIN_REQUIRES_REVIEW"
        reasons.append("cannot be classified deterministically")
    flags = []
    if any(w in (answer or "").lower() for w in _ESTIMATE_WORDS):
        flags.append("offers_unsourced_estimate")
    return {"class": cls, "reasons": reasons, "review_flags": flags, "money_figure": money, "states_insufficient_evidence": insufficient, "invalid_markers": bad_markers}


POST_HOC_NOTE = ("POST-HOC (defined AFTER observing the corrected run; it never replaces the registered classification): ABSTAINED_WITH_CITED_CONTEXT = the answer states insufficient evidence, "
                 "carries only valid [n] markers that refer to retrieved evidence, and contains no money figure. Whether citations attached to an abstention are acceptable is a product-presentation question for the owner.")


def _states_insufficient_loosely(text: str) -> bool:
    """POST-HOC only: the model often paraphrases the tail of the insufficient-evidence sentence ("... to answer what a Data Analyst earns"), so the first six words of any supported language's sentence are matched. The statement must
    OPEN the answer (within its first 400 characters, i.e. the Evidence section): a caveat at the end of an otherwise evidence-backed answer is a partial limitation, not an abstention."""
    flat = re.sub(r"\W+", " ", (text or "")[:400]).strip().lower()
    return any(" ".join(sent.split()[:6]) in flat for sent in _insufficient_sentences())


def reclassify_post_hoc(case: dict, answer: str, n_evidence: int, n_citations: int) -> dict:
    """An additional, clearly post-hoc reading of an answer the registered rules classed as ANSWERED_WITH_EVIDENCE although it states insufficient evidence."""
    registered = classify_answer(case, answer, n_evidence, n_citations)
    markers = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
    valid = all(1 <= m <= max(n_evidence, 0) for m in markers)
    if registered["class"] == "ANSWERED_WITH_EVIDENCE" and _states_insufficient_loosely(answer) and valid and not registered["money_figure"]:
        return {"registered_class": registered["class"], "post_hoc_class": "ABSTAINED_WITH_CITED_CONTEXT", "post_hoc": True}
    return {"registered_class": registered["class"], "post_hoc_class": registered["class"], "post_hoc": False}


def reclassify_run_post_hoc(run_dir: Path) -> dict:
    """Offline (no provider call): apply the post-hoc reading to a recorded multilingual run. Writes ``reclassification.json`` exclusively; the original files are never touched."""
    run_dir = Path(run_dir)
    summary = json.loads((run_dir / "summary.json").read_text(encoding="utf-8"))
    packet = json.loads((run_dir / "review_packet.json").read_text(encoding="utf-8"))
    cases = {c["id"]: c for c in load_multilingual_cases()["cases"]}
    ev = {(lang, kind): v for lang, kinds in summary["results"]["per_language"].items() for kind, v in kinds.items()}
    rows = []
    for item in packet["cases"]:
        c = cases[item["case"]]
        v = ev[(c["language"], c["kind"])]
        rows.append({"case": c["id"], "language": c["language"], "kind": c["kind"], **reclassify_post_hoc(c, item["model_answer"], int(v.get("evidence_items") or 0), int(v.get("citations") or 0))})
    out = {"source_run": run_dir.name, "note": POST_HOC_NOTE, "rescored_offline": True, "rows": rows}
    with open(run_dir / "reclassification.json", "x", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False)
    return out


def judge_class(kind: str, cls: str, expectations: dict) -> str:
    """Map a class to the PRE-REGISTERED expectation for the case kind: intended, gap, failure or review."""
    e = expectations["expectations_by_kind"][kind]
    for label in ("intended", "acceptable_but_gap", "failure", "review"):
        if cls in e[label]:
            return {"acceptable_but_gap": "gap"}.get(label, label)
    return "review"


def load_corrected_expectations() -> dict:
    verify_registration()
    return json.loads((R1_DIR / "multilingual_corrected_v1.json").read_text(encoding="utf-8"))


def check_multilingual_answer(case: dict, answer: str, n_evidence: int, n_citations: int, expectations: dict | None = None) -> dict:
    markers = {int(m) for m in re.findall(r"\[(\d+)\]", answer)}
    det = detect_language(answer)
    cl = classify_answer(case, answer, n_evidence, n_citations)
    checks = {"answer_language_matches": det["language"] == case["language"], "detected_language": det["language"], "citation_markers_valid": all(1 <= m <= max(n_evidence, 0) for m in markers),
              "citations": n_citations, "classification": cl["class"], "classification_reasons": cl["reasons"], "review_flags": cl["review_flags"] + ([] if det["language"] == case["language"] else ["language_mismatch"])}
    if expectations is not None:
        checks["against_registered_expectation"] = judge_class(case["kind"], cl["class"], expectations)
    if case["kind"] == "unsupported_country_compensation":
        checks["no_salary_figure_invented"] = not cl["money_figure"]
        checks["no_citation_for_unsupported"] = n_citations == 0
    return checks


def answer_case(world, spy, case: dict):
    """THE corrected candidate path: the fixture world's normal retriever is enabled and the case's conversation language is passed through the existing service interface (no hard-coded headings)."""
    return world.service(responder=spy).answer(case["query_live"], conversation_language=case["language"])


def run_multilingual_live(session: G.LiveSession, profile: str = "balanced", *, only: list[str] | None = None, build=None, base: Path = G.LIVE_DIR) -> dict:
    """Live answers through the existing knowledge-base service, one case at a time, reported PER LANGUAGE (never averaged)."""
    from src.copilot.knowledge import requalification as Q

    doc = load_multilingual_cases()
    cases = [c for c in doc["cases"] if not only or c["id"] in only]
    corpus = Q.load_corpus()
    offline = multilingual_offline(doc)
    expectations = load_corrected_expectations()
    rec = G.LiveRunRecorder("multilingual-live", provider="OpenRouter", model="(resolved below)", profile=profile, dataset_version=doc["version"], base=base,
                            extra={**session.evidence_refs(), "dataset_sha256": verify_registration()["multilingual_cases.json"], "corrected_expectations_sha256": verify_registration()["multilingual_corrected_v1.json"],
                                   "harness": "p10e-r1 corrected: retriever enabled, conversation_language passed"})
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
                spy = Q.Spy(live)
                res = answer_case(world, spy, c)
                reason = R._refused_since(session, before)
                if reason:
                    raise G.BudgetExceeded(reason, "stopped by the budget guard")
                answer = res.response.answer or ""
                n_ev, n_cit = len(res.response.evidence), len(res.response.citations)
                rows.append({"case": c["id"], "language": c["language"], "kind": c["kind"], "status": "COMPLETE", "checks": check_multilingual_answer(c, answer, n_ev, n_cit, expectations), "evidence_items": n_ev})
                packet.append({"case": c["id"], "language": c["language"], "query": c["query_live"], "expected_behaviour": c["expected_behaviour"], "model_answer": answer,
                               "human_ratings": {m: {"rating": None, "reviewer": None, "status": "PENDING_HUMAN_REVIEW"} for m in doc["pending_human_review"]}})
            except G.BudgetExceeded as exc:
                stopped = exc.reason
                rows.append({"case": c["id"], "language": c["language"], "kind": c["kind"], "status": "NOT RUN (stopped by the budget guard)", "reason": exc.reason})
                break
            except Exception as exc:  # noqa: BLE001
                rows.append({"case": c["id"], "language": c["language"], "kind": c["kind"], "status": "FAILED", "error_category": type(exc).__name__})
    per_lang: dict[str, dict] = {}
    for r in rows:
        per_lang.setdefault(r["language"], {})[r["kind"]] = r if r["status"] != "COMPLETE" else {"status": "COMPLETE", **r["checks"], "evidence_items": r["evidence_items"]}
    results = {"profile": profile, "model": slug, "dataset_version": doc["version"], "cases_planned": len(cases), "cases_completed": sum(1 for r in rows if r["status"] == "COMPLETE"), "stopped_by_guard": stopped,
               "per_language": per_lang, "offline_retrieval_native_phrasing": offline["per_language"], "pending_human_review": doc["pending_human_review"], "thresholds": doc["thresholds"],
               "note": "Languages are reported separately and never averaged. The language detector is a stopword proxy, not native-speaker validation; no native reviewer has rated anything."}
    d = rec.finish(session.budget.summary(), results)
    (d / "review_packet.json").write_text(json.dumps({"reviewer": None, "cases": packet}, indent=1, ensure_ascii=False), encoding="utf-8")
    if session.http_guard is not None:
        session.http_guard.recorder = None
    return {"run_dir": str(d), "results": results, "budget": session.budget.summary()}
