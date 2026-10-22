# 06H Evidence: language activation control (fail-closed enforcement of LG-01 to LG-14)

Branch `feat/06h-language-activation`, from `origin/main` f9a06a9 (06A merged). No migration. Requirements: REQ-LANG-11, REQ-LANG-13, REQ-LANG-14; owner decisions OD-LANG-03, OD-LANG-04 (they supply the named approvers; neither is decided here).

## 0. Position, stated plainly

- **ZERO languages are qualified.** The committed record (`docs/production/execution/language_readiness.json`) is unchanged in substance: no language has a release SHA, a named approver or an approval date on any gate, so none can pass the validator. A test asserts this (`test_committed_record_has_zero_qualified_languages_and_enforced_mode_offers_nothing`).
- **In a hosted environment (production, staging, or any unrecognised `API_ENV`) the product therefore offers no language and accepts no new language-bearing activity today.** That is the intended fail-closed outcome of this package, not a defect. It is a decision the owner should see before the first staging deploy (section 5).
- Nothing here approves, qualifies or translates anything. The mechanism is proven only with synthetic fixtures. All fourteen gates for all seven languages still need the human, legal and live evidence listed in section 7.

## 1. Requirement mapping

| ID | Covered | How | NOT covered |
|---|---|---|---|
| REQ-LANG-11 (per-language, per-gate status) | Yes | Validator derives `QUALIFIED / INCOMPLETE / UNQUALIFIED` plus a gate count per locale; Admin readiness row shows counts and state only; `/capabilities` shows offered and unqualified locale codes | Admin per-gate matrix page (follow-up, section 6) |
| REQ-LANG-13 (no early claim) | Yes | Claim flags `production_qualified` and `offered_to_real_users` are claims: they must equal the derived result in both directions, so a flag cannot be flipped alone; no page text changed to claim anything | Public-page copy review stays with 06A's claims gate |
| REQ-LANG-14 / LG-14 (Russian out, Admin English-only, speech unchanged) | Yes | A record for any locale outside `ACTIVE_CANDIDATE_LOCALES` (Russian included) makes the whole file untrustworthy and nothing qualifies; `ru` is refused in every mode; Admin catalogues, speech and OCR lists untouched | |
| OD-LANG-03 / OD-LANG-04 (native reviewer, legal qualifier) | Mechanism only | LG-10 and LG-11 need a named approver like every gate; the people are the owner's decision | Naming reviewers, any sign-off |

## 2. The qualification record (format and rules)

One committed, reviewed file. A locale is qualified only when `validate_locale_record` returns no problem at all:

- `gates` has exactly the fourteen keys LG-01..LG-14, no unknown key, no missing key, no duplicate key (the loader rejects duplicate JSON keys, so a duplicated gate or locale cannot silently keep the last value).
- Every gate is `PASS`. Every PASS carries: `evidence` (a reference of at least 8 characters, not a placeholder), `approver` (a named person: not empty, not a placeholder such as TBD, and not an automation or engineering label such as Claude, bot, CI, "Engineering team"), `approved_on` (ISO date, not in the future) and `release_sha` (7 to 40 hex).
- The locale carries `release_sha`; every gate's `release_sha` must equal it. **Staleness rule (deterministic, offline):** a gate approved at any other SHA is stale; an optional `approved_until` date that has passed makes the gate stale. Ancestor checking against git history is deliberately not used (it needs a repository at run time); binding to one explicit SHA plus an optional expiry is simple and testable. Whether the running build equals or descends from that SHA is checked by the release go/no-go (08A), not by this module.
- `production_qualified` and `offered_to_real_users` equal the derived result (true only when qualified, false otherwise). Editing a status string, a flag or any single field cannot enable a language.

Resolution (`src/language_activation.py`, pure `resolve`):

| Mode (from `API_ENV`, server side) | Offered and accepted for new activity |
|---|---|
| `enforced`: production, staging, any unknown value | only qualified locales. **If none qualifies the set is empty and every new language-bearing activity is refused.** English is not an exception and is not declared qualified |
| `labelled`: development, local, test | the seven active locales, each labelled UNQUALIFIED unless the record qualifies it |

An unreadable, missing, malformed or duplicate-keyed record fails closed (nothing qualifies; labelled mode still lists the seven but never marks one qualified). The mode and the record are code and committed file: no Admin setting, request field or environment variable can change the record, and the only environment input is `API_ENV` itself.

## 3. Changes

Backend
- New `src/language_activation.py` (validator, pure resolver, runtime accessor, entry-point guard, safe summaries, test-only seam).
- Guard `require_locale_activated` (422, code `language_not_activated`, fixed safe message, no echo) at every entry point 06A guards: account registration (`locale`), preferences (interface and conversation language, checked before any field is written), Career chat, agent run, interview creation (both `configuration` and `preparation_context` forms). An omitted language means the default language and is **not exempt**. The 06A schema rejection for an excluded or unknown locale is unchanged (`invalid_request`, 422): Russian is still refused there first.
- `GET /api/v1/capabilities`: `active_candidate_locales` is now the OFFERED set (the seven in development, empty in a hosted environment until a locale qualifies); additive `language_activation_mode`, `qualified_locales`, `unqualified_locales`, `no_language_available`. Locale codes and mode only.
- Admin: a read-only `language_activation` row in the existing `GET /admin/readiness` (`platform.overview.read`, no new permission, still 44 permissions): counts of qualified locales, gate records at PASS, mode, offered count; no evidence text, approver names or SHAs.
- `deploy/Dockerfile.api` and `.dockerignore` now ship the record into the image (docs were excluded, which would have made every hosted deployment fail closed for a packaging reason). Not verified by an image build (no Docker in this environment).
- Test-only seam `install_test_records`: refuses unless `pytest` is imported and `PYTEST_CURRENT_TEST` is set; no production module references it (static test); a subprocess test proves it refuses in a clean interpreter.

Frontend
- `frontend/lib/i18n/offeredLocales.ts` (`useOfferedLocales`, pure `offeredLocalesFrom`): selectors render the server-offered subset, label unqualified locales, and show a disabled state with a clear note when none is offered. While the answer is unknown (loading, offline) the static seven are shown as before; the server still enforces.
- `LanguageMenu`, `ConversationLanguageField`, `LanguageSettings` use it. Two new keys (`common.languageUnqualified`, `common.languagesNoneAvailable`) in all eight catalogues (engineering translations, unreviewed, parity kept; the scanner stays at 0).

Existing tests and checks adjusted (strengthened or moved, nothing weakened)
- `tests/test_language_boundaries_06a.py::test_frontend_active_list_matches_backend_exactly` and `scripts/eval_i18n_l10n.py` (`active_locales_frontend_backend_parity`): they asserted that selectors literally contain `SELECTABLE_LOCALES.map`. Selectors now render `useOfferedLocales().options`, which is derived from `SELECTABLE_LOCALES.filter` in `offeredLocales.ts`; both checks now require that chain and still forbid `APP_LOCALES.map`.
- `docs/production/execution/evidence/06A_LOCALE_AUDIT.md` regenerated with `scripts/eval_locale_inventory.py --write`: the only change is the interface key count 2382 to 2384 (two new keys per locale). `scripts/eval_locale_inventory.py` itself and its freshness comparison are untouched.

## 4. Security and privacy impact

No new data, table, migration, secret, provider call or network call. The guard returns one fixed code and message that does not echo the requested locale. Capabilities exposes locale codes and the mode only (no gate detail, names or SHAs); gate counts are Admin-only. Account controls (sign-in, `/auth/me`, privacy and deletion, preference changes that do not touch a language) are not language-gated, and reading an existing session is not new activity. Cross-user isolation is unaffected (no new resource). Risk accepted: the activation mode trusts `API_ENV`; a hosted deployment that sets it to a development value would show the seven labelled UNQUALIFIED and accept all of them (documented in section 6).

## 5. Behaviour the owner must decide or know

1. **Fail-closed means staging and production accept no candidate registration, preference change to a language, Career chat, agent run or interview until at least one language has a complete approved record.** There is deliberately no bypass. If the owner wants a staging environment for synthetic testing, either set it to a development-class `API_ENV` for that environment or qualify one language; the code will not special-case English.
2. Whether `approved_until` expiry should be mandatory (currently optional) and whether the SHA binding should require descent from the deployed build.
3. The named approvers for LG-05, LG-06, LG-07, LG-10, LG-11 (OD-LANG-03, OD-LANG-04, owner).

## 6. Risks and limitations

- The SHA binding is an equality check between the record's own SHAs; it does not read git. A record approved at an earlier SHA stays valid until edited or expired; 08A (go/no-go) must compare it with the release SHA.
- `API_ENV` misconfiguration is the single input that selects the mode; unknown values fail closed, a deliberate development value does not.
- The Admin per-gate view is not built: the data is available through the readiness row and `admin_summary`, but a per-locale Admin page needs its own permission decision (follow-up).
- Existing interview sessions and stored preferences in a now-unoffered language are left intact (read-only continuation is not new activity); resuming provider-backed steps in such a session is not blocked by this package.
- Dockerfile and `.dockerignore` change not verified by building an image.
- The seam guard relies on pytest being imported plus `PYTEST_CURRENT_TEST`; an attacker who controls the process environment and imports pytest already controls the process.

## 7. What remains (all human, legal or live evidence; nothing below exists)

All fourteen gates for all seven languages need evidence at a named SHA with a named approver before any language can be offered. Concretely: native human review of interface text, Mo samples and interview questions (LG-11, OD-LANG-03); legal and privacy translation qualification by counsel or a qualified translator (LG-10, OD-LANG-04); per-language candidate journeys with screenshots (LG-03, 06C); prompt and policy suites per language (LG-04); blinded interview-quality rating (LG-05); multilingual RAG and attribution evaluation (LG-06, 06F); owner market-mapping decision and source qualification (LG-07, OD-LANG-02); per-language injection, security and privacy suites (LG-08); Story Bank and Workspaces per language (LG-09); the Mo language ownership tests per language (LG-12); the generated matrix and claims test closing LG-13; LG-01, LG-02 and LG-14 need an approver and release SHA recorded in the new fields (their engineering evidence exists from 06A but is not an approval). Live multilingual Mo quality is not measured.

## 8. Tests and commands

| Command | Result |
|---|---|
| `tests/test_language_activation_06h.py` (.venv) | see section 9 |
| Targeted language, openapi and 06A suites (.venv and /tmp/ci_venv) | see section 9 |
| `ruff check .` | All checks passed |
| `scripts/ci_test_shards.py verify --shards 4` | OK: 281 test files, each in exactly one of 4 shards (before the final count) |
| All 46 `scripts/eval_*.py` named in CI (/tmp/ci_venv) | 46 of 46 exit 0 |
| `cd frontend && npx tsc --noEmit`, `npm run lint` | clean |
| `cd frontend && npx vitest run` | 115 files, 1145 tests passed |
| `node frontend/scripts/scan-i18n.mjs --count` | 0 |
| `E2E_PORT=3104 npx playwright test language-activation-06h language-selection-06a` | 9 passed |
| `E2E_PORT=3104 npx playwright test i18n onboarding data-privacy experience-closure trust-polish settings-memory russian-locale` | 52 passed, 11 skipped (the dormant Russian specs from 06A) |

Pre-existing failure, not caused by this package: `tests/test_knowledge_persistence_02a_identity.py::test_no_forbidden_files_were_touched_and_no_migration_in_part_one` diffs the working tree against the stale ref `origin/feat/02k-knowledge-contract`, which already differs from `origin/main` in `src/agent/`, `.github/workflows/ci.yml` and others, so it fails on a clean main as well. Reported, not edited.

## 9. Final counts, SHA, throughput

(Filled in after the final full run; see the delivery report.)

CI: not available until a PR exists. Compare URL: `https://github.com/moaltamimi-unbiasedtalent/Intelligent-Interview-Coach/pull/new/feat/06h-language-activation`.
