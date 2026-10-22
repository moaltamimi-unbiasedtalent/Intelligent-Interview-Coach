# 06D Reviewer summary: multilingual retrieval, attribution and abstention (LG-06 sample review)

For the future native-language and independent reviewers. **Nothing here is a review result. LG-06 is NOT met and no retrieval quality is claimed.** Every sentence and dataset below was written by engineering and is neither independent nor native-reviewed.

## What was tested (offline, deterministic, no provider call)

| Area | What the test proves | Where |
|---|---|---|
| Evaluation grid | 49 ordered pairs (question language x source language, seven languages) with 7 questions each; per pair recall@1/3/5, nDCG@1/3/5, MRR (with a seeded bootstrap interval), cross-language rate (X != Y only), sample size and a wide-interval warning. A perfect topic-oracle embedder scores 1.0 on every pair, so the metric code is correct; the local lexical embedder shows same-language better than cross-language, which only describes that embedder | `src/copilot/evaluation/multilingual_pairs.py`, `scripts/eval_multilingual_pairs.py`, `tests/test_multilingual_retrieval_06d.py` |
| Citation attribution | Every `[n]` in an answer maps to a retrieved source (marker, document id, chunk id; a recorded version must agree). A source in another language than the conversation is announced: source language named, statement is a translation, original wording quoted unchanged. No translation step exists in the code | `src/copilot/rag/attribution.py` (wired into `CareerIntelligenceService.answer` and `RagChain.answer`) |
| Abstention | When no retrieved source clears the relevance floor the answer abstains in the conversation language (else the question's language, else English), cites nothing, and says the sources found were not relevant. Tested for all 8 languages and for the 49 pairs with the oracle embedder | `decide_abstention` |
| Mixed-language corpora | Spanish source with an English question, English source with a German conversation, same-language no-notice, unknown source language makes no claim; the language-aware router (02E) routes each question by its own language whatever language the sources are in | `tests/test_multilingual_retrieval_06d.py` |

## What the reviewers must judge (not testable by engineering)

1. **The sentences.** `src/copilot/rag/localized.py`: `IRRELEVANT_SOURCES` (one sentence per language) and `SOURCE_LANGUAGE_NOTICE` (one template per language; slots `{marker}`, `{source_language}`, `{quote}`). Judge: natural, correct register (this file uses informal "du/tu/je" for de/es/it/pt/nl and "vous" for fr, matching the existing Mo sentences), and that the translation statement is unambiguous.
2. **Language names inside sentences.** The source language is shown by its endonym (`Deutsch`, `français`, `español`, `italiano`, `português`, `Nederlands`, `English`), not translated into the conversation language. Decide if a localized exonym is preferred (a table of 7 x 7 names would be needed).
3. **The quote.** The original wording is shown verbatim (whitespace collapsed, at most 200 characters, cut at a word boundary with an ellipsis; double quotes inside it become single quotes). Decide if the limit and the quote punctuation suit each language.
4. **The dataset.** `evaluations/retrieval_multilingual/dataset_v1.json` (7 topics x 7 languages, one question per topic and language) and `evaluations/retrieval_quality/abstention_cases_v1.json` (3 out-of-domain questions per language). Judge naturalness and whether the questions are phrased as native speakers would ask. They are NOT independent: the same author wrote questions and passages, so passages echo the question wording.

## Sample review suggestion (LG-06)

Per language: 20 retrieval questions written by the native reviewer (not derived from the passages) against a corpus of real, versioned sources in at least two other languages; the reviewer marks relevant sources and judges (a) whether the cited source supports the claim, (b) whether the translation notice is present and understandable, (c) whether abstentions on off-topic questions read correctly. The harness `run_pair_evaluation` can score such a set once it is supplied in the dataset format; a live run needs the 05C governor marker and an owner ceiling.

## What was NOT tested

- Retrieval quality of any production embedder (live multilingual benchmark: NOT RUN; needs OD-EMBED, the 05C governor marker and an owner ceiling).
- Whether a model's prose, when it paraphrases a foreign-language source, is faithful (no live model; the rule guarantees the notice and the verbatim quote, not the model's paraphrase).
- Sources whose language was not recorded: the rule makes no claim for them (they are listed in the attribution report, no notice). How much of the real knowledge base carries a `language` metadata value is unmeasured here.
- Mixed-language single passages, non-seven languages, right-to-left or non-Latin scripts.
- Real-user questions, typos, code-switching beyond one mixed-language router case.
- Independent review of citation correctness on real answers; native review of any sentence.
