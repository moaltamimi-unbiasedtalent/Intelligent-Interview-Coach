"""06D (LG-06): multilingual retrieval evaluation grid, citation attribution, cross-language abstention and mixed-language corpora.

Offline: the local lexical embedder and a deterministic topic embedder, no network, no provider. Nothing here is retrieval-quality evidence: the data is synthetic,
engineering-authored, not independent and not native-reviewed.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.copilot.config import CopilotConfig
from src.copilot.embeddings import BaseEmbedder, LocalHashEmbedder
from src.copilot.embedding_budget import PaidEmbeddingRefused
from src.copilot.evaluation import embedding_benchmark as EB
from src.copilot.evaluation import multilingual_pairs as MP
from src.copilot.evaluation import multilingual_retrieval as ML
from src.copilot.knowledge import router as ROUTER
from src.copilot.knowledge.router_lang import guess_language
from src.copilot.models import Citation, DocumentChunk, RetrievalResult
from src.copilot.rag import attribution as AT
from src.copilot.rag import localized
from src.copilot.rag.responder import ModelReply
from src.copilot.retrieval_quality.floor import RelevanceFloor
from src.copilot.service import CareerIntelligenceService
from src.copilot.vectorstore import InMemoryVectorStore
from src.locales import SUPPORTED_LOCALE_CODES

ROOT = Path(__file__).resolve().parents[1]
SEVEN = ("en", "de", "fr", "es", "it", "pt", "nl")
DATA = ML.load_dataset()
TOPIC_OF_TEXT = {**{p["text"]: p["topic"] for p in DATA["passages"]}, **{q["text"]: q["topic"] for q in DATA["queries"]}}
TOPICS = sorted(DATA["topics"])


class TopicEmbedder(BaseEmbedder):
    """A deterministic stand-in that knows each dataset text's topic: a one-hot topic vector, zeros for any other text. It declares the free ``local``
    provider so no paid-call approval is involved (test double only)."""

    provider, model, version, dimensions = "local", "topic-oracle", "t1", len(TOPICS)

    def _vec(self, text):
        v = [0.0] * len(TOPICS)
        if text in TOPIC_OF_TEXT:
            v[TOPICS.index(TOPIC_OF_TEXT[text])] = 1.0
        return v

    def embed_documents(self, texts):
        return [self._vec(t) for t in texts]

    def embed_query(self, text):
        return self._vec(text)


# ------------------------------------------------------------------ (1) the 49-pair grid
@pytest.fixture(scope="module")
def local_run():
    return MP.run_pair_evaluation(LocalHashEmbedder())


@pytest.fixture(scope="module")
def oracle_run():
    return MP.run_pair_evaluation(TopicEmbedder())


def test_grid_has_all_49_pairs_with_sample_sizes_and_interval_warnings(local_run):
    assert set(local_run["pairs"]) == {f"{x}>{y}" for x in SEVEN for y in SEVEN}
    for key, e in local_run["pairs"].items():
        assert e["n"] == 7, key
        assert e["cross_language"] == (e["question_language"] != e["source_language"])
        assert any(w.startswith("wide_interval") for w in e["warnings"]), key
        assert e["mrr_ci95"] is not None and e["mrr_ci95"][0] <= e["mrr"] <= e["mrr_ci95"][1]
        for k in (1, 3, 5):
            assert 0.0 <= e[f"recall@{k}"] <= 1.0 and 0.0 <= e[f"ndcg@{k}"] <= 1.0
    assert local_run["dataset"]["pairs"] == 49 and local_run["dataset"]["questions_per_pair"] == 7


def test_result_is_labelled_harness_proof_and_claims_nothing(local_run):
    assert local_run["label"] == "harness proof, not retrieval quality"
    for flag in ("retrieval_quality_claimed", "lg06_met", "production_quality_evidence", "native_reviewed", "independent_data"):
        assert local_run[flag] is False
    assert local_run["embedder"]["lexical_only"] is True
    assert "NOT RUN" in " ".join(local_run["limitations"]) and "NOT independent" in " ".join(local_run["limitations"])
    assert "has NOT been run" in local_run["pending"]


def test_grid_is_deterministic():
    a = MP.run_pair_evaluation(LocalHashEmbedder())
    b = MP.run_pair_evaluation(LocalHashEmbedder())
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_oracle_embedder_proves_the_metric_plumbing_on_every_pair(oracle_run):
    """A perfect topic embedder must score 1.0 everywhere; a wrong rollup, k or relevance mapping would show here."""
    for key, e in oracle_run["pairs"].items():
        assert e["mrr"] == e["recall@1"] == e["recall@3"] == e["ndcg@3"] == 1.0, key
        # cross-language rate: defined (and 1.0) only for X != Y; X == Y is not applicable, never 0 or 1
        assert e["cross_language_rate@3"] == (1.0 if e["cross_language"] else None), key
    assert oracle_run["rollups"]["same_language"]["pairs"] == 7 and oracle_run["rollups"]["cross_language"]["pairs"] == 42
    assert oracle_run["rollups"]["cross_language"]["n"] == 294
    assert oracle_run["rollups"]["same_language"]["cross_language_rate@3"] is None


def test_local_lexical_embedder_is_visibly_worse_across_languages_than_within(local_run):
    same, cross = local_run["rollups"]["same_language"], local_run["rollups"]["cross_language"]
    assert same["mrr"] > cross["mrr"]       # a lexical embedder cannot cross languages; this is a harness check, not a quality claim


def test_a_non_local_embedder_is_refused_without_owner_approval(monkeypatch):
    for var in ("ASK4MO_ALLOW_PAID_EMBEDDINGS", "ASK4MO_EMBEDDING_BUDGET_MARKER", "ASK4MO_EMBEDDING_MAX_CALLS", "AI_BUDGET_APPROVED_MARKER"):
        monkeypatch.delenv(var, raising=False)

    class Paid(TopicEmbedder):
        provider = "openai"

    with pytest.raises(PaidEmbeddingRefused):
        MP.run_pair_evaluation(Paid())


def test_the_runner_is_dry_run_only_and_does_not_import_a_provider_client():
    src = (ROOT / "src/copilot/evaluation/multilingual_pairs.py").read_text(encoding="utf-8")
    for needle in ("OpenAIEmbedder", "requests", "httpx", "socket", "os.environ"):
        assert needle not in src


def test_evaluator_script_passes_and_writes_only_when_asked(tmp_path):
    out = tmp_path / "r.json"
    proc = subprocess.run([sys.executable, str(ROOT / "scripts/eval_multilingual_pairs.py"), "--write", str(out)], capture_output=True, text=True, cwd=ROOT)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "HARNESS PROOF, NOT RETRIEVAL QUALITY" in proc.stdout and "NOT RUN" in proc.stdout
    assert json.loads(out.read_text(encoding="utf-8"))["label"] == MP.LABEL


def test_evaluator_invariants_detect_a_broken_result(local_run):
    import importlib.util

    spec = importlib.util.spec_from_file_location("eval_ml", ROOT / "scripts/eval_multilingual_pairs.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.invariant_failures(local_run) == []
    broken = json.loads(json.dumps(local_run))
    broken["attribution_summary"]["notices_present"] = 41
    broken["lg06_met"] = True
    assert set(mod.invariant_failures(broken)) == {"attribution", "claims"}


# ------------------------------------------------------------------ (2) attribution
def _src(marker="[1]", language="es", version="v3", text="El texto original de la fuente."):
    return AT.RetrievedSource(marker, f"c{marker}", f"d{marker}", text, language, version)


def _cit(marker="[1]", language="es", version="v3"):
    return Citation(marker=marker, doc_id=f"d{marker}", chunk_id=f"c{marker}", language=language, version=version)


def test_every_citation_maps_to_a_retrieved_source_and_version():
    assert AT.check_citations("Claim [1].", [_cit()], [_src()]) == []
    assert AT.check_citations("Claim [2].", [], [_src()]) == ["unmapped_marker:[2]"]
    assert "citation_not_retrieved:[3]" in AT.check_citations("Claim [1].", [_cit("[3]")], [_src()])
    wrong_chunk = Citation(marker="[1]", doc_id="d[1]", chunk_id="other")
    assert AT.check_citations("Claim [1].", [wrong_chunk], [_src()]) == ["citation_mismatch:[1]"]
    assert AT.check_citations("Claim [1].", [_cit(version="v2")], [_src(version="v3")]) == ["version_mismatch:[1]"]
    # an unrecorded version on either side is not a mismatch (never invented)
    assert AT.check_citations("Claim [1].", [_cit(version=None)], [_src(version="v3")]) == []


@pytest.mark.parametrize("convo", SUPPORTED_LOCALE_CODES)
@pytest.mark.parametrize("source_lang", SEVEN)
def test_cross_language_source_gets_notice_in_conversation_language_with_verbatim_original(convo, source_lang):
    text = "Pour négocier un salaire, renseignez-vous d'abord. Puis justifiez votre attente."
    answer = "You can negotiate by researching the range [1]."
    out, report = AT.apply_source_language_notices(answer, [_src(language=source_lang, text=text)], conversation_language=convo)
    if source_lang == convo:
        assert out == answer and report.translated_markers == []
        return
    assert out.startswith(answer) and report.translated_markers == ["[1]"] and report.ok
    notice = out[len(answer):].strip()
    assert localized.LANGUAGE_ENDONYMS[source_lang] in notice
    assert f'"{text}"' in notice                                   # the original wording, unchanged, never translated
    template_without_slots = localized.SOURCE_LANGUAGE_NOTICE[convo].split("{marker}")[0]
    assert notice.startswith(template_without_slots)               # the sentence is the conversation language's own


def test_same_language_source_gets_no_notice_and_unknown_language_makes_no_claim():
    answer = "Claim [1] and [2]."
    out, report = AT.apply_source_language_notices(answer, [_src("[1]", "de"), _src("[2]", None)], conversation_language="de")
    assert out == answer
    assert report.unknown_language_markers == ["[2]"] and report.translated_markers == []
    out2, r2 = AT.apply_source_language_notices(answer, [_src("[1]", "de"), _src("[2]", "klingon")], conversation_language="de")
    assert out2 == answer and r2.unknown_language_markers == ["[2]"]      # an unsupported code is never named as a language


def test_only_cited_sources_get_a_notice_and_each_once():
    out, report = AT.apply_source_language_notices("See [2] and again [2].", [_src("[1]", "fr"), _src("[2]", "fr")], conversation_language="en")
    assert report.translated_markers == ["[2]"] and out.count("Source [2]") == 1 and "Source [1]" not in out


def test_unmapped_marker_is_reported_never_repaired():
    out, report = AT.apply_source_language_notices("Claim [7].", [_src("[1]", "fr")], conversation_language="en")
    assert out == "Claim [7]." and report.issues == ["unmapped_marker:[7]"] and not report.ok


def test_excerpt_is_a_verbatim_prefix_bounded_and_marks_the_cut():
    long = ("alpha beta gamma " * 40).strip()
    q = AT.verbatim_excerpt(long)
    assert q.endswith("…") and len(q) <= AT.QUOTE_MAX_CHARS + 1 and long.startswith(q[:-1])
    assert AT.verbatim_excerpt("kurz  und\nbündig") == "kurz und bündig"
    assert '"' not in AT.verbatim_excerpt('say "hi"')


def test_there_is_no_translation_step_anywhere_in_attribution():
    src = (ROOT / "src/copilot/rag/attribution.py").read_text(encoding="utf-8")
    code = "\n".join(line for line in src.splitlines() if not line.lstrip().startswith(("#", '"""')))
    for needle in ("translate(", "Responder", "responder", "llm", "ChatOpenAI"):
        assert needle not in code


# ------------------------------------------------------------------ (3) abstention across languages
def _results(*scores):
    return [RetrievalResult(chunk=DocumentChunk(chunk_id=f"c{i}", doc_id=f"d{i}", text="irrelevant passage"), score=s) for i, s in enumerate(scores)]


@pytest.mark.parametrize("lang", SUPPORTED_LOCALE_CODES)
def test_abstains_in_the_conversation_language_when_only_irrelevant_sources_exist(lang):
    d = AT.decide_abstention(_results(0.0, 0.0, 0.0), RelevanceFloor(0.0, "default"), conversation_language=lang)
    assert d.abstain and d.cited == () and d.sources_found == 3 and d.kept == 0 and d.language == lang
    assert d.message.startswith(localized.insufficient_message(lang))            # the standard abstention opening survives
    assert d.message.endswith(localized.IRRELEVANT_SOURCES[lang])
    assert "[1]" not in d.message


@pytest.mark.parametrize("lang", SEVEN)
def test_a_floor_above_every_score_abstains_and_a_score_above_the_floor_does_not(lang):
    assert AT.decide_abstention(_results(0.3, 0.2), RelevanceFloor(0.5, "calibrated"), conversation_language=lang).abstain
    ok = AT.decide_abstention(_results(0.9, 0.2), RelevanceFloor(0.5, "calibrated"), conversation_language=lang)
    assert not ok.abstain and ok.message is None and ok.kept == 1


def test_nothing_retrieved_at_all_uses_the_plain_sentence():
    d = AT.decide_abstention([], RelevanceFloor(0.0, "default"), conversation_language="fr")
    assert d.abstain and d.message == localized.insufficient_message("fr") and d.sources_found == 0


@pytest.mark.parametrize("lang", SEVEN)
def test_abstention_language_follows_the_question_when_no_conversation_language_is_set(lang):
    q = next(q for q in EB.load_abstention()["queries"] if q["language"] == lang)
    expected = guess_language(q["text"])
    got = AT.resolve_answer_language(None, q["text"])
    assert got == (expected if expected in SEVEN else "en")
    # the explicit Mo conversation language always wins over the question's language and nothing else (no interface language) takes part
    assert AT.resolve_answer_language("nl", q["text"]) == "nl"
    assert AT.resolve_answer_language("zz", "") == "en"


def test_a_tied_or_empty_language_guess_falls_back_to_english_never_to_a_guess():
    assert guess_language("") is None and AT.resolve_answer_language(None, "") == "en"
    assert AT.resolve_answer_language(None, "xyzzy plugh") == "en"


def test_every_abstention_case_in_all_49_pairs_is_in_the_question_language_without_citation():
    run = MP.run_pair_evaluation(TopicEmbedder())
    for key, e in run["pairs"].items():
        a = e["abstention"]
        assert a["n"] == 3 and a["abstained"] == 3 and a["false_answer_rate"] == 0.0, key
        assert a["language_correct"] and a["no_citation_on_abstention"], key
    assert run["abstention_summary"]["abstained"] == run["abstention_summary"]["cases"] == 147


def test_localized_catalogue_parity_for_the_new_sentences():
    for table in (localized.IRRELEVANT_SOURCES, localized.SOURCE_LANGUAGE_NOTICE, localized.LANGUAGE_ENDONYMS):
        assert set(table) == set(SUPPORTED_LOCALE_CODES)
        assert all(v.strip() for v in table.values())
    for lang, t in localized.SOURCE_LANGUAGE_NOTICE.items():
        assert "{marker}" in t and "{source_language}" in t and "{quote}" in t, lang
    assert "Ask More" not in json.dumps(localized.IRRELEVANT_SOURCES)       # no slogan is smuggled into (or translated by) these sentences
    assert localized.abstention_message("zz") == localized.INSUFFICIENT["en"]   # unknown language is English, like every other Mo table


# ------------------------------------------------------------------ (4) mixed-language corpora and the router
def _mixed_store():
    store = InMemoryVectorStore(LocalHashEmbedder())
    store.add_chunks([
        DocumentChunk(chunk_id="es1", doc_id="doc-es", text="Prepara preguntas para el empleador y formulalas al final de la entrevista de trabajo.",
                      metadata={"title": "Negociacion", "language": "es", "source_version": "2026-01", "document_type": "interview_guidance"}),
        DocumentChunk(chunk_id="en1", doc_id="doc-en", text="Prepare questions to ask the employer at the end of the interview.",
                      metadata={"title": "Employer questions", "language": "en", "source_version": "2026-02", "document_type": "interview_guidance"}),
    ])
    return store


def _service(responder_text):
    from src.copilot.retrieval import build_retriever

    return CareerIntelligenceService(config=CopilotConfig(), retriever=build_retriever(CopilotConfig(), mode="vector", store=_mixed_store()),
                                     synthesis_responder=lambda m: ModelReply(content=responder_text))


def test_end_to_end_english_question_with_a_spanish_source_states_language_and_quotes_original():
    res = _service("Prepare questions for the employer [1].").answer(
        "preparar preguntas empleador entrevista de trabajo", conversation_language="en")
    assert res.citations and res.citations[0].language == "es" and res.citations[0].version == "2026-01"
    assert "Source [1] is written in español" in res.answer and "a translation, not the source's own wording" in res.answer
    assert "Prepara preguntas para el empleador" in res.answer                       # the original Spanish wording, quoted unchanged
    assert not any(f.startswith("citation attribution") for f in (res.trace.output_findings or []))


def test_end_to_end_same_language_source_has_no_notice_and_other_conversation_language_gets_its_own_sentence():
    res_en = _service("Ask the employer questions [1].").answer("prepare questions to ask the employer at the end of the interview", conversation_language="en")
    assert res_en.citations and res_en.citations[0].language == "en" and "is written in" not in res_en.answer
    res_de = _service("Ask the employer questions [1].").answer("prepare questions to ask the employer at the end of the interview", conversation_language="de")
    assert "Quelle [1] ist auf English verfasst" in res_de.answer and "Übersetzung" in res_de.answer      # German sentence, source language named
    assert "is written in" not in res_de.answer                                           # no English sentence in a German conversation


def test_citation_to_a_source_that_was_not_retrieved_is_stripped_and_no_source_language_is_invented():
    res = _service("Made up claim [9].").answer("preparar preguntas empleador entrevista de trabajo", conversation_language="en")
    assert "[9]" not in res.answer and not res.citations         # the existing output guard removes it; attribution then has nothing to announce
    assert "is written in" not in res.answer


QUESTIONS = {   # one compensation question per language, each about pay (the same lane in every language)
    "en": "How much does a software engineer earn in Germany?", "de": "Wie viel verdient ein Softwareentwickler in Deutschland?",
    "fr": "Combien gagne un développeur logiciel en Allemagne ?", "es": "Cuánto gana un desarrollador de software en Alemania?",
    "it": "Quanto guadagna uno sviluppatore software in Germania?", "pt": "Quanto ganha um programador de software na Alemanha?",
    "nl": "Hoeveel verdient een softwareontwikkelaar in Duitsland?",
}


@pytest.mark.parametrize("lang", SEVEN)
def test_router_routes_the_question_by_its_own_language_regardless_of_the_source_language(lang):
    """Routing sees the QUESTION only: the same pay question goes to the compensation lane with or without a language hint, whatever language the
    knowledge-base sources are in (a Spanish source never changes the lane of an English question, and vice versa)."""
    q = QUESTIONS[lang]
    hinted = ROUTER.route_question(q, None, language=lang)
    unhinted = ROUTER.route_question(q, None)
    assert hinted.lane == unhinted.lane == "compensation"


def test_mixed_language_question_text_is_routed_without_error_and_never_by_source_language():
    mixed = "How much does a desarrollador earn? ¿Cuánto gana?"
    decision = ROUTER.route_question(mixed, None)
    assert decision.lane in {"compensation", "vector"}
    # a Spanish passage in the corpus is irrelevant to routing: only the question text is an input, so the decision is stable across calls
    assert ROUTER.route_question(mixed, None).lane == decision.lane


# ------------------------------------------------------------------ the RAG chain carries the same rule
class _StubRetriever:
    def __init__(self, results):
        self._results = results

    def retrieve(self, query, top_k=5, filters=None):
        return list(self._results)


def _chain(language, text):
    from src.copilot.rag.chain import RagChain

    chunk = DocumentChunk(chunk_id="c1", doc_id="d1", text=text, metadata={"title": "Quelle", "language": language, "source_version": "7"})
    return RagChain(_StubRetriever([RetrievalResult(chunk=chunk, score=0.9)]), responder=lambda m: ModelReply(content="Gemäß der Quelle [1]."))


def test_rag_chain_announces_a_foreign_language_source_and_citation_carries_language_and_version():
    resp = _chain("de", "Verhandeln Sie das Gehalt mit konkreten Erfolgen.").answer("salary negotiation", conversation_language="en")
    assert resp.citations[0].language == "de" and resp.citations[0].version == "7"
    assert "Source [1] is written in Deutsch" in resp.answer and '"Verhandeln Sie das Gehalt mit konkreten Erfolgen."' in resp.answer


def test_rag_chain_same_language_and_unrecorded_language_output_is_unchanged():
    assert _chain("de", "Verhandeln Sie das Gehalt.").answer("q", conversation_language="de").answer == "Gemäß der Quelle [1]."
    assert _chain(None, "Verhandeln Sie das Gehalt.").answer("q").answer == "Gemäß der Quelle [1]."       # an unrecorded language is never asserted
