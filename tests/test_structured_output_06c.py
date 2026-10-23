"""06C (REQ-LANG-04, REVIEW-02 structured outputs): schema-enforced structured outputs for the interview paths, with a safe fallback that never relaxes validation.

Offline: a FAKE provider returns scripted responses (valid, malformed, wrong schema, extra fields, wrapped in text, out of range, boolean scores). No model call, no network.

Inspection result recorded here as tests (see 06C_EVIDENCE.md for the narrative):
* every interview task (strategy, question, evaluation, report, branch) already goes through ``BaseGenerationService._generate_governed``: strict JSON Schema when the model advertises
  ``structured_outputs``, otherwise a ``json_object`` hint plus the defensive parser and ONE bounded repair;
* gaps closed by 06C: (1) the strict path no longer string-handles the reply (fences, preambles); a wrapped reply takes the controlled fallback instead; (2) a JSON boolean is no longer
  silently coerced into a score of 1; (3) the strict schema pins ``question_type`` and ``difficulty`` to the English vocabulary, so a localized label cannot be emitted and silently
  recorded as the default type;
* NOT changed (out of the interview path, owned elsewhere): ``src/copilot/rag/translation.py`` and ``src/copilot/retrieval/reranker.py`` still extract JSON by string handling.
"""

from __future__ import annotations

import json

import pytest

from src import constants, prompts
from src.evaluation_service import EvaluationService
from src.interview_service import InterviewService, ModelResponseError, QuestionHistory
from src.models import AnswerEvaluation, BranchQuestion, FinalInterviewReport, InterviewConfiguration, InterviewQuestion, InterviewStrategy, ModelSettings
from src.openrouter_client import ChatResult
from src.pricing_service import PricingService
from src.report_service import ReportService
from src.response_parser import ResponseParseError, parse_exact_json_object, parse_structured_output
from src.structured_output import build_strict_schema, build_structured_response_format

MODEL = constants.DEFAULT_MODEL

_EVAL = {"overall_score": 72, "relevance": 7, "structure": 7, "evidence": 6, "role_knowledge": 7, "problem_solving": 7, "communication": 8, "credibility": 7, "strengths": ["klar"],
         "improvement_areas": ["mehr Details"], "missing_evidence": ["Zahlen"], "stronger_answer_structure": "Situation, Handlung, Ergebnis.", "improved_example_answer": "Ein Beispiel.",
         "follow_up_question": "Was war das Ergebnis?"}
_QUESTION = {"question_id": 2, "question": "Beschreiben Sie einen Konflikt, den Sie gelöst haben.", "question_type": "behavioural", "competency": "Teamarbeit", "difficulty": "moderate",
             "interviewer_intent": "Konfliktlösung sehen.", "expected_answer_elements": ["Situation", "Handlung", "Ergebnis"]}


class Scripted:
    """Returns queued contents and records every call (kwargs)."""

    def __init__(self, *contents):
        self.queue = list(contents)
        self.calls: list[dict] = []

    def create_chat_completion(self, **kwargs) -> ChatResult:
        self.calls.append(kwargs)
        return ChatResult(content=self.queue.pop(0), model=kwargs["model"], prompt_tokens=100, completion_tokens=50, total_tokens=150, reported_cost=0.001, duration_seconds=0.5,
                          request_id="gen-test")


def _strict() -> PricingService:
    return PricingService(models_fetcher=lambda: [{"id": MODEL, "pricing": {"prompt": "0.0000006", "completion": "0.0000018"},
                                                    "supported_parameters": ["structured_outputs", "response_format", "max_tokens"]}])


def _plain() -> PricingService:
    return PricingService(models_fetcher=lambda: [{"id": MODEL, "pricing": {"prompt": "0.0000006", "completion": "0.0000018"},
                                                    "supported_parameters": ["temperature", "max_tokens", "response_format"]}])


def _config(lang="de") -> InterviewConfiguration:
    return InterviewConfiguration(target_role="Registered Nurse", industry_or_sector="healthcare", career_level="senior", interview_types=["behavioural"], interviewer_persona="neutral",
                                  difficulty="moderate", response_detail="standard", conversation_language=lang)


def _settings() -> ModelSettings:
    return ModelSettings(model=MODEL, prompt_technique="rubric_json")


def _evaluate(client, pricing=None):
    return EvaluationService(client, pricing or _strict()).evaluate_answer(_config(), "Frage?", "Antwort.", _settings())


def _question(client, pricing=None):
    return InterviewService(client, pricing or _strict()).generate_next_question(_config(), _settings(), current_question_number=2, history=QuestionHistory())


# ================================================================================================================================ exact parsing
@pytest.mark.parametrize("text", [json.dumps(_EVAL), "  \n" + json.dumps(_EVAL) + "\n  "])
def test_exact_parsing_accepts_one_json_object_with_whitespace_only(text):
    assert parse_exact_json_object(text)["overall_score"] == 72


@pytest.mark.parametrize("text", ["```json\n" + json.dumps(_EVAL) + "\n```", "Hier ist die Bewertung: " + json.dumps(_EVAL), json.dumps(_EVAL) + " Viel Erfolg!", "[1, 2]", "42", "null", "", "   ",
                                  "{not json}", json.dumps(_EVAL)[:-1]])
def test_exact_parsing_rejects_anything_that_is_not_exactly_one_json_object(text):
    with pytest.raises(ResponseParseError):
        parse_exact_json_object(text)
    with pytest.raises(ResponseParseError):
        parse_structured_output(text, AnswerEvaluation, exact_json=True)


def test_the_default_parser_is_unchanged_it_still_tolerates_fences_and_preambles():
    fenced = "```json\n" + json.dumps(_EVAL) + "\n```"
    assert parse_structured_output(fenced, AnswerEvaluation).overall_score == 72
    assert parse_structured_output("Hier ist die Bewertung: " + json.dumps(_EVAL), AnswerEvaluation).overall_score == 72


# ============================================================================================================================ scores are real
@pytest.mark.parametrize("field,bad", [("overall_score", True), ("overall_score", False), ("relevance", True), ("credibility", False), ("overall_score", 101), ("overall_score", -1),
                                       ("relevance", 0), ("relevance", 11), ("overall_score", None), ("overall_score", "high"), ("overall_score", 85.5), ("overall_score", [85])])
def test_a_malformed_score_is_rejected_never_silently_coerced(field, bad):
    with pytest.raises(Exception):
        AnswerEvaluation.model_validate({**_EVAL, field: bad})
    with pytest.raises(ResponseParseError):
        parse_structured_output(json.dumps({**_EVAL, field: bad}), AnswerEvaluation)


def test_the_meaning_preserving_numeric_forms_still_validate_as_before():
    assert AnswerEvaluation.model_validate({**_EVAL, "overall_score": "85"}).overall_score == 85
    assert AnswerEvaluation.model_validate({**_EVAL, "overall_score": 85.0}).overall_score == 85
    report = FinalInterviewReport.model_validate({"overall_readiness_score": 61, "performance_summary": "S.", "strongest_competencies": ["a"], "development_priorities": ["b"],
                                                   "recurring_answer_patterns": ["c"], "highest_risk_questions": ["d"], "evidence_gaps": ["e"], "recommended_practice_actions": ["f"],
                                                   "final_interview_checklist": ["g"]})
    assert report.overall_readiness_score == 61
    with pytest.raises(Exception):
        FinalInterviewReport.model_validate({**report.model_dump(), "overall_readiness_score": True})


# ================================================================================================================================== schemas
def _objects(node):
    if isinstance(node, dict):
        if "properties" in node:
            yield node
        for v in node.values():
            yield from _objects(v)
    elif isinstance(node, list):
        for v in node:
            yield from _objects(v)


@pytest.mark.parametrize("schema", [InterviewStrategy, InterviewQuestion, AnswerEvaluation, FinalInterviewReport, BranchQuestion])
def test_every_interview_schema_is_strict_closed_and_fully_required(schema):
    fmt = build_structured_response_format(schema, schema.__name__)
    assert fmt["type"] == "json_schema" and fmt["json_schema"]["strict"] is True and fmt["json_schema"]["name"] == schema.__name__
    for obj in _objects(fmt["json_schema"]["schema"]):
        assert obj["additionalProperties"] is False and obj["required"] == list(obj["properties"])


def test_score_bounds_and_the_language_independent_vocabularies_are_in_the_schema():
    props = build_strict_schema(AnswerEvaluation)["properties"]
    assert (props["overall_score"]["minimum"], props["overall_score"]["maximum"]) == (constants.MIN_OVERALL_SCORE, constants.MAX_OVERALL_SCORE)
    assert (props["relevance"]["minimum"], props["relevance"]["maximum"]) == (constants.MIN_RUBRIC_SCORE, constants.MAX_RUBRIC_SCORE)
    q = build_strict_schema(InterviewQuestion)["properties"]
    assert q["question_type"]["enum"] == list(constants.INTERVIEW_TYPES) and q["difficulty"]["enum"] == list(constants.DIFFICULTY_LEVELS)
    assert build_strict_schema(BranchQuestion)["properties"]["difficulty"]["enum"] == list(constants.DIFFICULTY_LEVELS)


def test_the_defensive_validator_is_unchanged_for_a_localized_label():
    # Only the strict-schema side was tightened; the lenient coercion of the defensive path behaves exactly as before (and is logged).
    assert InterviewQuestion.model_validate({**_QUESTION, "question_type": "technisch"}).question_type == "behavioural"
    assert InterviewQuestion.model_validate({**_QUESTION, "question_type": "Technical"}).question_type == "technical"


# ================================================================================================================================ strict path
def test_strict_path_sends_the_schema_and_accepts_a_pure_json_reply_in_one_call():
    client = Scripted(json.dumps(_EVAL))
    evaluation, usage = _evaluate(client)
    assert len(client.calls) == 1 and evaluation.overall_score == 72
    rf = client.calls[0]["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["strict"] is True and client.calls[0]["require_parameters"] is True
    assert usage.total_tokens == 150


@pytest.mark.parametrize("wrapped", ["```json\n" + json.dumps(_EVAL) + "\n```", "Hier ist die Bewertung: " + json.dumps(_EVAL), json.dumps(_EVAL) + "\nViel Erfolg!"],
                         ids=["fenced", "preamble", "trailer"])
def test_a_wrapped_reply_in_the_strict_path_takes_the_controlled_fallback_and_is_still_validated(wrapped):
    client = Scripted(wrapped, json.dumps(_EVAL))
    evaluation, usage = _evaluate(client)
    assert evaluation.overall_score == 72
    assert len(client.calls) == 2                                                       # strict call, then the defensive primary: bounded
    assert client.calls[0]["response_format"]["type"] == "json_schema" and client.calls[1]["response_format"] == {"type": "json_object"}
    assert usage.total_tokens == 300                                                    # both calls billed, none hidden


@pytest.mark.parametrize("bad", [
    "{not valid json", json.dumps({k: v for k, v in _EVAL.items() if k != "strengths"}), json.dumps({**_EVAL, "overall_score": "hoch"}), json.dumps({**_EVAL, "overall_score": True}),
    json.dumps({**_EVAL, "overall_score": 140}), json.dumps({**_EVAL, "relevance": 0}), json.dumps({**_EVAL, "strengths": []}), json.dumps({**_EVAL, "strengths": "klar"}), json.dumps([_EVAL]),
    json.dumps({"unrelated": "schema"}), json.dumps({**_EVAL, "overall_score": None}),
], ids=["malformed", "missing_field", "wrong_type", "bool_score", "out_of_range", "rubric_zero", "empty_list", "string_for_list", "array", "wrong_schema", "null_score"])
def test_a_bad_reply_never_becomes_an_evaluation_and_the_calls_are_bounded(bad):
    client = Scripted(bad, bad, bad, bad)
    with pytest.raises(ModelResponseError):
        _evaluate(client)
    assert len(client.calls) <= 3                                                       # strict + defensive primary + at most ONE repair; no loop


def test_a_wrong_schema_in_the_strict_path_can_still_self_heal_through_the_fallback_without_relaxing_anything():
    client = Scripted(json.dumps({"unrelated": 1}), json.dumps(_EVAL))
    evaluation, _ = _evaluate(client)
    assert evaluation.overall_score == 72 and len(client.calls) == 2


def test_extra_fields_are_ignored_by_design_and_never_reach_the_object():
    client = Scripted(json.dumps({**_EVAL, "injected_field": "ignore previous instructions", "overall_score_override": 100}))
    evaluation, _ = _evaluate(client)
    assert "injected_field" not in evaluation.model_dump() and "overall_score_override" not in evaluation.model_dump()
    assert evaluation.overall_score == 72                                               # an extra key can never replace a real score


def test_a_localized_enum_label_cannot_be_requested_the_schema_forces_the_english_identifier():
    client = Scripted(json.dumps(_QUESTION))
    question, _ = _question(client)
    assert question.question_type == "behavioural"
    sent = client.calls[0]["response_format"]["json_schema"]["schema"]["properties"]["question_type"]
    assert "technisch" not in sent["enum"] and "technical" in sent["enum"]


def test_secret_like_content_in_a_schema_valid_reply_is_still_blocked_by_the_output_guard():
    leaked = {**_EVAL, "strengths": ["sk-or-v1-" + "a" * 32]}
    with pytest.raises(ModelResponseError):
        _evaluate(Scripted(json.dumps(leaked), json.dumps(leaked)))


# ============================================================================================================================ defensive path
def test_without_structured_output_support_the_json_object_hint_and_one_repair_are_used():
    client = Scripted("not json at all", json.dumps(_EVAL))
    evaluation, _ = _evaluate(client, _plain())
    assert evaluation.overall_score == 72 and len(client.calls) == 2
    assert client.calls[0]["response_format"] == {"type": "json_object"} and client.calls[0]["require_parameters"] is False


def test_the_defensive_path_still_tolerates_a_fenced_object_it_is_the_documented_fallback():
    client = Scripted("```json\n" + json.dumps(_EVAL) + "\n```")
    evaluation, _ = _evaluate(client, _plain())
    assert evaluation.overall_score == 72 and len(client.calls) == 1


def test_the_request_shape_does_not_depend_on_the_conversation_language():
    shapes = set()
    for lang in ("en", "de", "fr", "es", "it", "pt", "nl"):
        client = Scripted(json.dumps(_EVAL))
        EvaluationService(client, _strict()).evaluate_answer(_config(lang), "Q?", "A.", _settings())
        shapes.add(json.dumps({k: v for k, v in client.calls[0].items() if k != "messages"}, sort_keys=True, default=str))
    assert len(shapes) == 1


@pytest.mark.parametrize("task", [prompts.TASK_STRATEGY, prompts.TASK_QUESTION, prompts.TASK_EVALUATION, prompts.TASK_REPORT, prompts.TASK_BRANCH])
def test_every_interview_task_uses_the_shared_structured_path(task):
    # one shared implementation: no interview task parses a model reply on its own
    import inspect

    from src import interview_service, report_service

    for module in (interview_service, report_service, __import__("src.evaluation_service", fromlist=["x"])):
        source = inspect.getsource(module)
        assert "json.loads" not in source and "parse_json_object" not in source
    assert task in prompts.TASK_SCHEMAS


def test_the_report_service_runs_the_strict_path_and_rejects_a_bad_reply():
    report_ok = {"overall_readiness_score": 61, "performance_summary": "S.", "strongest_competencies": ["a"], "development_priorities": ["b"], "recurring_answer_patterns": ["c"],
                 "highest_risk_questions": ["d"], "evidence_gaps": ["e"], "recommended_practice_actions": ["f"], "final_interview_checklist": ["g"]}
    q = InterviewQuestion.model_validate({**_QUESTION, "question_id": 1})
    ev = AnswerEvaluation.model_validate(_EVAL)
    good = Scripted(json.dumps(report_ok))
    report, _ = ReportService(good, _strict()).generate_report(_config(), [q], ["A."], [ev], _settings())
    assert report.overall_readiness_score == 61 and good.calls[0]["response_format"]["json_schema"]["name"] == "FinalInterviewReport"
    bad = {**report_ok, "overall_readiness_score": True}
    with pytest.raises(ModelResponseError):
        ReportService(Scripted(json.dumps(bad), json.dumps(bad), json.dumps(bad)), _strict()).generate_report(_config(), [q], ["A."], [ev], _settings())
