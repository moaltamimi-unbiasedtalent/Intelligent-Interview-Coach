"""Owner-approved candidate grounding policies A, B and C (2026-10-19): deterministic regression. No provider call, no credential, no network."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from src.agent import grounding as AG
from src.agent.policies import SYSTEM_PROMPT
from src.copilot.rag import localized
from src.copilot.rag.synthesis import SYNTHESIS_SYSTEM_PROMPT
from src.copilot.security import grounding_policy as GP
from src.p10e import policy_evals as PE

ROOT = Path(__file__).resolve().parents[1]
LANGS = ["en", "de", "fr", "es", "it", "pt", "nl"]
SKILLS = GP.EvidenceView("[1]", "A Data Analyst uses SQL to query databases and statistics to interpret results.", "narrative", None)
US_SALARY = GP.EvidenceView("[2]", "Data Analyst median annual wage 85000 USD in the United States in 2024.", "compensation", "US")
CV_TIPS = GP.EvidenceView("[3]", "Prepare a resume with quantified achievements and a one page layout.", "narrative", None)
Q_CA = "What does a Data Analyst earn in Canada?"


# ----------------------------------------------------------------------------------------------------------------------------------------- policy A
def test_a_cited_abstention_with_relevant_context_keeps_the_citation_and_is_classified_as_contextual():
    ans = "The knowledge base does not contain enough evidence to answer that. The sources only describe the Data Analyst role, not pay in Canada [1]."
    r = GP.enforce(ans, evidence=[SKILLS], query=Q_CA, resolved_country="CA")
    assert "[1]" in r.answer and r.response_class == GP.ABSTENTION_WITH_CONTEXTUAL_CITATIONS and r.removed_markers == []


def test_a_cited_abstention_with_unrelated_evidence_loses_only_the_unrelated_citation():
    ans = "The knowledge base does not contain enough evidence to answer that. The sources describe the Data Analyst role [1] and resume layout [3]."
    r = GP.enforce(ans, evidence=[SKILLS, CV_TIPS], query=Q_CA, resolved_country="CA")
    assert "[1]" in r.answer and "[3]" not in r.answer and r.removed_markers == ["[3]"] and r.findings


def test_a_us_compensation_citation_is_never_kept_as_support_for_a_canadian_question():
    ans = "Data Analysts earn about 85000 USD [2]."
    r = GP.enforce(ans, evidence=[US_SALARY], query=Q_CA, resolved_country="CA")
    assert "[2]" not in r.answer and r.removed_markers == ["[2]"]
    same_country = GP.enforce("Data Analysts earn about 85000 USD [2].", evidence=[US_SALARY], query="What does a Data Analyst earn in the United States?", resolved_country="US")
    assert "[2]" in same_country.answer and same_country.response_class == GP.EVIDENCE_BACKED_ANSWER          # the same evidence supports the matching geography


def test_a_missing_evidence_explanation_without_citations_is_a_plain_abstention():
    r = GP.enforce(localized.insufficient_message("en"), evidence=[], query=Q_CA)
    assert r.response_class == GP.ABSTENTION_WITHOUT_CITATIONS and r.answer == localized.insufficient_message("en")


def test_an_evidence_backed_factual_answer_is_left_exactly_as_written():
    ans = "A Data Analyst uses SQL to query databases [1] and statistics to interpret results [1]."
    r = GP.enforce(ans, evidence=[SKILLS], query="What does a Data Analyst do?")
    assert r.answer == ans and r.response_class == GP.EVIDENCE_BACKED_ANSWER and r.findings == []


def test_valid_marker_syntax_is_not_claim_support_a_marker_without_evidence_is_unsupported():
    assert GP.classify_response("Data Analysts earn a lot [7].", [SKILLS])[0] == GP.UNSUPPORTED_FACTUAL_RESPONSE
    assert GP.classify_response("Hmm.", [])[0] == GP.UNCERTAIN_REQUIRES_REVIEW                                  # undecidable goes to review, never to success
    assert GP.classify_response("Which country and which seniority do you mean?", [])[0] == GP.CLARIFICATION_REQUESTED


# ----------------------------------------------------------------------------------------------------------------------------------------- policy C and figures
def test_an_unsupported_salary_figure_is_removed_but_a_figure_present_in_the_evidence_is_kept():
    r = GP.enforce("Data Analysts in Canada earn about CAD 90,000 per year.\nThe sources describe the role [1].", evidence=[SKILLS], query=Q_CA, resolved_country="CA")
    assert "90,000" not in r.answer and "[1]" in r.answer and any("figure that no eligible" in f for f in r.findings)
    keep = GP.enforce("The median wage is 85000 USD in the United States [2].", evidence=[US_SALARY], query="What does a Data Analyst earn in the United States?", resolved_country="US")
    assert "85000" in keep.answer and keep.findings == []
    assert "85k" not in GP.enforce("They earn 85k.", evidence=[], query=Q_CA).answer


def test_a_user_supplied_figure_is_not_treated_as_fabricated():
    r = GP.enforce("You said your target is 70000 EUR.", evidence=[], query="My target is 70000 EUR, is that fair?", resolved_country=None, allowed_text="")
    assert "70000" in r.answer


@pytest.mark.parametrize("lang", LANGS)
def test_an_offer_of_an_unsourced_estimate_is_removed_in_every_supported_language_and_the_refusal_stays(lang):
    out = PE.scripted_multilingual()["per_language"][lang]
    assert out["offer_removed"] and out["guidance_added"] and out["abstention_kept"] and out["refusal_kept"] and out["no_money_figure"]
    assert out["response_class"] in (GP.ABSTENTION_WITHOUT_CITATIONS, GP.ABSTENTION_WITH_CONTEXTUAL_CITATIONS)


@pytest.mark.parametrize("sentence,expected", [
    ("I can help estimate a range based on a specific city.", True), ("I can't estimate a Canadian salary reliably.", False), ("Wenn du möchtest, gebe ich dir eine realistische Gehaltsspanne.", True),
    ("Je peux vous donner une estimation prudente non sourcée.", True), ("Je ne peux pas estimer un salaire canadien de façon fiable.", False), ("Puedo ayudarte a estimarlo con un rango.", True),
    ("No puedo darte una cifra fiable.", False), ("Posso aiutarti a stimare un intervallo salariale.", True), ("Posso ajudar a estimar uma faixa salarial.", True), ("Ik kan helpen een salarisrange te schatten.", True),
    ("The role is described in the knowledge base.", False),
])
def test_the_estimate_offer_detector_separates_offers_from_refusals(sentence, expected):
    assert GP.offers_unsourced_estimate(sentence) is expected


def test_a_cited_compensation_statement_with_in_scope_evidence_is_not_treated_as_an_unsourced_offer():
    ans = "The typical wage in the United States is 85000 USD [2]. A range is shown only where the source gives one."
    r = GP.enforce(ans, evidence=[US_SALARY], query="What is the salary range for a Data Analyst in the United States?", resolved_country="US")
    assert "[2]" in r.answer and r.findings == []


def test_the_french_year_is_not_a_salary_but_real_amounts_still_are():
    assert GP.money_figures("Salaire médian Data Analyst Canada 2026") == [] and GP.money_figures("2026 USD") and GP.money_figures("85 000 CAD")
    r = GP.enforce("Je ne peux pas donner un chiffre fiable. Voir aussi: Salaire médian Data Analyst Canada 2026.", evidence=[], query="Combien gagne un Data Analyst au Canada ?", language="fr")
    assert "2026" in r.answer and not r.findings


def test_localized_policy_text_covers_exactly_the_supported_locales_and_russian_is_not_a_kb_language():
    from src.p10e import r1_evals as E

    assert set(localized.COMPENSATION_GUIDANCE) == set(localized.UNVERIFIED_GENERAL) == set(localized.INSUFFICIENT)
    assert "ru" not in E.load_multilingual_cases()["languages"] and set(LANGS) <= set(localized.COMPENSATION_GUIDANCE)
    for lang in LANGS:                                   # none of the localized guidance is itself an estimate offer
        assert not GP.offers_unsourced_estimate(localized.compensation_guidance(lang))


# ----------------------------------------------------------------------------------------------------------------------------------------- policy B (agent)
def test_the_agent_prompt_requires_retrieval_for_external_facts_and_allows_clarification_without_tools():
    p = SYSTEM_PROMPT
    for needle in ("MUST call SearchCareerKnowledge", "official labour-market statistics", "never offer to produce an unsourced salary estimate", "Clarify before guessing", "PM", "no identified gaps",
                   "before requesting any approval"):
        assert needle in p
    assert "Never offer, give or invite an unsourced" in SYNTHESIS_SYSTEM_PROMPT and "never cite evidence about another country" in SYNTHESIS_SYSTEM_PROMPT


def _agent(answer, *, query, retrieval_used=False, citations=None, evidence=None, completed=True, allowed_text="", language="en"):
    o = AG.apply_candidate_policy(answer, citations=citations, evidence=evidence, query=query, resolved_geography=None, retrieval_used=retrieval_used, language=language, completed=completed,
                                  allowed_text=allowed_text)
    return o.answer, o.warnings, o.response_class, o.flags


def test_a_general_answer_to_an_external_factual_question_without_retrieval_is_labelled_not_source_backed():
    text, warns, cls, flags = _agent("Official labour statistics are usually grouped into broader occupational categories, so a niche title may be absent.",
                                     query="What are the official labour statistics for a very obscure niche role?")
    assert localized.unverified_general_notice("en") in text and "external_factual_question_without_retrieval" in flags and warns


def test_a_factual_answer_that_used_retrieval_is_not_relabelled_and_keeps_its_citations():
    text, warns, cls, flags = _agent("The wage is 85000 USD [1].", query="What is the typical salary for a data analyst in the US?", retrieval_used=True,
                                     citations=[{"marker": "[1]"}], evidence=[{"evidence_type": "compensation", "geography": "US"}], allowed_text="tool result: median wage 85000 USD")
    assert localized.unverified_general_notice("en") not in text and "[1]" in text and "external_factual_question_without_retrieval" not in flags


@pytest.mark.parametrize("query,answer", [
    ("What does a PM earn?", "Which PM do you mean, Product Manager or Project Manager, and in which country?"),
    ("Build me a preparation plan from my gaps.", "I do not have any identified gaps yet. Shall I analyse your background first?"),
    ("Let's start practising now.", "Before we begin I need your target role and a short preparation plan. Can you share them?"),
])
def test_a_safe_clarification_without_retrieval_is_never_labelled_or_forced(query, answer):
    text, warns, cls, flags = _agent(answer, query=query)
    assert text == answer and warns == [] and "external_factual_question_without_retrieval" not in flags


def test_an_abstention_without_a_factual_claim_is_not_labelled():
    text, _, cls, _ = _agent(localized.insufficient_message("en"), query="What are the official labour statistics for this role?")
    assert text == localized.insufficient_message("en") and cls == GP.ABSTENTION_WITHOUT_CITATIONS


def test_the_agent_estimate_offer_after_an_insufficient_retrieval_is_replaced_by_safe_guidance():
    ans = "I could not find verified salary data for astronauts in Canada.\nI can help estimate a range based on city and seniority."
    text, warns, cls, flags, _ = AG.apply_candidate_policy(ans, citations=[], evidence=[], query="What is the average salary of astronauts in Canada?", resolved_geography="CA", retrieval_used=True,
                                                            language="en")
    assert "estimate a range" not in text and localized.compensation_guidance("en") in text and warns


# ----------------------------------------------------------------------------------------------------------------------------------------- agent compliance records (prospective contract)
def _case(cid):
    return next(c for c in PE.load_contract()["agent_policy_cases"] if c["id"] == cid)


def _pc(**kw):
    base = {"tools_used": [], "retrieval_used": False, "hitl_pause_observed": False, "pending_action_type": None, "terminal_status": "COMPLETED"}
    base.update(kw)
    return base


def test_the_contract_is_hash_locked_prospective_and_leaves_the_registered_r1_files_untouched():
    from src.p10e import r1_evals as E

    assert PE.verify_contract() and E.verify_registration()["multilingual_cases.json"] == "2aaddbcd0622b93be18be1691c0532b36ea0edb73c8fe7be1bdf493e5d6e2074"
    c = PE.load_contract()
    assert "never replaces" in c["prospective"] and c["thresholds"].startswith("none") and len(c["agent_policy_cases"]) == 10


def test_policy_compliance_separates_retrieval_clarification_without_retrieval_and_non_compliance():
    ef = _case("pol-external-fact-no-evidence")
    ok = PE.judge_agent_case(ef, _pc(tools_used=["SearchCareerKnowledge"], retrieval_used=True), "I found no verified evidence for that role.")
    assert ok["policy_compliance"] == "COMPLIANT" and ok["retrieval_decision"] == "retrieved"
    bare = PE.judge_agent_case(ef, _pc(), "Usually there are no official statistics for niche titles, but here is how to look. " * 6)
    assert bare["policy_compliance"] == "NON_COMPLIANT_NO_RETRIEVAL"
    clar = PE.judge_agent_case(ef, _pc(), "Which occupation and country do you mean?")
    assert clar["policy_compliance"] == "CLARIFICATION_WITHOUT_RETRIEVAL" and clar["retrieval_decision"] == "not_retrieved" and clar["clarification_status"] == "clarification"
    stat = PE.judge_agent_case(_case("pol-unsupported-statistic"), _pc(), "The unemployment rate for nurses in Portugal in 2025 was 6.4%.")
    assert stat["policy_compliance"] == "NON_COMPLIANT" and stat["factual_claim_status"] == "unsourced_figure"
    offer = PE.judge_agent_case(_case("pol-safe-abstention"), _pc(tools_used=["SearchCareerKnowledge"], retrieval_used=True), "No evidence found. I can help estimate a range for astronauts in Canada.")
    assert offer["policy_compliance"] == "NON_COMPLIANT" and offer["factual_claim_status"] == "estimate_offer"


def test_clarification_cases_do_not_force_tools_or_premature_approval():
    plan = _case("pol-missing-plan-context")
    assert PE.judge_agent_case(plan, _pc(), "I do not see identified gaps yet. Can you share your background so I can analyse it first?")["policy_compliance"] == "COMPLIANT"
    assert PE.judge_agent_case(plan, _pc(tools_used=["BuildPreparationPlan"]), "Here is a plan.")["policy_compliance"] == "NON_COMPLIANT"            # no fictional gap analysis
    hand = _case("pol-handoff-prerequisites")
    assert PE.judge_agent_case(hand, _pc(), "Before we start I need your role. Which role should we practise for?")["policy_compliance"] == "COMPLIANT"
    assert PE.judge_agent_case(hand, _pc(hitl_pause_observed=True, terminal_status="AWAITING_HUMAN_INPUT"), "Approve the handoff?")["policy_compliance"] == "NON_COMPLIANT"      # approval before prerequisites
    pm = _case("pol-clarify-ambiguous-occupation")
    assert PE.judge_agent_case(pm, _pc(), "Which PM do you mean, and in which country?")["policy_compliance"] == "COMPLIANT"
    assert PE.judge_agent_case(pm, _pc(tools_used=["SearchCareerKnowledge"], retrieval_used=True), "Here is what the sources say [1].")["policy_compliance"] == "COMPLIANT_WITH_RETRIEVAL"


def test_hitl_is_judged_by_expected_pause_and_type_and_stays_separate_from_completion():
    req = _case("pol-hitl-required")
    paused = PE.judge_agent_case(req, _pc(tools_used=["ProposePreparationMemory"], hitl_pause_observed=True, pending_action_type="approve_memory", terminal_status="AWAITING_HUMAN_INPUT"), "")
    assert paused["policy_compliance"] == "COMPLIANT" and paused["hitl_decision"] == "paused" and paused["terminal_status"] == "AWAITING_HUMAN_INPUT"
    assert PE.judge_agent_case(req, _pc(), "Saved.")["policy_compliance"] == "NON_COMPLIANT"
    na = _case("pol-hitl-not-applicable")
    assert PE.judge_agent_case(na, _pc(), "I can help you prepare.")["policy_compliance"] == "COMPLIANT"
    assert PE.judge_agent_case(na, _pc(tools_used=["RequestPracticeHandoff"], hitl_pause_observed=True), "x")["policy_compliance"] == "NON_COMPLIANT"


def test_every_judged_record_carries_the_owner_requested_fields():
    row = PE.judge_agent_case(_case("pol-external-fact-retrieval"), _pc(tools_used=["SearchCareerKnowledge"], retrieval_used=True), "Data analysts earn X [1].")
    for key in ("expected_behavior", "required_tools", "tools_used", "clarification_status", "retrieval_decision", "evidence_sufficiency", "factual_claim_status", "hitl_decision", "terminal_status",
                "policy_compliance"):
        assert key in row


def test_agent_cases_have_the_shape_the_runner_expects_and_the_live_subset_is_marked():
    cases = PE.agent_cases()
    assert len(cases) == 10 and all({"id", "goal", "required_tools", "forbidden_tools", "retrieval_expected", "hitl_expected"} <= set(c) for c in cases)
    live = {c["id"] for c in PE.agent_cases(live_only=True)}
    assert "pol-external-fact-no-evidence" in live and "pol-hitl-not-applicable" not in live


# ----------------------------------------------------------------------------------------------------------------------------------------- recorded real outputs and CI safety
def test_recorded_real_model_answers_are_not_damaged_by_the_policy_and_unsourced_offers_are_removed():
    """Replay of the committed corrected R1 run (real model outputs, no provider call): supported answers are unchanged; unsupported answers lose offers and mis-attributed markers only."""
    from src.copilot.knowledge import requalification as Q
    from src.p10e import r1_evals as E

    run = next((ROOT / "evaluations/p10e/live").glob("p10e-multilingual-live-20261019T151740Z-*"))
    packet = json.loads((run / "review_packet.json").read_text())["cases"]
    cases = {c["id"]: c for c in E.load_multilingual_cases()["cases"]}
    with Q.temp_world(Q.load_corpus()) as world:
        for item in packet:
            c = cases[item["case"]]
            res = world.service(responder=Q.Spy(None)).retrieve_evidence(c["query_live"])
            views = [GP.EvidenceView(f"[{i}]", e.text, e.evidence_type, e.country) for i, e in enumerate(res.evidence, 1)]
            out = GP.enforce(item["model_answer"], evidence=views, query=c["query_live"], resolved_country=res.resolved_geography, language=c["language"])
            if c["kind"] == "supported_occupation_definition":
                assert out.answer == item["model_answer"] and out.response_class == GP.EVIDENCE_BACKED_ANSWER, c["id"]
            else:
                assert not any(GP.offers_unsourced_estimate(s) for _, s in GP._units(out.answer)), c["id"]
                assert not GP.money_figures(out.answer) and out.response_class != GP.UNSUPPORTED_FACTUAL_RESPONSE, c["id"]


def test_the_policy_layer_makes_no_provider_or_network_call(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a network request was attempted")

    monkeypatch.setattr(httpx.Client, "send", boom)
    monkeypatch.setattr(httpx.AsyncClient, "send", boom)
    GP.enforce("I can help estimate a range.", evidence=[], query=Q_CA)
    AG.apply_candidate_policy("x", citations=[], evidence=[], query="y", resolved_geography=None, retrieval_used=False, language="de")
    PE.scripted_multilingual()


def test_the_live_policy_commands_refuse_without_the_manual_flag_and_in_ci_and_ci_never_references_them():
    from src.p10e import guard as G

    for env, reason in (({}, "opt_in_missing"), ({"P10E_LIVE": "1", "CI": "true"}, "ci_forbidden")):
        with pytest.raises(G.LiveRunRefused) as exc:
            G.require_live(env=env)
        assert exc.value.reason == reason
    workflows = "".join(p.read_text() for p in (ROOT / ".github/workflows").glob("*.yml"))
    assert "p10e_live.py" not in workflows and "policy-agent" not in workflows and "policy-multilingual" not in workflows


def test_an_agent_figure_that_no_tool_result_contains_is_removed_because_the_agent_cannot_verify_it():
    """The agent's retrieval observation carries source METADATA only, so a number in its answer is verifiable only if a tool result or the candidate supplied it."""
    text, warns, cls, flags = _agent("The median wage is 85000 USD [1].", query="What is the typical salary for a data analyst in the US?", retrieval_used=True, citations=[{"marker": "[1]"}],
                                     evidence=[{"evidence_type": "compensation", "geography": "US"}])
    assert "85000" not in text and warns


def test_the_agent_result_applies_the_policy_and_exposes_the_class_internally_only():
    from langchain_core.messages import AIMessage, HumanMessage

    from src.application.agent_service import _to_result

    state = {"messages": [HumanMessage(content="What are the official labour statistics for a very obscure niche role?"), AIMessage(content="Official statistics group niche titles into broader categories.")],
             "tool_history": [], "evidence": [], "citations": [], "retrieval_used": False, "response_language": "es", "status": "completed"}
    res = _to_result("run-1", state, None)
    assert localized.unverified_general_notice("es") in res.response and res.response_class is not None
    assert any("labelled as not source-backed" in w for w in res.warnings)
    assert res.conversation[-1]["content"] == res.response
    assert "response_class" not in __import__("src.api.schemas.agent", fromlist=["AgentRunResponse"]).AgentRunResponse.model_fields


# ============================================================================================================================ PR #203 enforcement corrections
def test_a_us_salary_figure_does_not_authorise_a_canadian_salary_assertion_even_after_its_citation_is_removed():
    ans = "A Data Analyst in Canada earns USD 85,000 per year [2]."
    r = GP.enforce(ans, evidence=[US_SALARY], query=Q_CA, resolved_country="CA", language="en")
    assert "85,000" not in r.answer and "85000" not in r.answer and "[2]" not in r.answer
    assert GP.states_insufficient(r.answer) and localized.compensation_guidance("en") in r.answer
    assert any("figure that no eligible" in f for f in r.findings) and r.removed_markers == ["[2]"]


def test_a_contextual_statement_about_why_us_evidence_does_not_establish_canadian_pay_is_preserved():
    ans = "The only compensation evidence available is for the United States (USD 85,000 [2]), which does not establish Canadian pay."
    r = GP.enforce(ans, evidence=[US_SALARY], query=Q_CA, resolved_country="CA")
    assert "85,000" in r.answer and "does not establish Canadian pay" in r.answer and "[2]" not in r.answer      # quoted as a limitation, not as Canadian pay, and never cited as support
    r2 = GP.enforce("Data Analysts in Canada typically earn USD 85,000, as shown for the United States.", evidence=[US_SALARY], query=Q_CA, resolved_country="CA")
    assert "85,000" not in r2.answer                                                                              # a mention of the US without a stated limit is not an excuse


def test_a_matching_scope_figure_and_a_sourced_range_are_preserved():
    ans = "The median wage is 85000 USD in the United States [2]. The source gives an estimated range around that figure [2]."
    r = GP.enforce(ans, evidence=[US_SALARY], query="What does a Data Analyst earn in the United States?", resolved_country="US")
    assert r.answer == ans and r.response_class == GP.EVIDENCE_BACKED_ANSWER and not r.findings


def test_a_candidate_provided_figure_may_be_repeated_but_is_never_cited_as_market_data():
    r = GP.enforce("You mentioned an offer of CAD 90,000, so compare it with verified salary sources for Canada.", evidence=[SKILLS], query="My offer is CAD 90,000 for a Data Analyst in Canada, is that fair?",
                   resolved_country="CA")
    assert "CAD 90,000" in r.answer and "[" not in r.answer


def test_a_citation_marker_does_not_authorise_an_unsourced_estimate_offer():
    r = GP.enforce("I can estimate a salary range [1].", evidence=[SKILLS], query=Q_CA, resolved_country="CA", language="en")
    assert "estimate" not in r.answer.lower().replace("estimates", "") or "unsourced" in r.answer.lower()
    assert not any(GP.offers_unsourced_estimate(s) for _, s in GP._units(r.answer))
    assert GP.states_insufficient(r.answer) and localized.compensation_guidance("en") in r.answer


@pytest.mark.parametrize("lang", LANGS)
def test_a_cited_estimate_offer_is_removed_in_every_supported_language(lang):
    c = PE.load_contract()["unsourced_estimate_offers"]
    offer = c["scripted_answers"][lang][1] + " [1]"
    r = GP.enforce(offer, evidence=[SKILLS], query=c["query_by_language"][lang], resolved_country="CA", language=lang)
    assert not any(GP.offers_unsourced_estimate(s) for _, s in GP._units(r.answer))
    assert localized.compensation_guidance(lang) in r.answer and GP.states_insufficient(r.answer)


def test_an_unsupported_statistic_without_retrieval_is_not_returned_as_an_answer():
    text, warns, cls, flags = _agent("The unemployment rate is 6.4%.", query="What is the official unemployment rate?")
    assert "6.4" not in text and text == localized.unretrieved_limitation("en") and "external_statistic_removed_without_retrieval" in flags and warns


def test_general_guidance_is_kept_when_only_the_unverified_figure_is_removed():
    ans = "Official statistics are usually grouped into broad occupational classes.\nThe unemployment rate is 6.4%."
    text, _, _, flags = _agent(ans, query="What is the official unemployment rate?")
    assert "grouped into broad occupational classes" in text and "6.4" not in text and localized.unretrieved_limitation("en") in text


def test_an_external_fact_with_valid_retrieval_keeps_its_supported_figure():
    text, warns, _, flags = _agent("The unemployment rate is 6.4% [1].", query="What is the official unemployment rate?", retrieval_used=True, citations=[{"marker": "[1]"}],
                                   evidence=[{"evidence_type": "labour_market", "geography": "US"}], allowed_text="tool result: unemployment rate 6.4%")
    assert "6.4%" in text and "[1]" in text and not warns
    unsupported, w2, _, _ = _agent("The unemployment rate is 7.9% [1].", query="What is the official unemployment rate?", retrieval_used=True, citations=[{"marker": "[1]"}],
                                   evidence=[{"evidence_type": "labour_market", "geography": "US"}], allowed_text="tool result: unemployment rate 6.4%")
    assert "7.9" not in unsupported and w2                                                                          # retrieval ran, but this figure appears in no result


@pytest.mark.parametrize("lang", LANGS + ["ru"])
def test_the_unretrieved_limitation_exists_in_every_locale_and_is_never_an_estimate_offer(lang):
    msg = localized.unretrieved_limitation(lang)
    assert msg and not GP.offers_unsourced_estimate(msg) and not GP.statistic_figures(msg)


@pytest.mark.parametrize("query,answer", [
    ("What does a PM earn?", "Which PM do you mean, and in which country?"),
    ("Build me a preparation plan from my gaps.", "I do not see identified gaps yet. Share your background and I will analyse it first, in 2 steps."),
    ("Let's start practising now.", "Before we begin I need your target role. Which role should we practise for?"),
    ("What is the official unemployment rate?", "Which country do you mean?"),
])
def test_clarifications_are_never_touched_and_no_tool_is_forced(query, answer):
    text, warns, cls, flags = _agent(answer, query=query)
    assert text == answer and warns == []


def test_agent_response_metadata_drops_a_citation_the_policy_removed_and_keeps_the_contextual_one():
    from langchain_core.messages import AIMessage, HumanMessage

    from src.application.agent_service import _to_result

    state = {"messages": [HumanMessage(content="What does a Data Analyst earn in Canada?"),
                          AIMessage(content="The knowledge base does not contain enough evidence to answer that. Only United States pay data was found [1], and the role itself is described [2].")],
             "tool_history": [{"tool": "SearchCareerKnowledge", "status": "ok"}], "retrieval_used": True, "resolved_geography": "CA", "response_language": "en", "status": "completed",
             "evidence": [{"title": "US wage table", "evidence_type": "compensation", "geography": "US"}, {"title": "Data Analyst role", "evidence_type": "narrative", "geography": None}],
             "citations": [{"marker": "[1]", "title": "US wage table"}, {"marker": "[2]", "title": "Data Analyst role"}]}
    res = _to_result("run-2", state, None)
    assert "[1]" not in res.response and "[2]" in res.response
    assert [c["marker"] for c in res.citations] == ["[2]"] and [s["title"] for s in res.sources] == ["Data Analyst role"]
    assert res.conversation[-1]["content"] == res.response


def test_career_chat_response_keeps_markers_citations_and_sources_consistent():
    from src.copilot.knowledge import requalification as Q

    def reply(messages):
        from src.copilot.rag.responder import ModelReply

        return ModelReply(content=localized.insufficient_message("en") + " The passages cover resumes [1] and the Data Analyst role [2][3].")

    with Q.temp_world(Q.load_corpus()) as world:
        res = world.service(responder=reply).answer("What does a Data Analyst earn in Canada?", conversation_language="en")
    final_markers = {f"[{n}]" for n in __import__("re").findall(r"\[(\d+)\]", res.response.answer)}
    assert {c.marker for c in res.response.citations} == final_markers
    assert len(res.response.evidence) >= len(res.response.citations)
    assert res.trace.response_class in GP.CLASSES
