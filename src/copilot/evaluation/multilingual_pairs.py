"""Question-language x source-language retrieval evaluation, all 49 pairs (package 06D, LG-06). OFFLINE and deterministic.

For every ordered pair (X, Y) of the seven languages (en, de, fr, es, it, pt, nl) the questions written in X are run against a corpus that holds ONLY
sources written in Y; the relevant source is the topic's passage in Y. X == Y is the same-language case (7 pairs), X != Y the cross-language case (42).
The frozen 02B dataset is reused unchanged (hash-checked): 7 topics x 7 languages, one question per topic and language, so EVERY pair has n = 7 questions.

Reported per pair: recall@k, nDCG@k, MRR, the cross-language retrieval rate (X != Y only), the sample size and an interval warning. Two further checks ride
on the same grid so the harness proves the whole answer path across languages:

* ``abstention``   the frozen out-of-domain questions (02E) against the same per-language corpus: with the relevance floor, nothing relevant exists, so an
                   answer must abstain, in the question's language, with no citation (``decide_abstention``);
* ``attribution``  a synthetic answer that cites the source of each pair: a source in another language than the conversation gets the translation notice
                   (source language stated, original wording quoted verbatim); a same-language source gets none.

HONESTY RULES (enforced by tests): the result is labelled ``harness proof, not retrieval quality``; it never claims retrieval quality, LG-06 or native
review; the data is synthetic, engineering-authored and NOT independent; an embedder that is not local goes through the 02B paid-call guard first, so a
paid embedder cannot run without the owner's explicit approval environment. No network and no randomness except a seeded bootstrap.
"""

from __future__ import annotations

import random
from collections import defaultdict
from typing import Any

from src.copilot.embedding_budget import guard_embedder
from src.copilot.embeddings import BaseEmbedder
from src.copilot.evaluation import multilingual_retrieval as ML
from src.copilot.models import Citation, RetrievalResult
from src.copilot.rag import attribution as AT
from src.copilot.rag import localized
from src.copilot.retrieval_quality import metrics as M
from src.copilot.retrieval_quality.floor import RelevanceFloor, resolve_floor

LANGUAGES = ML.LANGUAGES
KS = (1, 3, 5)
LABEL = "harness proof, not retrieval quality"
MIN_QUERIES_FOR_STABLE_INTERVAL = 30       # a planning bound, not a statistical test (the same bound the 02E floor calibration uses)
WIDE_INTERVAL_WIDTH = 0.30
BOOTSTRAP_RESAMPLES = 1000
INDEPENDENCE = ("synthetic passages and questions authored by engineering; NOT independent, NOT native-reviewed; every pair has 7 questions, so every "
                "interval is wide and a difference between two pairs is not evidence of anything")


def _r(x: float | None) -> float | None:
    return None if x is None else round(x, 4)


def _bootstrap(values: list[float], seed: int, key: str) -> list[float] | None:
    if not values:
        return None
    rng = random.Random(f"{seed}:{key}")          # a string seed is stable across processes
    means = sorted(sum(rng.choice(values) for _ in values) / len(values) for _ in range(BOOTSTRAP_RESAMPLES))
    return [round(means[int(0.025 * BOOTSTRAP_RESAMPLES)], 4), round(means[int(0.975 * BOOTSTRAP_RESAMPLES) - 1], 4)]


def _warnings(n: int, ci: list[float] | None) -> list[str]:
    out = []
    if n < MIN_QUERIES_FOR_STABLE_INTERVAL:
        out.append(f"wide_interval: n={n} questions (below {MIN_QUERIES_FOR_STABLE_INTERVAL}); read as directional only")
    if ci is not None and ci[1] - ci[0] > WIDE_INTERVAL_WIDTH:
        out.append(f"mrr_interval_width_{round(ci[1] - ci[0], 2)}_exceeds_{WIDE_INTERVAL_WIDTH}")
    return out


def _rank(qvec: list[float], corpus: list[dict], dvecs: dict[str, list[float]]) -> list[tuple[float, dict]]:
    return sorted(((ML._cosine(qvec, dvecs[p["id"]]), p) for p in corpus), key=lambda t: (-t[0], t[1]["id"]))


def _result(score: float, p: dict) -> RetrievalResult:
    return RetrievalResult(chunk=ML._chunk(p), score=score, retriever="vector")


def run_pair_evaluation(embedder: BaseEmbedder, *, dataset: dict | None = None, abstention: dict | None = None, ks: tuple[int, ...] = KS,
                        seed: int = 20260101, floor: RelevanceFloor | None = None) -> dict:
    """Run the 49-pair grid. Deterministic for a deterministic embedder. ``floor`` defaults to the resolved 02E floor for the embedder's identity."""
    embedder = guard_embedder(embedder)
    ds = dataset or ML.load_dataset()
    if abstention is None:
        from src.copilot.evaluation import embedding_benchmark as EB

        abstention = EB.load_abstention()
    passages = sorted(ds["passages"], key=lambda p: p["id"])
    queries = sorted(ds["queries"], key=lambda q: q["id"])
    negatives = sorted(abstention["queries"], key=lambda q: q["id"])
    ident = embedder.identity()
    floor = floor or resolve_floor((ident.provider, ident.model, ident.version, ident.dimensions))
    is_local = getattr(embedder, "provider", None) == "local"

    dvecs = dict(zip((p["id"] for p in passages), embedder.embed_documents([p["text"] for p in passages])))
    qvecs = {q["id"]: embedder.embed_query(q["text"]) for q in queries}
    nvecs = {q["id"]: embedder.embed_query(q["text"]) for q in negatives}
    lang_of = {p["id"]: p["language"] for p in passages}
    langs = [lang for lang in LANGUAGES if lang in {p["language"] for p in passages}]

    pairs: dict[str, dict] = {}
    for x in langs:
        for y in langs:
            corpus = [p for p in passages if p["language"] == y]
            cases = []                      # (query language, ranked ids, relevant ids)
            rows = []
            for q in (q for q in queries if q["language"] == x):
                ranked = [p["id"] for _, p in _rank(qvecs[q["id"]], corpus, dvecs)]
                relevant = {p["id"] for p in corpus if p["topic"] == q["topic"]}
                cases.append((x, ranked, relevant))
                rows.append({"rr": M.reciprocal_rank(ranked, relevant), **{f"recall@{k}": M.recall_at_k(ranked, relevant, k) for k in ks},
                             **{f"ndcg@{k}": M.ndcg_at_k(ranked, relevant, k) for k in ks}})
            n = len(rows)
            ci = _bootstrap([r["rr"] for r in rows if r["rr"] is not None], seed, f"{x}>{y}")
            entry: dict[str, Any] = {"question_language": x, "source_language": y, "n": n, "cross_language": x != y,
                                     "mrr": _r(M.mean_defined(r["rr"] for r in rows)), "mrr_ci95": ci}
            for k in ks:
                entry[f"recall@{k}"] = _r(M.mean_defined(r[f"recall@{k}"] for r in rows))
                entry[f"ndcg@{k}"] = _r(M.mean_defined(r[f"ndcg@{k}"] for r in rows))
                entry[f"cross_language_rate@{k}"] = _r(M.cross_language_retrieval_rate(cases, lang_of, k))
            entry["warnings"] = _warnings(n, ci)

            # abstention: out-of-domain questions never have a relevant source in the corpus
            decisions = []
            for q in (q for q in negatives if q["language"] == x):
                top = [_result(sc, p) for sc, p in _rank(nvecs[q["id"]], corpus, dvecs)[: max(ks)]]
                decisions.append(AT.decide_abstention(top, floor, conversation_language=x, question=q["text"]))
            abst = M.abstention_correctness((d.abstain, True) for d in decisions)
            entry["abstention"] = {"n": len(decisions), "abstained": sum(d.abstain for d in decisions), "false_answer_rate": _r(abst["false_answer_rate"]),
                                   "language_correct": all(d.language == x and (d.message or "").startswith(localized.insufficient_message(x)) for d in decisions if d.abstain),
                                   "no_citation_on_abstention": all(d.cited == () for d in decisions if d.abstain)}

            # attribution: cite the pair's first source in an answer written in conversation language X
            src = corpus[0]
            cit = Citation(marker="[1]", doc_id=src["id"], chunk_id=src["id"], language=y, version="v1")
            retrieved = AT.sources_from_citations([cit], {"[1]": src["text"]})
            issues = AT.check_citations("See [1].", [cit], retrieved)
            text, report = AT.apply_source_language_notices("See [1].", retrieved, conversation_language=x)
            quote = AT.verbatim_excerpt(src["text"])
            expects = x != y
            entry["attribution"] = {"citation_issues": issues, "notice_expected": expects, "notice_present": text != "See [1].",
                                    "source_language_named": (localized.LANGUAGE_ENDONYMS[y] in text) if expects else None,
                                    "original_quoted_verbatim": (quote.rstrip("…") in text) if expects else None}
            pairs[f"{x}>{y}"] = entry

    def roll(selected: list[dict]) -> dict:
        n = sum(e["n"] for e in selected)

        def wmean(key: str) -> float | None:
            vals = [(e[key], e["n"]) for e in selected if e[key] is not None]
            return _r(sum(v * w for v, w in vals) / sum(w for _, w in vals)) if vals else None

        out = {"pairs": len(selected), "n": n, "mrr": wmean("mrr")}
        for k in ks:
            out[f"recall@{k}"], out[f"ndcg@{k}"], out[f"cross_language_rate@{k}"] = wmean(f"recall@{k}"), wmean(f"ndcg@{k}"), wmean(f"cross_language_rate@{k}")
        out["warnings"] = _warnings(n, None) + ["single_author_synthetic_data: a larger n does not remove authoring bias (the 7 topics repeat in every language)"]
        return out

    all_pairs = list(pairs.values())
    att = [e["attribution"] for e in all_pairs]
    ab = [e["abstention"] for e in all_pairs]
    by_q: dict[str, list[dict]] = defaultdict(list)
    for e in all_pairs:
        by_q[e["question_language"]].append(e)
    return {
        "schema_version": 1,
        "label": LABEL,
        "retrieval_quality_claimed": False, "lg06_met": False, "production_quality_evidence": False, "native_reviewed": False, "independent_data": False,
        "embedder": {"provider": ident.provider, "model": ident.model, "version": ident.version, "dimensions": ident.dimensions, "lexical_only": is_local,
                     "label": ML.LOCAL_LABEL if is_local else "non-local embedder run; NOT reviewed as production evidence"},
        "floor": {"value": floor.value, "source": floor.source},
        "dataset": {"name": ds.get("name"), "sha256": ML.dataset_sha256() if dataset is None else None, "passages": len(passages), "questions": len(queries),
                    "abstention_questions": len(negatives), "languages": langs, "pairs": len(pairs), "questions_per_pair": 7,
                    "authored_by": "engineering (not native-reviewed, not independent)"},
        "ks": list(ks),
        "pending": ML.PENDING_STATEMENT,
        "rollups": {"same_language": roll([e for e in all_pairs if not e["cross_language"]]), "cross_language": roll([e for e in all_pairs if e["cross_language"]]),
                    "by_question_language": {x: roll(es) for x, es in sorted(by_q.items())}},
        "pairs": pairs,
        "abstention_summary": {"cases": sum(a["n"] for a in ab), "abstained": sum(a["abstained"] for a in ab),
                               "language_correct_everywhere": all(a["language_correct"] for a in ab),
                               "no_citation_on_abstention_everywhere": all(a["no_citation_on_abstention"] for a in ab),
                               "note": "false answers here are the LEXICAL hash embedder scoring shared function words above the strict default floor; "
                                       "it measures the harness, not a real embedder's abstention"},
        "attribution_summary": {"pairs": len(att), "notices_expected": sum(a["notice_expected"] for a in att), "notices_present": sum(a["notice_present"] for a in att),
                                "all_citations_map_to_retrieved_sources": all(not a["citation_issues"] for a in att),
                                "source_language_always_named": all(a["source_language_named"] in (None, True) for a in att),
                                "original_quote_always_verbatim": all(a["original_quoted_verbatim"] in (None, True) for a in att)},
        "limitations": [INDEPENDENCE,
                        "the corpus per pair holds 7 passages (one per topic): recall and MRR are easy to saturate and rank differences are not meaningful",
                        "the hash embedder is lexical: cross-language pairs score only through shared tokens, so low cross-language numbers describe that embedder, not multilingual retrieval",
                        "the live multilingual benchmark (production embedder) needs the 05C governor marker and an owner ceiling and was NOT RUN"],
    }
