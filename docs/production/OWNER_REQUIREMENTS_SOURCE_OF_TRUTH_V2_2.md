# Owner Requirements: Source of Truth (Production Roadmap V2.2)

**Status:** RECOVERED REQUIREMENTS, recorded 2026-10-21. These requirements were established by the Product Owner in a separate conversation and were not previously in the repository. This document records them as supplied; it does not add owner approvals that were not given. Where the supplied text is a suggestion or an example, it is marked as such.

**Provenance classes used throughout this document and in the reconciliation (`provenance` field):**

| Tag | Meaning |
|---|---|
| `[DECISION]` | Explicit owner decision |
| `[CAPABILITY]` | Owner-requested product capability (the owner asked for it; the design is not decided) |
| `[REVIEWER]` | Finding from the actual Turing College capstone review, with its stated requirements |
| `[PROPOSED]` | Proposed engineering implementation or example, not an approval |
| `[AWAITING]` | Decision still awaiting the owner |

Nothing here upgrades a historical status or result. The 394 historical issues, their closure evidence and the failed historical gates (95% coverage gate: 386 of 412 against 392, FAIL; AC-24 PARTIAL; human-qualified coverage 0 of 412) are preserved.

## 1. Confirmed owner decisions

| ID | Decision | Tag |
|---|---|---|
| OWN-D01 | Product: Ask4Mo, Intelligent Interview Coach | `[DECISION]` |
| OWN-D02 | R1.0 target: 30 November 2026. The date is the owner's target; release safety and legal gates are not waived to meet it | `[DECISION]` |
| OWN-D03 | R1.0 launch type: free, invitation-only private production beta. No live customer payments in R1.0 | `[DECISION]` |
| OWN-D04 | R1.0 languages: English, German, Spanish, Italian, Portuguese, French, Dutch; all seven intended for the initial beta, each subject to individual qualification | `[DECISION]` |
| OWN-D05 | Russian excluded from R1.0: keep existing code where safe, remove it from active Candidate language selection | `[DECISION]` |
| OWN-D06 | Mandarin, Hindi, Arabic assigned to R1.3, each with separate implementation and language-specific qualification | `[DECISION]` |
| OWN-D07 | Markets: selected EU countries. Proposed primary mappings Ireland, Germany, Spain, Italy, Portugal, France, Netherlands. These are NOT individually approved country qualifications. Language selection must never silently select or change labour-market geography | `[DECISION]` for the rule; mappings `[PROPOSED]`, per-country approval `[AWAITING]` |
| OWN-D08 | Admin English-only for the initial release, initially operated by the product owner; server-side role-based access control, specialist permissions, approvals and audit trails preserved | `[DECISION]` |
| OWN-D09 | Plans: R1.0 includes the existing Basic and Premium, both usable as free beta access tiers; new plan families are R1.1 | `[DECISION]` |
| OWN-D10 | All dates after R1.0 are indicative planning windows, not fixed promises | `[DECISION]` |

## 2. Actual Turing College review findings

These five findings supersede the five demo-observed findings that had been recorded as RF-01 to RF-05. The demo-observed findings are preserved as separate engineering issues (DEMO-01 to DEMO-05) and are not reviewer findings.

### REVIEW-01 Prompt-injection defence depth `[REVIEWER]`
Finding: defences rely heavily on deterministic heuristics in `src/security.py` and on instructions inside RAG prompts. Requirements:
1. Extend `detect_injection` using a labelled regression corpus derived from `evaluations/jailbreak_test_results.csv`.
2. Include direct, indirect, multilingual, encoded and retrieved-document attacks.
3. Measure attack detection and benign false positives.
4. Fail CI on unacceptable regression against an approved held-out corpus.
5. Add an injection-risk score to each `RetrievalResult`.
6. Quarantine or exclude high-risk chunks before model context construction.
7. Revalidate any model-requested tool action against the authenticated user's actual goal, authorization, tool permissions and allowed arguments.
8. Apply the decisive authorization check before execution or side effects.
9. Retain output-side safeguards in `src/copilot/service.py` `answer()`.
10. Do not depend solely on the LLM obeying an instruction to ignore untrusted content.
11. Test that malicious source content cannot trigger unauthorized tool calls or cross-user information disclosure.
Main areas: `src/security.py`, `src/copilot/security/`, `src/copilot/service.py`, `src/copilot/rag/`, `src/agent/`, `evaluations/jailbreak_test_results.csv`.

### REVIEW-02 Externalized, versioned prompts `[REVIEWER]`
Finding: production prompts are mainly Python literals without independently declared version identities. Requirements:
1. Externalize agent system prompts, interview technique prompts and RAG prompts into versioned assets.
2. Create a validated prompt loader.
3. Assign stable semantic version identities independent of content hashes.
4. Retain SHA hashes for integrity checks.
5. Extend `production_versions()` to include declared version plus hash.
6. Record effective prompt versions on `AgentRunResult` and evaluation results.
7. Make Prompt Lab experiments attributable to exact prompt, model and configuration.
8. Enable safe rollback to an existing approved prompt version without new application code.
9. Test template variables, compatibility, missing versions and rollback.
`[PROPOSED]` example structure (version names are examples; audit actual compatibility before use): `prompts/agent/system.v3.md`, `prompts/interview/zero_shot.v1.md`, `role_persona.v1.md`, `few_shot.v1.md`, `structured_procedure.v1.md`, `rubric_json.v2.md`, `prompts/rag/system.v2.md`.
Main areas: `src/agent/policies.py`, `src/prompts.py`, `src/copilot/rag/prompts.py`, `src/config_versions.py`, `src/prompt_registry.py`, `src/agent/models.py`, Prompt Lab and evaluation contracts.

### REVIEW-03 Tool catalogue parity `[REVIEWER]`
Finding: `src/agent/policies.py` duplicates tool descriptions already defined through the authoritative registry. Requirements:
1. Make the allow-listed tool registry the single authoritative catalogue.
2. Generate model-visible tool descriptions from registered tool metadata.
3. Derive argument contracts from the relevant Pydantic models.
4. Prevent tool names, signatures and descriptions from drifting.
5. Reject duplicate or invalid registrations.
6. Assert parity between registered tools, model bindings and authorization policy.
7. Remove manually duplicated descriptions after migration and regression testing.
8. Do not widen the available tool set simply to make parity checks pass.
Main areas: `src/agent/registry.py`, `src/agent/policies.py`, Pydantic tool schemas, tool-binding and execution layers.

### REVIEW-04 Silent embedding degradation `[REVIEWER]`
Finding: `DEFAULT_EMBEDDING_PROVIDER = "auto"` can resolve to `LocalHashEmbedder` without a real semantic embedding configuration; the local embedder is lexical, not semantic. Requirements:
1. Surface the actual embedding provider, model and degradation state in readiness.
2. Prevent silent hash-embedding fallback in production.
3. Fail closed when required semantic embedding credentials are missing.
4. Preserve a clearly labelled offline development mode where appropriate.
5. Record embedding provider, model, version, vector dimensions and other compatibility metadata in every index manifest.
6. Detect index/query embedding mismatch.
7. Never silently query an index with an incompatible embedder.
8. Rebuild qualified indexes from approved source material when necessary.
9. Evaluate BM25, vector search and RRF separately and in combination.
10. Include multilingual retrieval and cross-language evidence attribution.
Main areas: `src/copilot/constants.py`, `src/copilot/embeddings.py`, `src/copilot/retrieval/hybrid.py`, knowledge build and readiness tools.

### REVIEW-05 Agent streaming and feedback `[REVIEWER]`
Finding: LangGraph agent execution is synchronous from the Candidate perspective; no qualified `astream_events` incremental delivery. Requirements:
1. Add an authenticated SSE endpoint alongside `POST /api/v1/agent/run`.
2. Use LangGraph `astream_events` with `version="v2"` where compatible.
3. Forward only safe allow-listed projections of existing `AgentEvent` types.
4. Never stream chain-of-thought, system prompts, private tool arguments, secret values or raw internal events.
5. Display useful Candidate progress states.
6. Support cancellation and timeouts.
7. Preserve durable run identity, checkpointing and authorization.
8. Ensure reconnection cannot expose another user's events.
9. Reconcile provider usage and costs even when a run is cancelled.
10. Retain the synchronous API as a tested compatibility fallback.
Main areas: `src/agent/nodes.py`, `src/agent/events.py`, `src/application/agent_service.py`, Agent API routes, Candidate Mo interface.

## 3. Admin Platform 2.0 `[CAPABILITY]` (a major R1.0 delivery programme)

The Admin must allow routine management without code changes. This is not permission to create arbitrary executable functionality through Admin configuration.

**ADMIN-01 Navigation redesign.** Replace the flat destination list with a grouped, collapsible sidebar. `[PROPOSED]` groups (the owner wrote "suggested"): Command Center; Customers and Workspaces; Products and Commercial; AI and Knowledge; Insights and Operations; Governance and Settings. Required: expand/collapse groups, active destination highlighting, breadcrumbs, responsive layout, keyboard accessibility, permission-aware navigation, search or quick navigation where useful, route compatibility when safe. Review and Diagnostics: platform-wide surfaces accessible only through the Admin panel; remove their entry from the global Candidate navigation; move or redirect internal diagnostic surfaces under `/admin`; keep Candidate access to their own authorized run details through a separate owner-scoped experience; frontend hiding is not authorization, backend permissions stay mandatory.

**ADMIN-02 Basic/Premium management** (R1.0 only the existing Basic and Premium): edit draft plan versions; select from implemented registered features; enable or disable features per plan; configure usage limits and allowances; clone or version plans; compare plan configurations; preview effects on candidate access; assign plans to users; apply authorized Workspace entitlements; activate and retire versions; preserve existing subscriber rights until an explicit migration decision; immutable audit trail; safe rollback; entitlements enforced in backend services. A Premium plan existing is not a reason to enable billing. New plan families, broad commercial migration tooling and paid activation are R1.1.

**ADMIN-03 User management:** search, filter, sort, paginate; safe account metadata; activation and suspension; account closure and deletion; role changes through approvals; revoke active sessions; resend permitted account communications; assign Basic/Premium; inspect Workspace memberships; permitted membership actions; support status and audit history; carefully restricted bulk actions; prevent owner self-lockout and privilege escalation. The owner-operated Platform Admin is not an unrestricted reader of private CVs, stories, interviews or conversations.

**ADMIN-04 Command Center:** operational dashboards, for example active users and registration trends, candidate activation, interview start and completion rates, AI failure rate and latency, AI model usage and costs, retrieval and source health, worker and indexing failures, support ticket trends, security and incident indicators, deployment and provider readiness. Charts use real sourced data, chart types chosen by meaning, with period, numerator, denominator, coverage and missing-data state; no invented figures or misleading zeros.

**ADMIN-05 Reporting:** enhance the existing aggregate foundation with prebuilt reports (acquisition and onboarding; candidate engagement; interview practice and completion; AI feedback quality; Story Bank adoption and reuse; Workspace invitations and sharing; model performance and economics; agent/tool execution outcomes; knowledge/RAG quality; support operations; security and privacy; commercial performance once real billing is qualified) and a governed custom report builder (approved metrics, approved dimensions, date-range filters, comparisons, appropriate chart types, saved report configurations, export in supported formats). No arbitrary SQL, no private candidate-data access; permission checks and small-cohort suppression enforced. Scheduled distribution and advanced automation are R1.2.

**ADMIN-06 AI operations:** administration of registered models, effective configuration, approved prompt versions, model readiness and cost, safe feature flags, provider readiness, agent execution status, evaluation results, operational incidents, audit and diagnostic information. High-impact changes validated, permissioned and audited. No unsafe direct modification of system instructions or tool permissions.

## 4. Permanent Knowledge Source fix `[CAPABILITY]`, R1.0

The owner has repeatedly encountered missing or empty Knowledge Sources. The fix must address persistence and environment architecture, not only the visual empty state.
1. Persistent SQL source registry. 2. Durable private storage for uploaded source files. 3. Persistent curated and governed knowledge indexes. 4. Separate, clearly labelled views of curated and governed sources. 5. Environment, database and index identity in safe Admin diagnostics. 6. API and indexing workers use compatible authoritative configuration. 7. Persisted index manifests including embedding model identity and checksums. 8. Register, scan, parse, review, approve, index, activate, replace, retire, reindex. 9. Licensing and source-qualification safeguards preserved. 10. Genuine fail-closed malware scanning for real user uploads. 11. Monitoring of indexing and source health. 12. Alerts for lost collections, missing sources, incompatible embeddings, failed jobs. 13. Authorized backup, restore, retry, rebuild and rollback. 14. Restart persistence tested. 15. Redeployment persistence tested. 16. Restoration in a separate environment tested. 17. Retrieval, citation provenance and actual candidate access tested. 18. Never silently connect a production UI to an empty local demonstration database. 19. Never invent source counts or claim temporary demonstration fixtures are production-approved evidence.
Definition of done: sources survive restarts, deployments and restore drills, remain compatible with their indexes, and produce attributable candidate-facing retrieval results.

## 5. Story Bank completion `[CAPABILITY]`, R1.0

Create stories manually; draft from approved Candidate evidence; full STAR editing (Situation, Task, Action, Result); preserve evidence provenance; distinguish user-created, source-backed, user-corrected and model-suggested content; search and filter; tag competencies; connect stories to Opportunities; suggest relevant stories for interviews; Candidate approval before use; reuse during Practice; reflect story evidence in feedback; never invent achievements or numbers; persist across sessions; deletion and privacy controls; strict Candidate ownership. Acceptance journey: create, edit, link to Opportunity, reuse in Practice, receive feedback, retrieve after restart.

## 6. Workspace completion `[CAPABILITY]`, R1.0

Create and manage Workspaces; invite members by email; accept and decline invitations; show pending invitations; cancel or revoke invitations; display membership and roles; remove members where authorized; transfer ownership safely; share supported resources explicitly; initial sharing defaults to VIEW-only; display what is shared and with whom; immediate revocation; no access to unshared private content; activity and audit data; qualified in all seven Candidate languages. Acceptance journey: User A creates a Workspace and invites User B; B accepts; A explicitly shares one resource; B accesses only that resource; A revokes; B immediately loses access. Authorization is tested at the API boundary, not only in the frontend.

## 7. Candidate product requirements `[CAPABILITY]`

R1.0 preserves and qualifies: registration and onboarding; Opportunities and role context; Mo interview preparation; real agent and tool orchestration; source-backed career evidence; Interview Practice and Deep Dive; structured feedback; Story Bank; Workspaces and explicit sharing; History and Progress; data and privacy controls; accessible responsive navigation; useful error recovery; language-specific quality and safety. The previously observed Start Interview 503 / "unavailable" issue is a regression risk requiring a real Candidate journey test, not only a backend unit test. Offline simulation must never be confused with live model qualification.

## 8. Agreed release train

All dates after R1.0 are indicative planning windows, not fixed promises.

| Release | Window | Content |
|---|---|---|
| R1.0 | 30 November 2026 | Free private production beta; seven languages each subject to individual qualification; selected qualified EU markets; Admin English-only with owner-operated Platform Admin and RBAC; complete core Candidate functionality; Admin 2.0 operational essentials; reliable Knowledge Sources; Story Bank and Workspaces; professional core reporting; the five reviewer corrections; secure hosting, privacy and operations; no live customer billing |
| R1.1 | indicative December 2026 | Paid beta and plan expansion: Stripe and subscription lifecycle only after provider and legal qualification; live payments, pricing, tax, cancellation, refunds, reconciliation; new plan families and expanded commercial entitlement management |
| R1.2 | indicative December 2026 to January 2027 | Advanced Admin and automation: scheduled reporting, advanced custom analytics, operational automation, enhanced bulk administration, expanded alerts and management workflows |
| R1.3 | indicative January to February 2027 | New languages Mandarin, Hindi, Arabic: new locale, prompt, safety, retrieval, accessibility, legal and native review; RTL for Arabic |
| R1.4 | indicative February 2027 | Voice interview experience: qualified speech-to-text, text-to-speech and live voice practice; provider licensing and consent; latency and accessibility; native speech quality evaluation |
| R1.5 | indicative February to March 2027 | Global career intelligence: additional country coverage, qualified occupational sources, global evidence and provenance, multilingual geographic retrieval |
| R1.6 | indicative March 2027 | Compensation Intelligence V2: qualified salary datasets, geographic comparisons, source freshness, methodology and confidence controls, legal and human evidence approval |
| R1.7 | after R1.6, date not committed | Teams and enterprise: enterprise Workspaces, organization subscriptions, advanced collaboration, SSO and governance, qualified external integrations |
| R2.0 | evidence-led, subsequent | Expanded intelligent career platform: personalized career guidance, intelligent agentic workflows, deeper career-development capabilities |

Russian remains excluded from R1.0. Its eventual activation is a separate future decision, not an automatic R2.0 commitment.

## 9. Multilingual qualification `[DECISION]`

Each of the seven languages must independently pass the fourteen language gates LG-01 to LG-14 and be reported per language. Validate navigation and UI strings, registration and onboarding, Mo responses and safety, interview questions and feedback, Story Bank and Workspaces, RAG retrieval and citation support, mixed-language injection and privacy, legal documents, native-speaker review, and language/geography separation. A failed mandatory locale gate prevents activation for real users in that locale. No claim that all seven are qualified before the evidence exists.

## 10. Reconciliation corrections required `[DECISION]`

Replace the reviewer findings with the five actual ones; keep the demo findings separately; convert REQ-OWN-01 to REQ-OWN-08 into testable R1.0 requirements from sections 3 to 6, retaining only genuinely awaiting choices; restore R1.0 to R2.0; reclassify academic-only submission tasks separately from production dependencies; preserve failed or partial historical results and the original 95% coverage gate; define a separate frozen R1.0 beta-scope coverage measure; exclude unsupported or unlicensed market evidence from enabled features; do not require disabled Compensation V2 or speech to ship an unrelated safe beta feature; verify that every deferral leaves the feature inaccessible through UI and backend; give every item an ID, origin, description, work package, target release, priority, dependencies, acceptance criteria, test evidence, status and owner role; keep zero unmapped; recalculate counts and explain the changes.

## 11. November production gates `[DECISION]` (measurable definitions are in `PRODUCTION_ACCEPTANCE_MATRIX.md`)

PG-01 secure hosted deployment; PG-02 identity and account lifecycle; PG-03 injection defence and tool safety; PG-04 privacy, legal and data rights; PG-05 persistent Knowledge Sources and embedding/index integrity; PG-06 Candidate end-to-end reliability; PG-07 independent human AI evaluation; PG-08 Admin 2.0 functionality; PG-09 observability, resilience, backup, restore and rollback; PG-10 deferred and paid features disabled; PG-11 complete issue reconciliation; PG-12 prompt versioning, provenance and registry parity; PG-13 Story Bank and Workspaces; PG-14 reports and safe analytics; PG-15 free beta operational acceptance; plus LG-01 to LG-14 per language. A mandatory safety, privacy, licensing or operational gate cannot be bypassed by recording an "accepted limitation". The owner may remove a feature from scope or delay activation. No PASS evidence is fabricated.

## 12. Not permitted by this planning pass

No production code, no database modification, no paid provider calls, no live Stripe activation, no production deployment, no feature activation, no rewriting of historical results.
