# 04A Evidence: Story Bank completion (REQ-OWN-06) and story flows in the seven languages (REQ-LANG-05)

Branch `feat/04a-story-bank`, based on the pushed prep branch `origin/chore/migration-head-agnostic` (ec14963), which is NOT yet merged to `main`; this branch therefore carries the prep commits and the PR should target `main` after the prep branch merges (or be stacked on it). Wave 2 start: 2026-10-22 01:57 CEST.

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
| Frontend | A read-only `StoryBank` list inside `DocumentsClient` (title, status badge, evidence badge, result, delete without confirmation) plus "draft a story" from selected claims. 13 i18n keys (`documents.st*`, `ev*`, `story*`). |
| Tests | `test_documents_api` (draft, revocation, edit marks corrected, cross-user GET), sharing and privacy tests above, `documents.spec.ts` (one mocked draft journey). |

## 2. Gap list (REQ-OWN-06 S1 to S7), recorded BEFORE coding
| # | Gap | Requirement |
|---|---|---|
| G1 | No manual create or edit UI; no STAR editor; no quality prompts | S1 |
| G2 | No archive / restore; delete has no confirmation | S6 |
| G3 | Evidence labels are weak: `evidence_state` is stored, so a `user_corrected` story keeps "verified" after its source is deleted or a claim is rejected; a rejected claim still counts as live; user-created stories cannot attach evidence; no answer evidence; nothing distinguishes self-confirmed from evidenced | S2, S5 |
| G4 | No search, filter or tag UI or API | S3 |
| G5 | No Opportunity link | S3, S7 |
| G6 | No suggestions and no approval step; Practice reuse is a blanket boolean with no consent record and no attribution | S4 |
| G7 | Deleting a story leaves derived copies: Preparation Pack items citing it, and the story text copied into in-progress/completed session configuration; no usage record to find them | S6 |
| G8 | Shared projection returns the full repository dict (claim ids included) and ignores archive | S6 |
| G9 | Agent/Pack read paths use `list()` that would now include archived stories | S6 |
| G10 | Opportunity delete does not unlink stories | S3 |
| G11 | Story flows are not localised beyond 13 keys; no per-locale story journey test | REQ-LANG-05 |
| G12 | Cross-user tests exist only for GET one; none for PATCH, DELETE, evidence, archive, suggest, Practice story selection, share | S6 |
| G13 | No Playwright journey create, verify, practice, share, revoke, delete | S7 |
