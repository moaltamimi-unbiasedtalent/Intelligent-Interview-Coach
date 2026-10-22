"""02E (L-ROUTE-1): language-aware retrieval routing, tested per language with fixtures. Offline; no model call."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.copilot.knowledge import router as R
from src.copilot.knowledge import router_lang as RL

CASES = json.loads((Path(__file__).resolve().parents[1] / "evaluations" / "retrieval_quality" / "routing_cases_v1.json").read_text(encoding="utf-8"))["cases"]
FOREIGN = [lang for lang in CASES if lang != "en"]


def _flat(langs):
    return [(lang, q, lane) for lang in langs for q, lane in CASES[lang]]


def test_fixture_covers_the_seven_languages_with_the_core_lanes():
    assert set(CASES) == {"en", "de", "fr", "es", "it", "pt", "nl"}
    for lang in FOREIGN:
        lanes = {lane for _, lane in CASES[lang]}
        assert {"compensation", "structured_role", "shortage", "education", "licence", "forecast", "openings", "certification", "transition", "mixed"} <= lanes, lang


@pytest.mark.parametrize("lang", sorted(CASES))
def test_every_fixture_routes_to_its_lane_with_and_without_a_language_hint(lang):
    for q, lane in CASES[lang]:
        assert R.route_question(q).lane == lane, (lang, q, "auto-detected")
        assert R.route_question(q, language=lang).lane == lane, (lang, q, "hinted")


def test_the_old_english_only_rules_missed_most_non_english_questions():
    """Documents the gap that was closed: the English rules alone route most foreign fixtures wrongly (they fell to the vector lane)."""
    flat = _flat(FOREIGN)
    english_only = sum(1 for _, q, lane in flat if (R._english_rules(q) or R.RouteDecision(R.RetrievalLane.VECTOR, "default")).lane == lane)
    assert english_only < 0.5 * len(flat)
    assert all(R.route_question(q).lane == lane for _, q, lane in flat)


def test_english_routing_is_unchanged_and_never_enters_the_localized_tables():
    for q, lane in CASES["en"]:
        assert RL.candidate_languages(q) == []
        assert R.route_question(q).lane == lane
    cases = json.loads((Path(__file__).resolve().parents[1] / "evaluations" / "router_cases.json").read_text(encoding="utf-8"))["cases"]
    wrong = [c["id"] for c in cases if R._english_rules(c["query"]) is not None and R.route_question(c["query"]).lane != R._english_rules(c["query"]).lane]
    assert wrong == []        # wherever the English rules decide, the full router decides the same


def test_an_english_hint_or_unsupported_hint_uses_the_english_rules_only():
    q = "Was verdient ein Datenanalyst?"
    assert RL.route_localized(q, "en") is None
    assert RL.route_localized(q, "ru") is None                      # Russian is not a routing language
    assert R.route_question(q, language="en").lane != "compensation"


def test_unrecognised_text_defaults_to_the_vector_lane_and_never_raises():
    for q in ("", "   ", "Ciao come stai oggi", "Привет, как дела?", "你好", "asdf qwer"):
        assert R.route_question(q).lane in R.constants.RETRIEVAL_LANES
    assert R.route_question("Привет, как дела?").lane == "vector"


def test_language_guess_is_deterministic_and_prefers_the_evident_language():
    assert RL.candidate_languages("Wie viele offene Stellen gibt es für Ingenieure?")[0] == "de"
    assert RL.candidate_languages("Hoeveel vacatures zijn er voor ingenieurs?")[0] == "nl"
    assert RL.candidate_languages("Quais são as responsabilidades de um gestor?")[0] == "pt"
    assert RL.candidate_languages("Quels sont les salaires pour un infirmier ?")[0] == "fr"
    assert RL.candidate_languages("xyz") == list(RL.ROUTING_LANGUAGES)       # no evidence: every table, fixed order
    assert RL.candidate_languages("anything", "de-AT") == ["de"]


def test_accents_are_folded_so_both_spellings_route_alike():
    assert R.route_question("Gibt es einen Fachkräftemangel?").lane == R.route_question("Gibt es einen Fachkraftemangel?").lane == "shortage"
    assert R.route_question("¿Hay escasez de enfermeros?").lane == R.route_question("Hay escasez de enfermeros").lane == "shortage"


def test_a_question_mixing_a_language_with_an_english_term_still_routes():
    assert R.route_question("Was verdient ein Software Engineer?").lane == "compensation"
    assert R.route_question("What is the Gehalt of a nurse?").lane == "compensation"        # English stop-words, English rule 'what' is not needed: table fallback is not used


def test_every_table_defines_every_lane_name():
    for lang, table in RL._TABLES.items():
        assert set(table) == set(RL.LANE_ORDER), lang
        for name, src in table.items():
            assert RL._COMPILED[lang][name].pattern, (lang, name)
