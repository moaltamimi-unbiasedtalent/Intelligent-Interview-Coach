# Legal review pack for counsel (package 05E, PR 2)

**Status: REVIEW-READY, NOT REVIEWED.** This folder is the material a qualified reviewer needs to review Ask4Mo's Privacy, Terms and AI-transparency texts. It is **not** final legal copy, **not** legal advice and **not** a claim that Ask4Mo complies with any law. **No counsel sign-off exists.** Legal review (LG-10, PG-04) is open, counsel is a long-lead resource, and nothing here may be recorded as done on counsel's behalf. The legal page copy in the product is unchanged by this package.

## What is here

| File | What it is | How it is made |
|---|---|---|
| `texts/<code>.md` (en, de, fr, es, it, pt, nl) | The exact current Privacy, Terms and AI-transparency texts, in the order the page shows them, plus the Trust page, the in-app Data & Privacy copy and the in-product AI-guidance and source wording (K-AIGUID), including the fixed Mo wording the backend produces without a model | Generated from the product catalogues by `scripts/legal_review_pack.py` |
| `texts/ru_PRESERVED_EXCLUDED.md` | The Russian texts, preserved in the code but not offered to users (REQ-LANG-14) | Generated |
| `texts/MANIFEST.json` | A digest per language and document, so any later change to a legal string is visible as a changed digest | Generated |
| `FACTS.md` | The data-flow and retention facts the texts rely on: every statement mapped to the code that makes it true (file and symbol), with an engineering status, and the facts the texts do not state | Generated from `source/facts.json` and the catalogue; references are checked by a test |
| `CHANGE_LIST.md` and `proposed/en_with_proposals.md` | A diff-able list of PROPOSED English copy changes with reasons, and the whole English text with them applied (diff it against `texts/en.md`). Not applied | Generated from `source/proposals.json` |
| `OPEN_LEGAL_QUESTIONS.md` | The questions engineering cannot answer | Written by hand |
| `COUNSEL_CHECKLIST.md` | A checklist for the qualified review, per document, per language and cross-cutting, and an empty sign-off record | Written by hand |

Regenerate with `python scripts/legal_review_pack.py --write`; `python scripts/legal_review_pack.py --check` (and `tests/test_legal_review_pack_05e.py`) fails if a committed generated file no longer matches the catalogues, so the pack cannot silently go stale when the product copy changes.

## Findings counsel should read first

These come from `FACTS.md` and are readings of the code, not legal conclusions.

1. **The Terms say Premium is EUR 19.99 per month and is selected online after account creation. Today Premium cannot be bought** (no purchase path, live billing disabled by a code constant, external checkout not authorised). See TF-05 and proposal CL-01.
2. **The Privacy text points to "the support address configured for your deployment". No such address exists** in the configuration or code. See PF-21 and proposal CL-02.
3. **The Privacy text says OCR-extracted text is stored; only the detected claims are** (the full text is re-read from the private file on demand). See PF-03 and CL-03.
4. **"AI features send necessary text (not secrets) to a model provider" understates the categories** (messages, approved Memory summaries, selected job-description text, approved evidence snippets, Practice answers, selected stories) and omits a second recipient for search-query embeddings. See PF-13, DF-01, DF-02, CL-04, CL-05.
5. **The AI-transparency text says tool calls have "server-side revalidation".** The allow-list exists; full revalidation of every model-requested call is package 01D, not merged when this pack was written. See AF-05 and CL-13.
6. **No fixed retention period exists** for content, authentication records or audit records; the texts are silent. See DF-05, CL-09, OL-P8.
7. **Backups:** no code erases or enumerates hosting backups; the sentence about them is a design statement, not an observed behaviour. See PF-19.

## What this pack does not do

- It does not decide a lawful basis, a controller identity, a retention period, a processor list, a transfer mechanism, a data-access procedure or any wording that makes a legal commitment. Each is a question in `OPEN_LEGAL_QUESTIONS.md`.
- It does not assert GDPR, AI Act or any other compliance. The product's own texts say they are drafts; that stays true until counsel decides otherwise.
- It does not verify hosted behaviour, live providers or human translation quality. **Hosted verification: NOT RUN.**
- It does not apply any proposal. Approved proposals would be applied in a later change, then translated and reviewed per language.

## Related engineering work

The engineering safeguards (deletion, ownership index, acceptance history, audit allow-list, report differencing) and the DSAR options are in the 05E engineering PR (`feat/05e-privacy-safeguards`); its decision record is `docs/production/execution/PRIV_DSAR_DECISION_RECORD.md`.
