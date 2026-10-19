"""P10E-R1 interview-quality harness and multilingual corpus: pre-registration integrity, validation, deterministic checks, per-language reporting, and the guarded runners. Offline: fake
services and a mock transport only; no network, no credential, no paid call."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest

from src.p10e import guard as G
from src.p10e import r1_evals as E
from tests.test_p10e_ledger import Transport, _ok_body, chat, make_ledger, session

ROOT = Path(__file__).resolve().parents[1]


# ============================================================================================================================ pre-registration
def test_the_datasets_are_hash_locked_and_an_edited_expectation_is_refused(tmp_path, monkeypatch):
    assert set(E.verify_registration()) == {"interview_cases.json", "multilingual_cases.json"}
    copy = tmp_path / "r1"
    shutil.copytree(E.R1_DIR, copy)
    monkeypatch.setattr(E, "R1_DIR", copy)
    monkeypatch.setattr(E, "LOCK", copy / "registration.lock.json")
    E.verify_registration()
    p = copy / "interview_cases.json"
    p.write_text(p.read_text().replace("Python", "Python3", 1))                                           # an expectation changed after registration
    with pytest.raises(G.LiveRunRefused) as e:
        E.verify_registration()
    assert e.value.reason == "dataset_changed_after_registration"


# ============================================================================================================================ interview harness
def test_the_interview_dataset_covers_the_required_role_families_with_every_expectation_fixed():
    doc = E.load_interview_cases()
    fams = {c["role_family"] for c in doc["cases"]}
    assert {"Technology", "Finance", "Operations", "Sales", "Customer service", "People and HR", "Marketing"} <= fams and len(doc["cases"]) == 7 and doc["calls_per_case"] == 2
    assert doc["thresholds"].startswith("none") and "feedback_usefulness" in doc["pending_human_review"] and "bias_sensitivity" in doc["pending_human_review"]
    for c in doc["cases"]:
        cfg = E.interview_configuration(c)                                                                 # valid against the product's own input model
        assert cfg.target_role == c["target_role"]
        for f in ("job_description", "candidate_background", "candidate_answer", "role_keywords", "answer_facts", "forbidden_inventions", "interview_types"):
            assert c[f]
        assert "synthetic" in c["candidate_background"].lower()                                           # synthetic personas only
        assert not any(f.lower() in c["candidate_answer"].lower() for f in c["forbidden_inventions"])    # the answer never contains what the feedback must not invent


def _q(**o):
    base = dict(question="Tell me about a time you reduced API latency in a Python service?", question_type="technical", competency="Performance engineering", interviewer_intent="Look for database and caching work.")
    base.update(o)
    return SimpleNamespace(**base)


def _ev(**o):
    base = dict(strengths=["You added indexes and caching to cut latency."], improvement_areas=["Quantify the latency improvement."], missing_evidence=["No measured numbers were given."],
                stronger_answer_structure="Situation, action, measured result.", improved_example_answer="Illustrative: I reduced p95 latency by indexing.", follow_up_question="How did you measure the improvement?")
    base.update(o)
    return SimpleNamespace(**base)


def test_deterministic_checks_pass_and_fail_for_the_right_reasons():
    doc = E.load_interview_cases()
    case = doc["cases"][0]
    assert all(E.check_question(case, _q()).values()) and all(E.check_evaluation(case, doc, _ev()).values())
    bad_q = E.check_question(case, _q(question="Describe your work", question_type="culture_values", competency="x", interviewer_intent="y"))
    assert bad_q == {"question_is_a_question": False, "question_type_requested": False, "question_role_keyword": False}
    assert not E.check_evaluation(case, doc, _ev(strengths=["You used Kubernetes well."]))["no_invented_candidate_experience"]
    assert not E.check_evaluation(case, doc, _ev(missing_evidence=[]))["evaluation_has_missing_evidence_when_gap_designed"]
    assert not E.check_evaluation(case, doc, _ev(strengths=["Good work."], improvement_areas=["Add detail."], missing_evidence=["Numbers."]))["evaluation_references_answer_content"]
    assert not E.check_evaluation(case, doc, _ev(follow_up_question="Tell me more."))["follow_up_is_a_question"]
    assert not E.check_evaluation(case, doc, _ev(improvement_areas=["We should hire this candidate."]))["no_hiring_decision"]
    assert not E.check_evaluation(case, doc, _ev(strengths=["A great fit for a young team."]))["no_biased_wording"]
    assert E.check_evaluation(case, doc, _ev(strengths=["You showed ownership."] + ["You used caching."]))["no_biased_wording"]       # "her/his" substrings do not false-trigger


class FakeInterview:
    def __init__(self, fail_on=None): self.calls, self.fail_on = 0, fail_on
    def generate_next_question(self, cfg, settings, *, current_question_number):
        self.calls += 1
        if self.fail_on and cfg.target_role == self.fail_on: raise RuntimeError("service failed")
        return _q(), None


class FakeEvaluation:
    def evaluate_answer(self, cfg, question, answer, settings):
        ev = _ev(strengths=["You added indexes and caching to cut latency; tests and alerts were covered."])
        ev.model_dump = lambda: {"strengths": ev.strengths}
        return ev, None


def test_the_interview_runner_reports_per_case_checks_a_review_packet_and_never_rates_anything(tmp_path):
    d, g = make_ledger(tmp_path)
    ev = tmp_path / "evidence"; ev.mkdir()
    q = _q(); q.model_dump = lambda: {"question": q.question}
    class FI(FakeInterview):
        def generate_next_question(self, cfg, settings, *, current_question_number):
            return q, None
    with session(tmp_path, d, g) as s:
        out = E.run_interview_quality(s, "balanced", only=["ie-software-engineer"], services=(FI(), FakeEvaluation()), base=ev)
    r = out["results"]
    assert r["cases_completed"] == 1 and r["thresholds"].startswith("none") and "no human or AI judge" in r["note"]
    packet = json.loads((Path(out["run_dir"]) / "review_packet.json").read_text())
    assert packet["reviewer"] is None and all(v["status"] == "PENDING_HUMAN_REVIEW" and v["rating"] is None for c in packet["cases"] for v in c["human_ratings"].values())
    meta = json.loads((Path(out["run_dir"]) / "meta.json").read_text())
    assert meta["dataset_sha256"] == E.verify_registration()["interview_cases.json"] and meta["ledger_genesis_id"] == g and meta["calls_per_case_planned"] == 2


def test_a_service_failure_is_a_controlled_category_and_the_run_continues(tmp_path):
    d, g = make_ledger(tmp_path)
    ev = tmp_path / "evidence"; ev.mkdir()
    q = _q(); q.model_dump = lambda: {"question": q.question}
    class FI(FakeInterview):
        def generate_next_question(self, cfg, settings, *, current_question_number):
            if cfg.target_role == "Financial Analyst": raise RuntimeError("boom Authorization: Bearer sk-or-SECRETSECRETSECRET")
            return q, None
    with session(tmp_path, d, g) as s:
        out = E.run_interview_quality(s, "balanced", only=["ie-software-engineer", "ie-finance-analyst"], services=(FI(), FakeEvaluation()), base=ev)
    r = out["results"]
    assert r["cases_completed"] == 1 and r["cases_not_completed"][0]["status"] == "FAILED" and r["cases_not_completed"][0]["error_category"] == "RuntimeError"
    assert "sk-or" not in json.dumps(out)                                                                  # provider or exception text is never recorded


# ============================================================================================================================ multilingual corpus
def test_the_multilingual_corpus_is_registered_validated_and_excludes_russian():
    doc = E.load_multilingual_cases()
    assert E.validate_multilingual(doc) == [] and set(doc["languages"]) == {"en", "de", "fr", "es", "it", "pt", "nl"} and "ru" in doc["excluded_languages"] and "ru" not in doc["languages"]
    assert len(doc["cases"]) == 14 and set(doc["priority_languages"]) == {"es", "it", "pt", "nl"} and set(doc["controls"]) == {"en", "de", "fr"}
    assert doc["thresholds"].startswith("none") and "never averaged" in doc["thresholds"]
    for c in doc["cases"]:
        assert c["geography"] and c["evidence_availability"] and c["expected_behaviour"] and c["citation_boundary"] and c["acceptable_outcomes"]
    bad = json.loads(json.dumps(doc)); bad["languages"].append("ru")
    assert E.validate_multilingual(bad)


SENTENCES = {"en": "The role is defined in the knowledge base and the evidence does not cover that question.", "de": "Die Rolle ist in der Wissensbasis nicht beschrieben und es gibt keine Belege für diese Frage.",
             "fr": "Les sources ne contiennent pas des informations pour cette question dans la base de connaissances.", "es": "Los datos de la base de conocimiento no incluyen una respuesta para esta pregunta.",
             "it": "Le fonti della base di conoscenza non contengono una risposta per questa domanda e non sono sufficienti.", "pt": "Os dados da base de conhecimento não incluem uma resposta para esta pergunta e não são suficientes.",
             "nl": "De bronnen in de kennisbank bevatten geen antwoord op deze vraag en het bewijs is niet voldoende."}


@pytest.mark.parametrize("lang", sorted(SENTENCES))
def test_the_language_proxy_identifies_each_supported_language_on_fixed_sentences(lang):
    assert E.detect_language(SENTENCES[lang])["language"] == lang
    assert E.detect_language("")["language"] is None and E.detect_language("12345 ???")["language"] is None


def test_the_deterministic_answer_checks_flag_figures_citations_and_wrong_language():
    doc = E.load_multilingual_cases()
    unsupported = next(c for c in doc["cases"] if c["id"] == "ml-es-unsupported-country")
    ok = E.check_multilingual_answer(unsupported, SENTENCES["es"], 0, 0)
    assert ok["answer_language_matches"] and ok["no_salary_figure_invented"] and ok["no_citation_for_unsupported"] and ok["outcome"] == "abstained"
    bad = E.check_multilingual_answer(unsupported, "El salario es de $85,000 al año [1].", 1, 1)
    assert not bad["no_salary_figure_invented"] and not bad["no_citation_for_unsupported"]
    assert not E.check_multilingual_answer(unsupported, SENTENCES["de"], 0, 0)["answer_language_matches"]                       # a German answer to a Spanish question is flagged
    assert bad["outcome"] == "answered_with_citation"
    supported = next(c for c in doc["cases"] if c["id"] == "ml-de-supported")
    c2 = E.check_multilingual_answer(supported, SENTENCES["de"] + " [3]", 2, 1)
    assert not c2["citation_markers_valid"]                                                              # marker [3] with only two evidence items is invalid grounding
    assert E.check_multilingual_answer(supported, SENTENCES["de"] + " [2]", 2, 1)["citation_markers_valid"]


def test_the_offline_measurement_is_free_covers_every_language_and_reports_the_cross_language_gap():
    out = E.multilingual_offline()
    assert out["no_model_call"] is True and set(out["per_language"]) == {"en", "de", "fr", "es", "it", "pt", "nl"}
    en = out["per_language"]["en"]["supported_occupation_definition"]
    assert en["retrieved_role_document"] is True
    for lang, v in out["per_language"].items():
        assert v["unsupported_country_compensation"]["retrieved_compensation_for_canada"] is False and v["unsupported_country_compensation"]["resolved_country"] == "CA"


def test_the_live_multilingual_runner_reports_each_language_separately_and_never_an_average(tmp_path):
    d, g = make_ledger(tmp_path)
    ev = tmp_path / "evidence"; ev.mkdir()
    t = Transport(lambda req, n: httpx.Response(200, json={**_ok_body(), "choices": [{"index": 0, "message": {"role": "assistant", "content": SENTENCES["es"]}, "finish_reason": "stop"}]}))
    with session(tmp_path, d, g) as s:
        out = E.run_multilingual_live(s, "balanced", only=["ml-es-supported", "ml-es-unsupported-country", "ml-nl-supported"], build=lambda slug: chat(t, model=slug), base=ev)
    r = out["results"]
    assert r["cases_completed"] == 3 and set(r["per_language"]) == {"es", "nl"} and "never averaged" in r["note"] or "never averaged" in r["thresholds"]
    assert not any(k in json.dumps(r) for k in ("average", "overall_score", "global_score")) or "never averaged" in r["note"]
    assert r["per_language"]["es"]["unsupported_country_compensation"]["no_salary_figure_invented"] is True
    assert r["per_language"]["nl"]["supported_occupation_definition"]["answer_language_matches"] is False                 # a Spanish answer to a Dutch question is reported as such, per language
    packet = json.loads((Path(out["run_dir"]) / "review_packet.json").read_text())
    assert packet["reviewer"] is None and all(v["status"] == "PENDING_HUMAN_REVIEW" for c in packet["cases"] for v in c["human_ratings"].values())
