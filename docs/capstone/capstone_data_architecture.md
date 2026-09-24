# Ask4Mo Capstone — Data Architecture (proposed)

Proposed model only — **no migrations created in P0/E0**. Preserve Sprint 4 tables; extend, don't
duplicate. Every candidate resource carries `owner_user_id` and is private by default.

## Preserve / extend / add
| Existing table | Disposition | Change |
|---|---|---|
| users | EXTEND | add `platform_role`, `status`, verified-email fields; keep subject mapping during transition |
| interviews / questions / answers / reports | PRESERVE | scope to real accounts; add export/delete lifecycle |
| interview_sessions | PRESERVE | active-session discovery query (A2) |
| preparation_memories | PRESERVE | unchanged trust model |
| user_feedback | PRESERVE | unchanged |

## New entities (target)
| Entity | Owner | Sensitive | Deletion | Retention | Notes |
|---|---|---|---|---|---|
| account_identity | user | email, provider sub | cascade w/ account | account life | local + social; verified flag |
| user_profile | user | profile text | cascade | account life | onboarding data |
| platform_role | (on user) | — | — | — | USER / PLATFORM_ADMIN |
| product_entitlement | user | — | — | — | BASIC / PREMIUM; future billing writes here |
| usage_allowance | user | — | reset windows | rolling | per-op counters for entitlement/limits |
| workspace | workspace owner | name | explicit | until deleted | team scope |
| workspace_membership | workspace | role | on removal | — | OWNER / MEMBER |
| share_grant | resource owner | — | on revoke | until revoked | selected-resource → workspace/user |
| candidate_document | user | file, extracted text | hard delete + derived cleanup | user-set / policy | object storage ref; PDF/DOCX/TXT + OCR |
| document_extraction | user | extracted text, page provenance | with document | with document | native text first, OCR when needed |
| candidate_evidence / story | user | STAR text, source refs | cascade | account life | distinct from model inference & market evidence |
| recording | user | audio | explicit delete | short/default | object storage; opt-in |
| transcript | user | transcript text | with recording/answer | policy | original-language preserved |
| consent_record | user | scope, timestamp | retained for audit | policy | consent where required |
| privacy_request | user | type, status | audit-retained | policy | export/delete lifecycle |
| audit_event | platform | actor, action, target, safe metadata | retained | policy | admin/privacy/security actions; no secrets/CoT |
| feature_flag | platform | — | — | — | operational enablement |

## Provenance classes (must stay distinguishable)
candidate-document evidence · candidate-authored story · model inference (draft, labelled) ·
governed market/knowledge evidence · external-research result. Each carries its class + source ref;
model suggestions are drafts, never presented as verified candidate achievements.

## Deletion & retention semantics
Account deletion cascades personal resources and derived data (extractions, transcripts, embeddings,
caches, checkpoints for owned runs). Share revocation removes access without deleting the owner's copy.
Deleted data must not resurrect via caches, vector stores or backups beyond documented backup windows.
Bulk cleanup (C9) is dry-run first, bounded, idempotent, excludes active/held/pending items.

## Authorization boundary
Every read/write resolves `owner_user_id` (or a valid `share_grant`), the actor's `platform_role`,
their `workspace_membership` where relevant, and the resource's entitlement gate. Personal candidate
records remain private even from workspace admins and platform admins unless an explicit, audited,
least-privilege justification applies.
