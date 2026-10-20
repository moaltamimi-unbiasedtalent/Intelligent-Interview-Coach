# Dependency Graph (Phase 00)

**Status:** GENERATED from the package definitions. Dependencies mean: the dependent package starts no earlier than the week in which its dependency finishes (merged). Owner decisions and human reviews are shown as external gates.

## Package dependencies

```mermaid
graph LR
  P00A["00A Governance, reviewers and owner de"]
  P00B["00B Scope reconciliation delta (docume"]
  P01A["01A Prompt-injection security and tool"]
  P01B["01B Externalized, versioned prompts (R"]
  P01C["01C Tool registry parity (REVIEW-03)"]
  P02A["02A Permanent Knowledge reliability: p"]
  P02B["02B Embedding integrity and index mani"]
  P02C["02C Real malware scanning for uploads"]
  P02D["02D Market source qualification and li"]
  P02E["02E Retrieval quality and the frozen b"]
  P03A["03A Admin navigation foundation (REQ-O"]
  P03B["03B Admin Plans: Basic/Premium managem"]
  P03C["03C Admin Users: complete user managem"]
  P03D["03D Command Center and AI operations ("]
  P03E["03E Reports and governed custom report"]
  P04A["04A Story Bank completion (REQ-OWN-06)"]
  P04B["04B Workspaces completion (REQ-OWN-07)"]
  P04C["04C Agent streaming and cancellation ("]
  P04D["04D Candidate journey reliability (REQ"]
  P04E["04E Invitation-only registration (REQ-"]
  P04F["04F Browser dictation disclosure and v"]
  P05A["05A Hosted topology and platform harde"]
  P05B["05B Persistence, backup, restore and r"]
  P05C["05C Observability, alerting and provid"]
  P05D["05D Identity, email and rate limiting "]
  P05E["05E Privacy, legal and data-rights rea"]
  P06A["06A Locale audit and language boundari"]
  P06B["06B Per-language journeys, Story Bank "]
  P06C["06C Per-language AI behaviour: prompts"]
  P06D["06D Multilingual retrieval and cross-l"]
  P06E["06E Per-language injection, security a"]
  P06F["06F Native review and legal translatio"]
  P06G["06G Independent human AI evaluation"]
  P07A["07A Deferral inaccessibility and engin"]
  P07B["07B Live grounding and agent-policy va"]
  P07C["07C Residual live verifications"]
  P08A["08A Freeze, release evidence and beta "]
  P01A --> P01C
  P01B --> P01C
  P02A --> P02B
  P02A --> P02C
  P00A --> P02D
  P02B --> P02E
  P03A --> P03B
  P03A --> P03C
  P03A --> P03D
  P03D --> P03E
  P01A --> P04C
  P05A --> P04D
  P05A --> P05B
  P02A --> P05B
  P05A --> P05C
  P05A --> P05D
  P04A --> P06B
  P04B --> P06B
  P06A --> P06B
  P01B --> P06C
  P06A --> P06C
  P02B --> P06D
  P01A --> P06E
  P06A --> P06E
  P06A --> P06F
  P06C --> P06G
  P00A --> P06G
  P05A --> P07A
  P03A --> P07A
  P01B --> P07B
  P01C --> P07B
  P07A --> P08A
  P06G --> P08A
  P05B --> P08A
  P05C --> P08A
  P05D --> P08A
  P05E --> P08A
  P03E --> P08A
  P04C --> P08A
  P04D --> P08A
  P04E --> P08A
  P02C --> P08A
  P02D --> P08A
  P02E --> P08A
  P06B --> P08A
  P06D --> P08A
  P06E --> P08A
  P06F --> P08A
```

## Dependency order (topological)

00A, 00B, 01A, 01B, 01C, 02A, 02B, 02C, 02D, 02E, 03A, 03B, 03C, 03D, 03E, 04A, 04B, 04C, 05A, 04D, 04E, 04F, 05B, 05C, 05D, 05E, 06A, 06B, 06C, 06D, 06E, 06F, 06G, 07A, 07B, 07C, 08A

## Critical path

Lowest-effort chain: 03A -> 03D -> 03E -> 08A = 26 days. Highest-effort chain: 03A -> 03D -> 03E -> 08A = 39 days. These are lower bounds on elapsed effort no matter how many people work in parallel; they exclude calendar-bound human and legal review.

## Shared modules and safe integration order

| Shared module | Packages that edit it | Safe order |
|---|---|---|
| src/agent/policies.py and the tool-execution path (registry.py, nodes.py) | 01A, 01B, 01C, 04C | 01B, then 01A, then 01C; 04C after 01A |
| src/prompts.py, src/prompt_registry.py, src/config_versions.py | 01B, 06C | 01B before 06C |
| src/copilot/security/ and src/copilot/models.py (RetrievalResult) | 01A, 02B, 06D, 06E | 01A first |
| src/knowledge_admin/ and src/copilot/embeddings.py, retrieval/ | 02A, 02B, 02C, 02D, 02E | 02A, then 02B and 02C, then 02D and 02E |
| frontend/components/admin/AdminShell.tsx and frontend/lib/admin/capabilities.ts | 03A, 03B, 03C, 03D, 03E | 03A first; the rest rebase on it |
| frontend/components/layout/nav-items.ts | 03A only | single owner |
| tests/_admin_matrix.py and the admin role fixture | 03A to 03E | regenerate only when a permission or route changes |
| deploy/docker-compose.staging.yml, Dockerfiles, deploy/scripts | 02A (worker, volumes), 02C (clamd), 05A, 05B | 05A owns the file; 02A and 02C supply fragments |
| Alembic migrations (head 0039_speech_governance) | 03E, 04A, 04B, 04E (new tables) | one migration per PR, sequential heads, never two heads |
| src/application/agent_service.py and Mo UI | 04C, 04D | 04C then 04D |
| i18n catalogues (frontend/lib/i18n/messages) | all frontend packages | add keys to all locales in the same PR (existing rule) |

## External gates (not engineering dependencies)

- Owner decisions: OD-SCOPE-01, OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS, OD-INVITE, OD-MALWARE, OD-PLAN-ENFORCE, OD-ADMIN-NAV, OD-BULK-ACTIONS, OD-REPORT-EXPORT, OD-WS-TRANSFER, OD-LANG-02, OD-LANG-03, OD-LANG-04, OD-COVERAGE, OD-EMBED, OD-US-CONTENT.
- Human and legal: named reviewers (00A), native review and legal translation (06F), independent human evaluation (06G), counsel review (05E), licence review (02D).
