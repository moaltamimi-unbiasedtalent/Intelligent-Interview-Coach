"""06C (LG-05, REQ-LANG-04): interview scoring and evaluation are language-independent. Offline, deterministic, no provider call.

What is proved (see ``src/language_quality/invariance.py`` for the claim and the tolerance):

* the real ``EvaluationService`` and ``ReportService`` pipelines, driven by a content-aware FAKE provider, send the same rubric, the same scoring rules, the same request parameters and
  the same user-message frame in every language, and return identical evaluations, usage records and aggregates for the same fake model output. Tolerance: exactly zero.
* the offline report fails when a language differs by even one point, and the live report refuses a verdict without live scores and without OWNER-APPROVED thresholds.

What is NOT proved: that a real model grades an answer and its translation alike. That needs the owner's budget marker and is recorded as NOT RUN.
"""

from __future__ import annotations

import json

import pytest

from src import constants, prompts
from src.coaching_style import COACHING_STYLES
from src.evaluation_service import EvaluationService
from src.language_quality import invariance as INV
from src.llm import models as _registry  # noqa: F401  (registry import keeps model resolution identical to production)
from src.models import InterviewConfiguration, InterviewQuestion, ModelSettings
from src.openrouter_client import ChatResult
from src.pricing_service import PricingService
from src.report_service import ReportService

PAIRS, LANGS = INV.load_pairs()
MODEL = constants.DEFAULT_MODEL
_REF_Q, _REF_A = "[interview_question]\n", "[candidate_answer]\n"


class ScoringFake:
    """A provider fake that is content-aware but language-blind: it finds which pair the candidate answer belongs to and returns that pair's reference scores, whatever the language."""

    def __init__(self):
        self.calls: list[dict] = []
        self._by_answer = {text: p for p in PAIRS for text in p.answer.values()}

    def create_chat_completion(self, **kwargs) -> ChatResult:
        self.calls.append(kwargs)
        user = kwargs["messages"][-1]["content"]
        pair = next(p for text, p in self._by_answer.items() if text in user)
        body = dict(pair.reference_scores, strengths=["clear"], improvement_areas=["add detail"], missing_evidence=["numbers"], stronger_answer_structure="Situation, action, result.",
                    improved_example_answer="An improved example.", follow_up_question="What was the result?")
        return ChatResult(content=json.dumps(body), model=kwargs["model"], prompt_tokens=100, completion_tokens=50, total_tokens=150, reported_cost=0.001, duration_seconds=0.5,
                          request_id="gen-test")


def _pricing(strict: bool) -> PricingService:
    params = ["structured_outputs", "response_format", "max_tokens"] if strict else ["temperature", "max_tokens", "response_format"]
    return PricingService(models_fetcher=lambda: [{"id": MODEL, "pricing": {"prompt": "0.0000006", "completion": "0.0000018"}, "supported_parameters": params}])


def _config(lang: str, **over) -> InterviewConfiguration:
    base = dict(target_role="Registered Nurse", industry_or_sector="healthcare", career_level="senior", interview_types=["behavioural"], interviewer_persona="neutral",
                difficulty="moderate", response_detail="standard", conversation_language=lang)
    base.update(over)
    return InterviewConfiguration(**base)


def _settings() -> ModelSettings:
    return ModelSettings(model=MODEL, prompt_technique="rubric_json")


def _run_all(strict: bool, **config_over):
    """Evaluate every (pair, language) through the real service. Returns {lang: {pair id: (evaluation, usage, call)}}."""
    out: dict[str, dict[str, tuple]] = {lang: {} for lang in LANGS}
    for lang in LANGS:
        for pair in PAIRS:
            client = ScoringFake()
            service = EvaluationService(client, _pricing(strict))
            evaluation, usage = service.evaluate_answer(_config(lang, **config_over), pair.question[lang], pair.answer[lang], _settings())
            assert len(client.calls) == 1
            out[lang][pair.id] = (evaluation, usage, client.calls[0])
    return out


@pytest.fixture(scope="module", params=[True, False], ids=["strict_schema_path", "defensive_path"])
def runs(request):
    return request.param, _run_all(request.param)


def _scores(runs_):
    return {lang: {pid: INV.scores_of(v[0]) for pid, v in by_pair.items()} for lang, by_pair in runs_.items()}


# ------------------------------------------------------------------------------------------------------------------------------------- fixtures
def test_the_pair_fixture_is_complete_synthetic_and_ordered_by_quality():
    assert LANGS == ("en", "de", "fr", "es", "it", "pt", "nl") and len(PAIRS) == 4
    by_level = {p.level: p.reference_scores["overall_score"] for p in PAIRS}
    assert by_level["strong"] > by_level["medium"] > by_level["weak"] > by_level["off_topic"]
    for p in PAIRS:
        for lang in LANGS[1:]:
            assert p.answer[lang] != p.answer["en"] and p.question[lang] != p.question["en"]      # a real translation, not a copy of the English text
        assert all(1 <= p.reference_scores[k] <= 10 for k in INV.RUBRIC_FIELDS) and 0 <= p.reference_scores["overall_score"] <= 100


# --------------------------------------------------------------------------------------------------------------------------------- service path
def test_scores_and_evaluations_are_identical_across_languages_with_zero_tolerance(runs):
    _, results = runs
    report = INV.offline_invariance_report(_scores(results))
    assert report.status == "WITHIN_TOLERANCE" and report.max_overall_delta == 0 and report.max_rubric_delta == 0
    assert report.pairs == len(PAIRS) and set(report.languages) == set(LANGS)
    for pair in PAIRS:
        base_eval, base_usage, _ = results["en"][pair.id]
        assert INV.scores_of(base_eval) == dict(pair.reference_scores)                  # the code never rescales or clamps what the model returned
        for lang in LANGS:
            evaluation, usage, _ = results[lang][pair.id]
            assert evaluation == base_eval                                              # the whole evaluation object, not only the numbers
            assert usage == base_usage


def test_the_request_the_model_receives_differs_only_by_the_directive_and_the_data(runs):
    _, results = runs
    for pair in PAIRS:
        _, _, base_call = results["en"][pair.id]
        base_sys = base_call["messages"][0]["content"]
        base_user = base_call["messages"][-1]["content"]
        for lang in LANGS[1:]:
            _, _, call = results[lang][pair.id]
            directive = prompts._language_directive(_config(lang))
            sysprompt = call["messages"][0]["content"]
            assert sysprompt.replace("\n\n" + directive, "", 1) == base_sys             # rubric and rules: byte-identical in every language
            user = call["messages"][-1]["content"].replace(pair.question[lang], "<Q>").replace(pair.answer[lang], "<A>")
            assert user == base_user.replace(pair.question["en"], "<Q>").replace(pair.answer["en"], "<A>")      # frame and DATA labels identical; only Q and A text differ
            assert {k: v for k, v in call.items() if k != "messages"} == {k: v for k, v in base_call.items() if k != "messages"}   # same model, temperature, tokens, response format


def test_the_strict_schema_is_the_same_object_in_every_language():
    results = _run_all(True)
    formats = {json.dumps(v[2]["response_format"], sort_keys=True) for by_pair in results.values() for v in by_pair.values()}
    assert len(formats) == 1                                                            # one strict JSON Schema; the language never changes the shape or the score bounds
    schema = next(iter(results["en"].values()))[2]["response_format"]["json_schema"]["schema"]
    props = schema["properties"]
    assert (props["overall_score"]["minimum"], props["overall_score"]["maximum"]) == (constants.MIN_OVERALL_SCORE, constants.MAX_OVERALL_SCORE)
    assert (props["relevance"]["minimum"], props["relevance"]["maximum"]) == (constants.MIN_RUBRIC_SCORE, constants.MAX_RUBRIC_SCORE)


@pytest.mark.parametrize("style", COACHING_STYLES)
def test_a_coaching_style_changes_neither_the_scores_nor_the_scoring_request_in_any_language(style):
    base = _run_all(True)
    styled = _run_all(True, coaching_style=style)
    assert INV.offline_invariance_report(_scores(styled)).status == "WITHIN_TOLERANCE"
    for lang in LANGS:
        for pid in base[lang]:
            assert INV.scores_of(styled[lang][pid][0]) == INV.scores_of(base[lang][pid][0])
            b, s = base[lang][pid][2], styled[lang][pid][2]
            assert {k: v for k, v in s.items() if k != "messages"} == {k: v for k, v in b.items() if k != "messages"}
            assert s["messages"][-1] == b["messages"][-1]                               # the DATA message is untouched; only trusted system wording may differ


def test_the_report_input_built_from_evaluations_is_identical_across_languages():
    captured: dict[str, str] = {}
    for lang in LANGS:
        evaluations = [_run_one(lang, p) for p in PAIRS]
        questions = [InterviewQuestion(question_id=i + 1, question=p.question[lang], question_type="behavioural", competency="teamwork", difficulty="moderate",
                                       interviewer_intent="See how they respond.", expected_answer_elements=["situation", "action", "result"]) for i, p in enumerate(PAIRS)]
        report_json = json.dumps({"overall_readiness_score": 61, "performance_summary": "Summary.", "strongest_competencies": ["a"], "development_priorities": ["b"],
                                  "recurring_answer_patterns": ["c"], "highest_risk_questions": ["d"], "evidence_gaps": ["e"], "recommended_practice_actions": ["f"],
                                  "final_interview_checklist": ["g"]})

        class _Client:
            def create_chat_completion(self, **kwargs):
                captured[lang] = kwargs["messages"][-1]["content"]
                return ChatResult(content=report_json, model=kwargs["model"], prompt_tokens=10, completion_tokens=10, total_tokens=20, reported_cost=None, duration_seconds=0.1,
                                  request_id="r")

        report, _ = ReportService(_Client(), _pricing(False)).generate_report(_config(lang), questions, [p.answer[lang] for p in PAIRS], evaluations, _settings())
        assert report.overall_readiness_score == 61
    assert set(captured) == set(LANGS)
    normalised = {}
    for lang, text in captured.items():
        for p in PAIRS:
            text = text.replace(p.question[lang], "<Q>").replace(p.answer[lang], "<A>")
        normalised[lang] = text
    assert len(set(normalised.values())) == 1                                           # same score summaries, same frame, in every language


def _run_one(lang, pair):
    return EvaluationService(ScoringFake(), _pricing(False)).evaluate_answer(_config(lang), pair.question[lang], pair.answer[lang], _settings())[0]


# ------------------------------------------------------------------------------------------------------------------------------------- the report
def _ok_scores():
    return {lang: {p.id: dict(p.reference_scores) for p in PAIRS} for lang in LANGS}


def test_the_offline_report_passes_on_equal_scores_and_fails_on_a_one_point_difference():
    assert INV.offline_invariance_report(_ok_scores()).status == "WITHIN_TOLERANCE"
    for field in ("overall_score", "relevance"):
        scores = _ok_scores()
        scores["fr"]["strong_star"][field] += 1
        report = INV.offline_invariance_report(scores)
        assert report.status == "EXCEEDS_TOLERANCE"
        assert report.worst[0]["language"] == "fr" and report.worst[0]["pair"] == "strong_star"


def test_the_offline_report_is_not_evaluated_without_comparable_rows():
    assert INV.offline_invariance_report({}).status == "NOT_EVALUATED"
    assert INV.offline_invariance_report({"en": _ok_scores()["en"]}).status == "NOT_EVALUATED"


def test_the_live_report_refuses_a_verdict_without_live_scores_or_approved_thresholds():
    none = INV.live_invariance_report(None, None)
    assert none.status == "NOT_EVALUATED" and "NOT RUN" in none.reason
    proposed = dict(INV.LIVE_TOLERANCE_PROPOSED)
    assert INV.live_invariance_report(_ok_scores(), proposed).status == "NOT_EVALUATED"          # the proposal is not an approval
    assert INV.live_invariance_report(_ok_scores(), {**proposed, "approved_by": "", "approved_on": ""}).status == "NOT_EVALUATED"
    assert "OWNER" not in INV.LIVE_TOLERANCE_PROPOSED["status"] and "NOT APPROVED" in INV.LIVE_TOLERANCE_PROPOSED["status"]


def test_the_live_report_applies_owner_approved_thresholds_when_they_exist():
    approved = {"overall_score_abs": 10, "rubric_abs": 1, "min_share_of_pairs_within": 0.9, "approved_by": "Named Approver", "approved_on": "2026-11-20"}
    scores = _ok_scores()
    scores["de"]["strong_star"]["overall_score"] -= 7                                   # within 10
    assert INV.live_invariance_report(scores, approved).status == "WITHIN_TOLERANCE"
    scores["de"]["strong_star"]["overall_score"] -= 20                                  # beyond 10 in 1 of 24 rows: share 23/24 = 0.958 still above 0.9
    assert INV.live_invariance_report(scores, approved).status == "WITHIN_TOLERANCE"
    for lang in ("de", "fr", "es"):
        scores[lang]["weak_generic"]["overall_score"] += 30
    assert INV.live_invariance_report(scores, approved).status == "EXCEEDS_TOLERANCE"


def test_the_noise_floor_measures_repeat_spread_and_needs_two_gradings():
    assert INV.noise_floor([{**INV.scores_of(dict(PAIRS[0].reference_scores)), "overall_score": 80}, dict(PAIRS[0].reference_scores)]) == {"overall_score": 5, "rubric": 0}
    with pytest.raises(ValueError):
        INV.noise_floor([dict(PAIRS[0].reference_scores)])


def test_the_scoring_code_path_contains_no_language_branch():
    # Static guard: the score-bearing code never reads the conversation language. A language-dependent score would need one of these names to appear there.
    import inspect
    import re
    from pathlib import Path

    from src import models

    pattern = re.compile(r"conversation_language|response_language|\blocale\b|LANGUAGE_NAMES")
    root = Path(__file__).resolve().parents[1]
    for rel in ("src/evaluation_service.py", "src/report_service.py", "src/response_parser.py", "src/application/progress_analytics.py"):
        text = (root / rel).read_text(encoding="utf-8")
        assert not pattern.search(re.sub(r'""".*?"""', "", text, flags=re.S)), rel
    for cls in (models.AnswerEvaluation, models.FinalInterviewReport, models._GeneratedModel):
        assert not pattern.search(inspect.getsource(cls)), cls.__name__
    assert not pattern.search(inspect.getsource(models._reject_bool_score))
