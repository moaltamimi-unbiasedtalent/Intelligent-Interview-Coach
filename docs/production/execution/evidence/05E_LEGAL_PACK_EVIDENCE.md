# 05E Evidence: privacy, legal and data-rights readiness, PR 2 (legal review pack)

Branch `feat/05e-legal-review-pack`, from `origin/main` f5cf7cb4 (Alembic head `0043_story_bank_completion`). **No migration, no change to any product text.** The engineering safeguards are PR 1 (`feat/05e-privacy-safeguards`, evidence in `05E_EVIDENCE.md`). This PR is documentation, one generator script, one small frontend catalogue-dump helper and one test.

**Claim discipline.** The pack is REVIEW-READY, NOT REVIEWED. It is not final legal copy, not legal advice, and makes no GDPR or other compliance claim. **No counsel sign-off exists and none is recorded anywhere in this PR: legal review (LG-10, PG-04) stays open; counsel is a long lead and has not been appointed (OD-LANG-04 awaiting).** Hosted verification: **NOT RUN.**

## Requirement mapping

| Id | Requirement | Covered here | NOT covered |
|---|---|---|---|
| PRIV-LEGAL | Legal counsel review of Privacy, Terms and policy drafts | The package counsel reviews: exact current texts per language, fact map, diff-able proposals, open questions, checklist, empty sign-off record | **The review itself: NOT DONE** |
| K-PRIV | Privacy, Terms and AI-transparency pages are engineering drafts | The drafts are unchanged and still labelled as drafts; the pack lists what is inaccurate or silent in them (7 findings in the README) | The pages stay drafts until counsel approves replacement copy |
| K-AIGUID | Legal and privacy review of AI-guidance and source-excerpt wording | Section 6 of every language file lists the in-product AI-guidance and source wording and the fixed Mo wording the backend produces without a model; open questions OL-A2 to OL-A5 | Review of that wording: NOT DONE |
| K-GDPR | No GDPR or compliance claim | None made; a test scans the hand-written and generated prose for sign-off and compliance claims and for banned characters | Remains DEFERRED |

## What the pack contains

`docs/production/legal_review/`: `README.md`, `texts/{en,de,fr,es,it,pt,nl}.md` and `texts/ru_PRESERVED_EXCLUDED.md` (generated from the catalogues; the page order is read from the page components, and the generator fails on any page line it does not understand), `texts/MANIFEST.json` (a digest per language and document), `FACTS.md` (generated from `source/facts.json` and the English catalogue: 52 entries mapping every statement of the three pages, and the facts the pages do not state, to `file :: symbol` references), `CHANGE_LIST.md` and `proposed/en_with_proposals.md` (13 proposals, NOT APPLIED, generated from `source/proposals.json`), `OPEN_LEGAL_QUESTIONS.md` (29 questions), `COUNSEL_CHECKLIST.md` (checklist per document, per language, with a sign-off table that reads NOT DONE for every language). Tooling: `scripts/legal_review_pack.py` (`--write`, `--check`), `frontend/scripts/dump-legal-texts.mjs` (read-only esbuild bundle of the catalogue to stdout, writes nothing in the repository).

## Findings surfaced for the owner and counsel (engineering readings, not legal conclusions)

1. **Terms say Premium is EUR 19.99 per month and is selected online after account creation; Premium cannot be bought today** (TF-05; proposal CL-01).
2. **Privacy points to a support address configured for the deployment; none exists** (PF-21; CL-02).
3. Privacy says OCR-extracted text is stored; only the detected claims are (PF-03; CL-03).
4. "AI features send necessary text" understates the categories sent to a model, and a second recipient gets search-query text for embeddings (PF-13, DF-01, DF-02; CL-04, CL-05).
5. AI transparency says "server-side revalidation" of tool calls; that is package 01D, not merged at this commit (AF-05; CL-13).
6. No retention period exists for content, authentication or audit records (DF-05; CL-09).
7. Backups: no code erases or enumerates them; the sentence is a design statement (PF-19, NOT_VERIFIED).

Status counts in `FACTS.md`: 2 CONTRADICTED_BY_CODE, 4 PARTIAL, 3 NOT_VERIFIED, 10 UNSTATED_FACT, 4 NOT_A_CODE_FACT, 29 VERIFIED_IN_CODE (generated; the test checks the summary matches the data).

## Security and privacy impact

None on the product: no source file under `src/` or `frontend/app|components|lib` changes. The pack quotes only product copy and code symbols; it contains no candidate data, no secret and no environment value. The generator reads the catalogue and the backend's fixed Mo wording tables and writes only under `docs/production/legal_review/` (or a temp directory when run without `--write`).

## Tests and commands

| Check | Result |
|---|---|
| `tests/test_legal_review_pack_05e.py` (23): pack matches the catalogues, byte-stable generation, every string of the three pages present in every language, parser fails loudly on an unknown line, every code reference in the fact map resolves, every statement of the three texts is mapped to a fact, README findings backed by the fact map, claims about the code re-checked (billing flags, no contact address, step limit, no analytics script), proposals well-formed and cite real facts and questions, no compliance claim or banned character, sign-off table NOT DONE for all, language readiness still shows no legal qualification, legal page copy and components untouched against `origin/main` | 23 passed (repo venv) |
| Fresh-dependency canary (`$HOME/.cache/ask4mo/ci_venv`) | 23 passed |
| Full backend suite (`pytest tests -n 3 --dist loadfile`, repo venv) | **6300 passed, 41 skipped, 0 failed** (13 min 39 s); the skips are pre-existing, none added |
| `ruff check .`; `scripts/ci_test_shards.py verify --shards 4`; `npm run lint` (frontend, for the new `.mjs` helper) | pass; 301 test files, each in exactly one shard; no ESLint warnings or errors |
| All CI evaluators (`scripts/eval_*.py` and the coverage and corpus scripts listed in `.github/workflows/ci.yml`, with the arguments CI passes), once on the final tree | 49 commands, every exit code 0; the working tree stayed clean; 0 paid or live calls |
| `python scripts/legal_review_pack.py --check` | OK: 12 generated files match the catalogues |

Commands: `python scripts/legal_review_pack.py --check`; `pytest tests/test_legal_review_pack_05e.py -p no:cacheprovider`; `pytest tests -n 3 --dist loadfile -q -p no:cacheprovider`; `ruff check .`; `python scripts/ci_test_shards.py verify --shards 4`; `python scripts/eval_<name>.py`.

## Coordination with PR 1

Some fact-map references point at code that lands with PR 1 (`src/audit_allowlist.py`, `src/privacy/erasure.py`, `acceptance_history`). They are marked `pending-05E-PR1` in `source/facts.json`, rendered "(lands with the 05E engineering PR)" and checked only once the file exists, so this PR passes whether or not PR 1 has merged. After both merge, the lead can drop the marker (a one-word edit per entry) to make the check strict.

## Risks and limits

- The fact map is an engineering reading of the code at one commit; a later change can make an entry stale. The reference check catches a moved or renamed symbol, not a changed behaviour; `FACTS.md` states its commit-relative status.
- The proposals are English only and unapproved; every approved proposal needs seven translations and a native legal review.
- The pack assumes the page component structure (`<h2>`, `<p>`, `<li>`); a new construct makes the generator fail loudly rather than skip text.
- The 13 proposals and the OL questions are an engineer's list, not a legal analysis; counsel may reject or reorder any of it.

## Decisions for the owner

1. Appoint counsel and the per-language legal qualifiers (OD-LANG-04); nothing in the pack can be signed off until then.
2. Decide the plan wording before counsel sees the Terms (CL-01): is Premium described as a preview, or is purchase being enabled first?
3. Name the responsible organisation and a privacy contact (OL-P1, OL-P2): the Privacy text has nothing to point at today.
4. Decide whether to apply any of the 13 proposals before counsel review or leave all copy for counsel to redraft.

## Human, live-staging and gate evidence still missing

Counsel review and sign-off per language (LG-10, PG-04); native-language legal review; any provider's data terms; hosted behaviour (deletion, backups, email delivery, realtime voice); verification of the fact map against a running deployment.

## Throughput

Started 2026-10-22 07:22 CEST (shared with PR 1). First push about 08:55 CEST the same day. Rework rounds: 0 on this branch beyond fixing the generator and fact-map references while authoring (two references and five uncovered statements found by the new tests before the first commit). No CI has run on this branch (CI runs only on a PR, which the lead opens). `origin/main` was unchanged at f5cf7cb4 when this branch was pushed (0 commits to merge). Frontend: no UI source changed; `tsc`, `vitest` and Playwright (reserved port 3124) were NOT run; only the new `.mjs` helper was linted.
