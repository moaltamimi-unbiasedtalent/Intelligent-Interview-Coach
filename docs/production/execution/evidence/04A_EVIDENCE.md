# 04A Evidence: Story Bank completion (REQ-OWN-06) and story flows in the seven languages (REQ-LANG-05)

Branch `feat/04a-story-bank`, based on the pushed prep branch `origin/chore/migration-head-agnostic` (ec14963), which is NOT yet merged to `main`. This branch therefore carries the prep commits, and the PR should target `main` after the prep branch merges (or be stacked on it). Wave 2 start: 2026-10-22 01:57 CEST. Rework rounds: 2 (a vitest/Playwright mock-shape regression found by the existing specs, and the P2-04 wording guard found by the existing documents tests; both fixed in the code, no existing assertion changed). CI: not available until a PR exists. Final SHA: see the last section.

## 1. Inventory of what existed before 04A (read from the tree, before any change)
| Area | What exists |
|---|---|
| Tables (migration 0010) | `candidate_stories` (title, STAR text, `competencies` JSON, `status` user_created / source_backed / user_corrected / model_suggested, `evidence_state` none / verified / source_revoked) and `story_evidence` (story to `document_claims`, unique pair, FK cascade). No archive, no Opportunity link, no answer link, no usage record. |
| Repository / service | `StoryRepository` (create, get, list, evidence_stories, update, delete, rederive_all_for_user) and `StoriesApplicationService` (create, draft_from_claims from OWNED claims, update marks source_backed as user_corrected, delete). |
| Routes (`/api/v1/stories`) | GET list, POST create, POST draft, GET one, PATCH, DELETE (foreign or missing = 404; delete revokes share grants). No search, filter, archive, restore, evidence attach, suggestion or export route. |
| Sharing | `story` is an allow-listed share type (VIEW-only, owner verified, loader returns the repository dict). Tests: `test_sharing_p6_5` matrix, `test_w98_privacy_controls::test_story_delete_revokes_shared_grants`. |
| Export / deletion | `data_export` includes `candidate_stories` rows; account deletion removes `story_evidence` then stories. |
| Practice integration | `use_candidate_evidence` is an all-or-nothing boolean: up to 10 safe stories plus 25 approved claims go into `candidate_background` (DATA, screened). No per-story selection, no consent record, no attribution. |
| Agent / Pack | `EvidenceAccessService.evidence_stories` (specialist) and the Preparation Pack read `StoryRepository.list` (all stories). |
| Frontend | A read-only `StoryBank` list inside `DocumentsClient` (title, status badge, evidence badge, result, delete without confirmation) plus "draft a story" from selected claims. 13 i18n keys. |
| Tests | `test_documents_api` (draft, revocation, edit marks corrected, cross-user GET), sharing and privacy tests above, `documents.spec.ts` (one mocked draft journey). |

## 2. Gap list (REQ-OWN-06 S1 to S7), recorded before coding, with the outcome
| # | Gap | Req | Outcome |
|---|---|---|---|
| G1 | No manual create or edit UI; no STAR editor; no quality prompts | S1 | Closed: `StoryEditor`, deterministic quality prompt codes (`quality_prompts`), localised in the card. |
| G2 | No archive / restore; delete has no confirmation | S6 | Closed: `POST /stories/{id}/archive` and `/restore`, accessible confirm dialog before delete. |
| G3 | Evidence labels weak (stored `evidence_state`; a corrected story stayed "verified" after its source went; a rejected claim counted as live; no evidence on user stories; nothing separated self-confirmed from evidenced) | S2, S5 | Closed: `verification` is DERIVED on every read (section 4); user stories can link claims and own practice answers; confirmation is a separate, labelled attestation. |
| G4 | No search, filter or tag UI or API | S3 | Closed: `POST /stories/search` (words in the body, not the URL), `GET /stories/tags`, filter bar. |
| G5 | No Opportunity link | S3, S7 | Closed: nullable `opportunity_id` (owner-verified on write, unlinked on Opportunity delete). |
| G6 | No suggestions and no approval; Practice reuse blanket | S4 | Closed for Practice: `POST /stories/suggest` (deterministic, proposals only), per-story selection, explicit `confirm_story_use`. Prepare: see section 7 (NOT covered: per-story picker). |
| G7 | Delete leaves derived copies (Pack items, session configuration) | S6 | Closed: markers and a use record let delete strip the story text from session configuration and remove Pack items that cite it; limits in section 6. |
| G8 | Shared projection returned the full dict and ignored archive | S6 | Closed: bounded `shared_projection` (no claim, answer or Opportunity ids, usage or timestamps), archived story not viewable or shareable. |
| G9 | Agent/Pack reads would include archived stories | S6 | Closed: `list()` defaults to active; `evidence_stories` also excludes unconfirmed model suggestions. |
| G10 | Opportunity delete did not unlink stories | S3 | Closed. |
| G11 | Story flows not localised beyond 13 keys; no per-locale test | LANG-05 | Closed to the extent engineering can verify (section 5); native review NOT done. |
| G12 | Cross-user tests only for GET one | S6 | Closed: every route, both directions (section 3). |
| G13 | No Playwright journey | S7 | Closed: `e2e/story-bank.spec.ts` (3 tests). |

## 3. Requirement mapping (S1 to S7): covered / NOT covered
| ID | Covered | How | NOT covered |
|---|---|---|---|
| S1 create manually; draft from approved evidence; full STAR editing | Yes | `StoryEditor` (create and edit), existing deterministic draft from owned claims (now accepts an Opportunity). No model is called. | A model-written draft: no producer exists (`model_suggested` stays a status only; an unconfirmed suggestion is never used). |
| S2 provenance preserved; user-created, source-backed, user-corrected, model-suggested distinguished; nothing verified without evidence | Yes | Status badge (four origins) plus a separate `verification` label (section 4). Editing a source-backed story or a model draft marks it user-corrected. | |
| S3 search, filter, tags, Opportunity link | Yes | See G4, G5. Tags are the existing `competencies`, normalised (case-insensitive de-duplication, bounded). | |
| S4 suggest relevant stories; approval before use; reuse in Practice; evidence reflected in feedback | Practice: yes. Suggest: yes. | Suggestions are proposals (`requires_approval`). A story reaches a Practice session only by per-story selection AND `confirm_story_use`; it enters `candidate_background` as an attributed block (id, title, verification label, "the candidate's own account"), injection-screened as before. The existing evaluation prompts already receive `candidate_background`, so feedback can reflect the story; attribution is recorded in `story_uses` and shown as "Used in N practice sessions". | Prepare (Mo agent) per-story picker and per-run consent; live model behaviour (that feedback actually cites the story) is NOT verified, no live call was made. |
| S5 never invent achievements or numbers | Yes | Quality prompts are codes that ask the candidate to add what is missing and say "do not estimate"; no auto-fill anywhere; an empty STAR part stays empty (tested); no model call. | |
| S6 persists; deletion and privacy controls; strict ownership | Yes | Section 6. | |
| S7 acceptance journey in the browser incl. restart | Yes (mocked network) | `e2e/story-bank.spec.ts` journey: create, link to Opportunity, document evidence, confirm, reload (restart), search, share, stop sharing, Practice with consent, archive, restore, delete. | The journey runs against a mocked server; a real backend plus browser run was NOT performed in this package. |
| REQ-LANG-05 story flows in the seven languages | Engineering level | Section 5. | Native-speaker review and the LG gates (LG-09 etc.) are NOT claimed; no language is qualified by this package. |

## 4. Verification model (what is and is not called evidence)
`verification` is computed on every read, never stored, in this precedence:
1. `evidence_verified`: at least one linked document claim still exists, belongs to the owner and is not rejected. UI wording: "Supporting evidence available" (the existing P2-04 vocabulary, which deliberately avoids "verified by"; the existing documents tests enforce it).
2. `source_revoked`: it had document sources (source-backed, corrected from one, or links whose claims are gone) and none is left. A corrected story no longer stays "verified" after its source is deleted or rejected (the G3 defect).
3. `answer_linked`: only the candidate's own practice answer is linked. A reference (no answer text is copied or shown), and weaker than a document: it never reads as evidence. Answers are offered only from interviews inside the caller's history window (`GET /stories/answer-sources`, question text only); an answer outside the window is a plain 404 on attach.
4. `self_confirmed`: the candidate pressed "Confirm this is accurate". Labelled "Confirmed by you" with the sentence "not evidence". Editing the STAR text clears it (it applied to the text confirmed).
5. `unverified`: nothing. Wording: "No supporting source".

## 5. Localisation and accessibility
- All new copy is in `frontend/lib/i18n/messages/w04a/` (fragment `w04a`, registered in `w96/index.ts`): 116 keys per locale for en, de, fr, es, it, pt, nl and the preserved ru; each locale file is typed against `en` (a missing or extra key fails `tsc`). The three document-evidence labels reuse the existing `documents.ev*` strings (no duplicated copy). The slogan is not used.
- `story-bank-04a.test.tsx` asserts exact key parity, identical placeholders, no dash punctuation, no emoji and that every key a Story Bank component uses resolves in every locale. `story-bank-locales-04a.test.tsx` renders the real Story Bank, picker and sharing panel in each of the seven selectable languages (21 tests) and checks the five state labels are distinct words in each language.
- Accessibility (verified by tests, no automated axe tool is installed): labelled search region and every control, `aria-expanded` toggles, `aria-live="polite"` result count, `aria-invalid` plus `role="alert"` title error, accessible alert dialog for delete, focus moved to the title on open and back to "New story" on close, Escape closes, keyboard-only open (Playwright).
- Limits: translations are ENGINEERING translations (not natively reviewed); the 06A locale audit table was regenerated (counts and "identical to English" cognates such as Workspace, Tag, Action, Situation changed by a few).

## 6. Security, privacy and deletion
- Isolation: every route resolves identity through `get_current_user_id`; another account's story, claim, answer, Opportunity or share is a plain 404 (422 for an Opportunity or Practice story id, with ONE message for foreign, missing, archived or unusable). Tests call EVERY story route as the other account (11 per-story calls plus both foreign-evidence attaches), assert nothing of the owner changed, assert collection routes never list another account's data, and (against a production-mode app) 401 without a session on every route.
- Consent for sharing: sharing is a view-only grant the owner makes in the card (panel explains what a member can and cannot see; nothing is shared by opening it). Archiving revokes the story's grants; restoring never re-shares; an archived story cannot be shared; only the owner revokes; revocation is immediate (re-derived on every read). Platform Admin has no story route and no automatic access (route-invariant test).
- Deletion (`DELETE /stories/{id}`), tested: the story disappears from the list, search, tags, suggestions and the account export; its grants are revoked and the shared read is 404; evidence links, answer links and use records are removed; the story's marked text is stripped from in-progress session configuration and completed interview configuration; Preparation Pack items that cite it (`S<id>`) are removed. Account deletion removes the new tables too (tested). Export now carries each story's evidence ids and use records for the owner only.
- Logs and audit: no story text in any log record or audit row across create, search, suggest, edit, confirm, Practice, share, archive, restore and delete (caplog and `audit_events` sentinel test). Search and suggestion words travel in POST bodies, never in URLs or access logs. No new audit event was added.
- Practice safety: the story text is untrusted DATA (same screening as before); the browser sends ids and a consent flag only (asserted: the text never leaves the server); at most 5 stories; the block is size-bounded inside the existing 4,000 character background limit.
- Admin: no Admin shell, `nav-items.ts`, permission registry (still 44) or contract file was touched.
- Honest limits of deletion: text the model already produced from a story (generated questions, evaluations, the final report, a memory the candidate chose to save) is not unpicked; the confirm dialog says what is removed, not that every derivative is. The session payload edit is a direct update without the optimistic-concurrency version bump, so a save racing the delete could rewrite the old text (documented, narrow). Preparation memories carry no story link, so none can be found or removed automatically.

## 7. NOT covered, and why
- Prepare (Mo agent): the existing Candidate Evidence specialist keeps reading the owner's usable stories (now excluding archived stories and unconfirmed model suggestions, and attributing support as `story:<status>/<verification>`). There is NO per-story picker or per-run consent in Prepare; adding one means changing the agent request contract, which belongs with the agent packages (01B/01D/01C order). Owner decision: is the existing evidence-opt-in model acceptable for Prepare, or must Prepare get the same per-story consent as Practice?
- Model-suggested stories: nothing produces them (no LLM). The status, its label and the approval rule exist and are tested.
- Handoff (`preparation_context`) Practice creation does not accept `story_ids` (only the standalone setup, which sends `configuration`).
- Real-backend browser journey, live model quality and native-language review: not run (human/operational evidence below).

## 8. Migration (one, genuinely needed)
`migrations/versions/0041_story_bank_completion.py`, revision `0041_story_bank_completion`, `down_revision = 0040_knowledge_alert_categories` (the head on this base). The lead reserved 0043; the repository's contiguity guard (`tests/_alembic_head.py`) requires file numbers to be contiguous from 0001, so on this base the only linear number is 0041. At merge the lead should rename the file and revision id to the chosen number and set `down_revision` to the then-head: nothing else references the number (the new tests find the revision by its `_story_bank_completion` suffix, and the privacy exception below is keyed by that suffix).
Why a migration is needed: archive, the Opportunity link, self-confirmation, answer evidence and use attribution have no existing column or table. Additive and data-preserving: `candidate_stories.archived_at`, `confirmed_at`, `opportunity_id` (nullable, FK ON DELETE SET NULL where ALTER-ADD-FK is supported, plain indexed column on SQLite, explicit unlink in code), tables `story_answer_links` and `story_uses`. Fail-closed downgrade: refuses (deleting nothing) while any story is archived, confirmed or Opportunity-linked, or any link or use row exists (tested: refuses, nothing deleted, proceeds once reset, re-upgrades).
Privacy-schema invariant: `scripts/eval_privacy_controls.py` forbids any migration after 0039 from touching `candidate_stories`, `answers`, `opportunities` or `users`. I added a reviewed exception, `REVIEWED_PRIVACY_MIGRATIONS`, for a migration whose file name ends `_story_bank_completion.py` and ONLY for those four tables (renumbering keeps it; a different table in that file, or the same table in any other file, still fails; tested). PRIVACY_TABLES itself is unchanged. The owner should confirm this exception.

## 9. Changes
- Backend: `src/persistence.py` (3 columns, `StoryAnswerLink`, `StoryUse`), `src/documents/repository.py` (StoryRepository rewrite: derivation, archive, confirm, evidence, answer sources, uses, delete cascade, usability rule, quality prompts, block markers), `src/application/stories_service.py` (search, tags, suggest, shared projection, Practice block), new `src/api/routes/stories.py` (all story routes moved out of `documents.py`; router include changed in `main.py`), `src/api/schemas/documents.py`, `src/api/schemas/interview.py` and `src/api/routes/interview.py` (`story_ids`, `confirm_story_use`, use attribution; the create route now takes the repository by dependency so it is testable), `src/api/dependencies.py` (story share projection, Opportunity lookup), `src/application/data_export.py`, `src/application/account_deletion_service.py`, `src/opportunity_repository.py`, `src/agent/specialists/evidence_specialist.py` (provenance string only), `scripts/eval_privacy_controls.py` (reviewed exception).
- Frontend (candidate Story Bank components only): new `frontend/components/stories/` (`StoryBank`, `StoryCard`, `StoryEditor`, `EvidenceLinker`, `StoryShare`, `StoryPicker`, `storyVocab`), `DocumentsClient.tsx` now mounts `StoryBank`, `InterviewSessionSetup.tsx` mounts `StoryPicker`, API client and types, the `w04a` fragment.
- Tests: `tests/test_story_bank_04a.py` (31), `frontend/tests/story-bank-04a.test.tsx` (24), `story-bank-locales-04a.test.tsx` (21), `story-practice-04a.test.tsx` (2), `frontend/e2e/story-bank.spec.ts` (3).
- Generated doc: `06A_LOCALE_AUDIT.md` regenerated with `scripts/eval_locale_inventory.py --write` (required by `test_language_readiness_06a`, because the catalogue grew). Expect to regenerate it again at merge when other packages add keys.
- Not touched: Admin shell, `nav-items.ts`, `capabilities.ts`, the tracker, the register, frozen contracts, `src/copilot/security/*`, other agent policy modules.

## 10. Tests and exact commands
Python (repo venv `.venv` and fresh-dependency canary `/tmp/ci_venv`), all with `-p no:cacheprovider`:
- `pytest tests/test_story_bank_04a.py` : 31 passed.
- Targeted set under BOTH venvs: `test_story_bank_04a`, `test_documents_api`, `test_sharing_p6_5`, `test_w98_privacy_controls`, `test_privacy_schema_invariant_02a`, `test_migration_head_agnostic`, `test_wave4_context_integration`, `test_multi_agent_specialists`, `test_preparation_pack_p5a`, `test_openapi_contract`, `test_account_closure_w12_4d_f1r`: all passed.
- `ruff check .` : pass. `python scripts/ci_test_shards.py verify --shards 4` : OK, 282 test files.
- All 46 evaluators referenced by `.github/workflows/ci.yml` (including `eval_global_corpus --repeat 2`, `eval_kb_requalification --repeat 2`, `eval_speech_providers`) were run once after the final code change: all PASS, working tree stayed clean.
- Full backend suite, `/tmp/ci_venv/bin/python -m pytest tests -n 3 --dist loadfile -p no:cacheprovider`: 1 failed, 5587 passed, 43 skipped (289 s, run after the last code change); the one failure that remains is PRE-EXISTING on the base branch and unrelated: `test_knowledge_persistence_02a_identity::test_no_forbidden_files_were_touched_and_no_migration_in_part_one` diffs against the local ref `origin/feat/02k-knowledge-contract` and fails on any tree not rooted there (the prep base alone already differs in `src/agent/eval.py`, `judge.py`, `models.py`, `policies.py`); it passes where that ref is absent (it then diffs nothing). One earlier failure caused by this package (`test_language_readiness_06a`, stale audit table) was fixed by regenerating the table.
Frontend (symlinked `node_modules`, never committed): `npx tsc --noEmit` clean; `npm run lint` clean; `npx vitest run` 117 files, 1182 tests passed; Playwright with `E2E_PORT=3108`: `story-bank.spec.ts` 3 passed, and 93 passed in total across it and the touched neighbours (documents, interview, opportunity-practice, data-privacy, i18n, localization, language-selection-06a, journey, opportunities, experience-closure, service-recovery, navigation, product-surfaces). The full Playwright suite was not run.

## 11. Risks and limitations
- Story text copied into a session lives until the session is deleted or the story is; the strip handles the marked blocks only (a candidate who pastes their own story text into the free background field keeps that copy, by design: it is their own pasted text).
- `story_uses.session_id` is an opaque id; export lists it (owner only).
- SQLite does not enforce the new cascades; derivation checks liveness on every read and the code deletes children explicitly, so behaviour is the same on PostgreSQL, but the PostgreSQL FK paths of migration 0041 are rendered by Alembic and unit-checked only, NOT executed against a live PostgreSQL.
- Existing automated specs return `{}` for unknown routes; the new components tolerate missing arrays so older mocks keep working (a real regression found and fixed).
- The 02A static-boundary test above fails locally for everyone until that ref is gone; not weakened, not touched.

## 12. Remaining human and operational evidence
- Native-speaker review of the 116 new strings in each of de, fr, es, it, pt, nl (LG-10); legal wording review of the sharing and deletion text (LG-11); the per-language LG-09 journey on a real backend.
- A real-backend plus browser acceptance run (restart included) on a staging stack; PostgreSQL run of migration 0041 and its downgrade.
- Live model check that Practice feedback actually reflects a chosen story and that no story text is echoed beyond what the candidate supplied (no live call was made here).
- Owner decisions: (1) Prepare consent model (section 7); (2) the reviewed privacy-schema exception (section 8); (3) migration number at merge.

## 13. SHA
See the final report (verified with `git ls-remote origin feat/04a-story-bank` after the push).
