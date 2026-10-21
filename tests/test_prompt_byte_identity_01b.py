"""01B byte-identity proof: every migrated prompt renders EXACTLY as the former code literal.

The oracle is ``tests/fixtures/legacy_prompts/`` : verbatim copies of the pre-migration modules
(frozen at the 01B0 base commit). Each test compares the live, asset-backed consumer with the legacy
one over every family and every branch (techniques x tasks x languages x coaching styles x config
variations), plus pinned SHA-256 digests of the default static prompts so editing the oracle alone
cannot hide a drift. No provider or network call.
"""

from __future__ import annotations

import hashlib
import itertools
import json

import pytest

from src import coaching_style as new_cs
from src import constants
from src import prompts as new_lp
from src.agent import judge as new_judge
from src.agent import policies as new_ap
from src.copilot.rag import prompts as new_rp
from src.copilot.rag import synthesis as new_rs
from src.copilot.rag import translation as new_rt
from src.copilot.tools import job_analyzer as new_ja
from src.copilot.tools import question_generator as new_qg
from src.copilot.tools.schemas import JobAnalyzerArgs, QuestionGeneratorArgs
from src.locales import LANGUAGE_NAMES
from src.models import InterviewConfiguration
from tests.fixtures.legacy_prompts import legacy_agent_policies as old_ap
from tests.fixtures.legacy_prompts import legacy_coaching_style as old_cs
from tests.fixtures.legacy_prompts import legacy_interview_prompts as old_lp
from tests.fixtures.legacy_prompts import legacy_job_analyzer as old_ja
from tests.fixtures.legacy_prompts import legacy_judge as old_judge
from tests.fixtures.legacy_prompts import legacy_question_generator as old_qg
from tests.fixtures.legacy_prompts import legacy_rag_prompts as old_rp
from tests.fixtures.legacy_prompts import legacy_rag_synthesis as old_rs
from tests.fixtures.legacy_prompts import legacy_rag_translation as old_rt

# Pinned digests of the pre-migration static prompt text (independent of the oracle copies).
PINNED = {
    "agent_system": "72f03d8133c345f22e873418b8fb84718967625f539782cecf0df9b953c95a6e",
    "judge_system": "0d230bbc2e4aaf669aae3074b3c002f143b8ef35883f448460dfb92982b7ac94",
    "synthesis_template": "1de2487c2457486342f241412625b79983a871f81c0d7eae2a4c68625ae88b53",
    "job_analysis": "4cc3da88efd5355614bae244b86bc55c28f368afb5fbe258a084c182eb4be837",
    "question_generation_template": "8dbf2c040195f057d862397f52146b596bec2b3804d905d865823bc521f472e4",
    "rag_baseline_rendered": "107088adc88007647004ebf7549485551a3e359273d9f88b89475ac547506c73",
}


def _h(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cfg(**overrides) -> InterviewConfiguration:
    base = {
        "target_role": "Registered Nurse", "industry_or_sector": "healthcare", "career_level": "senior",
        "interview_types": ["behavioural", "situational"], "interviewer_persona": "challenging",
        "difficulty": "hard", "response_detail": "detailed",
    }
    base.update(overrides)
    return InterviewConfiguration(**base)


CONFIGS = [_cfg()] + [
    _cfg(interviewer_persona=p, difficulty=d, response_detail=r, career_level=lvl, number_of_questions=n,
         interview_types=types, job_description="JD {braces} and {0}", company_context="Acme — café",
         candidate_background="x", conversation_language="de", coaching_style="direct")
    for p, d, r, lvl, n, types in (
        ("supportive", "easy", "brief", "internship", 3, ["screening"]),
        ("neutral", "moderate", "standard", "mid", 5, ["technical", "case_study"]),
        ("formal", "hard", "detailed", "executive", 8, list(constants.INTERVIEW_TYPES[:4])),
        ("sceptical_executive", "hard", "brief", "director", 4, ["leadership", "executive_board"]),
        ("fast_paced_panel", "moderate", "detailed", "lead", 6, ["panel"]),
    )
]
LANGS = [None, "", "en", "EN ", "xx", "'; DROP--", *LANGUAGE_NAMES]
STYLES = ["", "balanced", "supportive", "direct", "challenging", "Challenging ", "nope"]


# ---------------------------------------------------------------- agent --------------------------------
def test_agent_system_prompt_is_byte_identical_and_pinned():
    assert new_ap.SYSTEM_PROMPT == old_ap.SYSTEM_PROMPT
    assert _h(new_ap.SYSTEM_PROMPT) == PINNED["agent_system"]


@pytest.mark.parametrize("code", [None, "", " ", "en", "EN", "zz", "x'; --", "de ", *LANGUAGE_NAMES])
def test_agent_language_directive_every_branch(code):
    assert new_ap.response_language_directive(code) == old_ap.response_language_directive(code)


def test_agent_language_allowlist_is_unchanged():
    assert new_ap.RESPONSE_LANGUAGE_NAMES == old_ap.RESPONSE_LANGUAGE_NAMES


# ---------------------------------------------------------------- interview --------------------------------
@pytest.mark.parametrize("technique", list(constants.PROMPT_TECHNIQUES))
@pytest.mark.parametrize("config_index", range(len(CONFIGS)))
def test_five_technique_system_prompts_and_user_messages(technique, config_index):
    cfg = CONFIGS[config_index]
    assert new_lp.build_system_prompt(technique, cfg) == old_lp.build_system_prompt(technique, cfg)
    for question, answer in ((None, None), ("Q {x}?", None), ("Q", "A — {answer}\n{{y}}")):
        assert new_lp.build_user_message(cfg, question, answer) == old_lp.build_user_message(cfg, question, answer)
        assert new_lp.build_messages(technique, cfg, question, answer) == old_lp.build_messages(
            technique, cfg, question, answer)


def test_interview_static_pieces_and_tables_are_identical():
    assert new_lp._MISSION == old_lp._MISSION
    assert new_lp._GUARDRAILS == old_lp._GUARDRAILS
    assert new_lp._TASK == old_lp._TASK
    assert new_lp._PERSONA_TONE == old_lp._PERSONA_TONE
    assert new_lp._DIFFICULTY_RIGOUR == old_lp._DIFFICULTY_RIGOUR
    assert new_lp._RESPONSE_DETAIL_LENGTH == old_lp._RESPONSE_DETAIL_LENGTH
    assert new_lp._TASK_INSTRUCTIONS == old_lp._TASK_INSTRUCTIONS
    assert new_lp._TECHNIQUE_DIRECTIVES == old_lp._TECHNIQUE_DIRECTIVES
    assert new_lp._few_shot_example() == old_lp._few_shot_example()
    assert new_lp._output_contract() == old_lp._output_contract()
    assert new_lp.ANSWER_EVALUATION_KEYS == old_lp.ANSWER_EVALUATION_KEYS


@pytest.mark.parametrize("task", list(old_lp.TASK_SCHEMAS))
def test_task_output_contracts_per_schema(task):
    schema = old_lp.TASK_SCHEMAS[task]
    assert new_lp._output_contract_for(schema) == old_lp._output_contract_for(schema)


@pytest.mark.parametrize("task", list(old_lp.TASK_SCHEMAS))
@pytest.mark.parametrize("technique", list(constants.PROMPT_TECHNIQUES))
def test_task_system_prompts_every_language_and_style(task, technique):
    for cfg, lang, style in itertools.product(CONFIGS[:3], LANGS, STYLES):
        cfg = cfg.model_copy(update={"conversation_language": lang or "", "coaching_style": style})
        assert new_lp.build_task_system_prompt(task, technique, cfg) == old_lp.build_task_system_prompt(
            task, technique, cfg)


@pytest.mark.parametrize("task", list(old_lp.TASK_SCHEMAS))
def test_task_user_messages_every_argument_shape(task):
    shapes = [
        {},
        {"question": "Why {this}?", "candidate_answer": "Because — {x}"},
        {"previous_questions": ["a", "b"], "previous_answers": ["c"], "previous_evaluation_summaries": ["d", "e"],
         "question": "q", "candidate_answer": "a"},
        {"current_question_number": 4, "branch_mode": "challenge", "branch_depth": 3, "question": "q"},
        {"current_question_number": 0, "branch_mode": "", "branch_depth": 0},
        {"previous_questions": ["only"], "branch_mode": None, "branch_depth": None},
    ]
    for cfg, kw in itertools.product(CONFIGS[:4], shapes):
        assert new_lp.build_task_user_message(task, cfg, **kw) == old_lp.build_task_user_message(task, cfg, **kw)
        assert new_lp.build_task_messages(task, "few_shot", cfg, **kw) == old_lp.build_task_messages(
            task, "few_shot", cfg, **kw)


def test_interview_unknown_technique_and_task_still_fail_closed():
    cfg = CONFIGS[0]
    for fn in (lambda: new_lp.build_system_prompt("nope", cfg), lambda: new_lp.build_task_system_prompt("x", "zero_shot", cfg),
               lambda: new_lp.build_task_system_prompt("report", "nope", cfg)):
        with pytest.raises(ValueError):
            fn()


# ---------------------------------------------------------------- coaching --------------------------------
@pytest.mark.parametrize("code", [None, "", "balanced", "supportive", "direct", "challenging", "DIRECT ", "x", "zz"])
def test_coaching_style_directive(code):
    assert new_cs.coaching_style_directive(code) == old_cs.coaching_style_directive(code)
    assert new_cs._DIRECTIVES == old_cs._DIRECTIVES


# ---------------------------------------------------------------- RAG --------------------------------
def test_rag_baseline_prompts():
    assert new_rp.system_prompt() == old_rp.system_prompt()
    assert _h(new_rp.system_prompt()) == PINNED["rag_baseline_rendered"]
    assert new_rp._SYSTEM_PROMPT == old_rp._SYSTEM_PROMPT
    for q, ctx in (("What is {x}?", "[1] some {braces} — text"), ("q", ""), ("q", "   ")):
        assert new_rp.build_messages(q, ctx) == old_rp.build_messages(q, ctx)


def test_synthesis_template_and_messages_every_language():
    assert new_rs.SYNTHESIS_SYSTEM_PROMPT == old_rs.SYNTHESIS_SYSTEM_PROMPT
    assert _h(new_rs.SYNTHESIS_SYSTEM_PROMPT) == PINNED["synthesis_template"]
    for lang in LANGS:
        assert new_rs._system_prompt(lang) == old_rs._system_prompt(lang)
        kw = {"query": "salary?", "evidence_context": "[1] e", "tool_summaries": ["t"], "job_description": "jd",
              "candidate_background": "bg", "language": lang}
        assert new_rs.build_synthesis_messages(**kw) == old_rs.build_synthesis_messages(**kw)
        kw2 = {"query": "q", "sections": {"compensation": ["[1] a"], "narrative": ["[2] b"]}, "coverage_notes": ["n"],
               "company_summary": "c", "language": lang}
        assert new_rs.build_evidence_messages(**kw2) == old_rs.build_evidence_messages(**kw2)


def test_query_understanding_prompts():
    assert new_rt._SYSTEM_PROMPT == old_rt._SYSTEM_PROMPT
    for alt in (0, 2, 4):
        assert new_rt.QueryTranslator(max_alternates=alt)._system_prompt() == old_rt.QueryTranslator(
            max_alternates=alt)._system_prompt()
    for q in ("plain", 'quote " and {braces} — x', ""):
        assert new_rt._user_prompt(q) == old_rt._user_prompt(q)


# ---------------------------------------------------------------- career tools / judge --------------------------------
def test_career_tool_prompts():
    assert new_ja.SYSTEM_PROMPT == old_ja.SYSTEM_PROMPT and _h(new_ja.SYSTEM_PROMPT) == PINNED["job_analysis"]
    assert new_qg.SYSTEM_PROMPT == old_qg.SYSTEM_PROMPT
    assert _h(new_qg.SYSTEM_PROMPT) == PINNED["question_generation_template"]
    for focus in (None, "", "leadership", "it's {odd}"):
        a = JobAnalyzerArgs(job_description="JD {x}", focus=focus)
        assert new_ja._messages(a) == old_ja._messages(a)
    for kw in ({}, {"focus": ["behavioural"], "per_category": 5, "requirements": ["r"], "findings": ["f"],
                    "evidence": ["e"]}):
        a = QuestionGeneratorArgs(role="Nurse", **kw)
        assert new_qg._messages(a) == old_qg._messages(a)


def test_judge_prompts():
    assert new_judge.JUDGE_SYSTEM_PROMPT == old_judge.JUDGE_SYSTEM_PROMPT
    assert _h(new_judge.JUDGE_SYSTEM_PROMPT) == PINNED["judge_system"]
    for material in ({}, {"goal": "g — {x}", "tools": ["a"], "n": 1}, json.loads('{"k": ["é"]}')):
        assert new_judge.build_judge_messages(material) == old_judge.build_judge_messages(material)
