"""Phase 00 execution programme: implementation packages for Production Roadmap V2.2 (R1.0, 30 November 2026).

    python scripts/production/execution_packages.py generate   write the generated sections of docs/production/execution/*.md
    python scripts/production/execution_packages.py check      fail unless every R1.0 FIX/VERIFY item belongs to exactly one package and the plan is internally consistent

The package definitions below are the ONLY source of truth for package scope, dependencies, effort and schedule; the documents are generated from them and the item
dispositions come from docs/production/PRODUCTION_ISSUE_RECONCILIATION.json (read-only). Nothing here implements a feature, calls a provider or changes a historical record.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RECON = ROOT / "docs/production/PRODUCTION_ISSUE_RECONCILIATION.json"
OUT = ROOT / "docs/production/execution"

TRACKS = {
    "A": "AI security, prompts and tool registry",
    "B": "Knowledge Sources, embeddings and RAG",
    "C": "Admin Platform 2.0",
    "D": "Candidate journeys, Story Bank, Workspaces and streaming",
    "E": "Hosted infrastructure and operations",
    "F": "Seven-language and human qualification",
}
PHASES = {
    0: "Programme readiness and governance (this phase)",
    1: "Track A foundations: injection defence, versioned prompts, tool registry",
    2: "Track B: Knowledge persistence, embedding integrity, scanning, source qualification",
    3: "Track C: Admin 2.0 navigation, plans, users, Command Center, reports",
    4: "Track D: Story Bank, Workspaces, streaming, journey reliability, invitations",
    5: "Track E: hosted topology, restore drills, observability, identity, privacy/legal readiness",
    6: "Track F: seven-language programme and human qualification",
    7: "Integration and hardening: deferral inaccessibility, live validation",
    8: "Freeze, release evidence and beta readiness",
}
WEEKS = {0: "W0 21-25 Oct", 1: "W1 26 Oct-1 Nov", 2: "W2 2-8 Nov", 3: "W3 9-15 Nov", 4: "W4 16-22 Nov", 5: "W5 23-27 Nov"}
WORKING_DAYS_PER_WEEK = 5
UTILISATION = 0.7   # assumption: review, CI waits, context switching and rework leave 70% of a stream's days productive


def P(id_, name, track, phase, start, end, effort, items, depends=(), decisions=(), scope="", components="", backend="", frontend="", security="", acceptance="", tests="", pr="", dod="", human="", note=""):
    return dict(id=id_, name=name, track=track, phase=phase, start=start, end=end, effort=effort, items=list(items), depends=list(depends), decisions=list(decisions), scope=scope, components=components,
                backend=backend, frontend=frontend, security=security, acceptance=acceptance, tests=tests, pr=pr, dod=dod, human=human, note=note)


PACKAGES = [
    P("00A", "Governance, reviewers and owner decisions", "F", 0, 0, 1, (2, 4), ["BL-1", "BL-2", "BL-3", "BL-18", "REQ-SCOPE-01"], decisions=["OD-SCOPE-01", "OD-LANG-03", "OD-LANG-04"],
      scope="Owner names reviewers A, B, C, the seven native reviewers and the legal qualifiers; two-person role changes recorded; the owner decides the open decisions that block Phase 01 to 06.",
      components="docs/production/OWNER_DECISION_REGISTER.md; Admin role-change approval flow (existing); audit log", backend="none (uses existing role-change approvals for appointments)", frontend="none",
      security="Appointments are privileged role changes: two-person approval with step-up, audited", acceptance="Appointment table filled; three reviewer accounts verified; audit evidence of the role changes; decision register has an owner answer for every Phase 01 to 03 blocker",
      tests="audit-log evidence; role-change approval tests already exist", pr="Documentation PR recording decisions and appointments (no code)", dod="Named people recorded; decisions recorded; evidence linked", human="Owner and named reviewers"),
    P("00B", "Scope reconciliation delta (documentation only)", "B", 0, 1, 1, (1, 2), ["BL-5", "BL-6", "BL-6.1", "BL-6.2", "BL-6.3", "BL-6.4", "BL-6.5", "BL-6.6", "BL-7", "BL-9", "BL-12", "W12.4E-12"], decisions=["OD-US-CONTENT"],
      scope="Phase 00 found items classified R1.0 whose feature stays disabled or whose evidence is outside the selected EU markets (US occupational measurement and alias reviews, Compensation V2 authorisation, server-side recording client). Propose their reclassification (R1.5, R1.6 or R1.4) for owner confirmation; apply only after the owner confirms.",
      components="docs/production/PRODUCTION_ISSUE_RECONCILIATION.json and scripts/production/reconcile_issues.py (regenerated, historical register untouched)", backend="none", frontend="none",
      security="Reclassification must keep REQ-DEFER-01 satisfied: the affected features stay inaccessible", acceptance="Owner confirms or rejects each proposed move; the reconciliation is regenerated with explained deltas and zero unmapped",
      tests="scripts/production/reconcile_issues.py check; tests/test_production_reconciliation.py", pr="Docs-only PR: reconciliation delta", dod="Reconciliation regenerated, counts explained, owner decision recorded", human="Owner"),
    # ---------------- Phase 01 Track A
    P("01A", "Prompt-injection security and tool authorization (REVIEW-01)", "A", 1, 1, 2, (8, 12), ["REVIEW-01", "D-LEX", "D-AGENT-TXT", "D-NONNUM", "D-SENT", "D-EST-FLAG", "D-COUNTRY"], decisions=["OD-GATE-THRESHOLDS"],
      scope="Labelled regression corpus from evaluations/jailbreak_test_results.csv (direct, indirect, multilingual, encoded, retrieved-document); detection and false-positive measurement; CI gate on a frozen held-out set; injection-risk score on RetrievalResult; quarantine of high-risk chunks before context; server-side revalidation of model-requested tool calls before side effects; output guard retained.",
      components="src/security.py (detect_injection); src/copilot/security/ (injection, rag_guard, output_guard, grounding_policy); src/copilot/models.py (RetrievalResult); src/copilot/service.py answer(); src/agent/nodes.py and registry.py validate_and_run; evaluations/",
      backend="Add risk score field to RetrievalResult; extend rag_guard.screen_results to quarantine by score; add an authorization layer in the tool-execution path (goal, user permission, tool permission, allowed arguments) before handler execution; corpus loader and evaluator script", frontend="none (no user-visible change; optional safe 'content withheld' note reuses existing insufficient-evidence copy)",
      security="Core safety work: no cross-user disclosure, no unauthorized tool side effects, no sole reliance on the prompt; evaluator uses only public/synthetic data", acceptance="REVIEW-01 R1 to R6; detection and false-positive rates reported per language and above owner-approved thresholds on the frozen held-out set; negative tests for tool calls and cross-user disclosure pass",
      tests="held-out corpus evaluator in CI (new scripts/eval_injection_corpus.py); tool-authorization negative tests; cross-user retrieval tests; output-guard regression; existing eval_agent and grounding suites unchanged", pr="Two PRs: (1) corpus, evaluator, risk score and quarantine; (2) tool-call authorization layer", dod="CI gate green on held-out set; thresholds recorded; no regression in existing security suites; documentation of residual risk"),
    P("01B", "Externalized, versioned prompts (REVIEW-02)", "A", 1, 1, 2, (5, 8), ["REVIEW-02"], scope="Move agent, interview technique and RAG prompts to versioned assets with a validated loader, semantic versions plus SHA, run attribution and rollback without code.",
      components="src/agent/policies.py (SYSTEM_PROMPT); src/prompts.py (733 lines); src/prompt_registry.py; src/copilot/rag/prompts.py; src/config_versions.py (production_versions); src/agent/models.py (AgentRunResult); Prompt Lab (src/application/prompt_lab/)",
      backend="Prompt asset directory and loader with variable validation; declared versions; production_versions() reports version plus hash; AgentRunResult and evaluation results record effective prompt versions; rollback selection via the existing governed-configuration mechanism", frontend="none (Admin AI operations later surfaces versions: 03D)",
      security="Prompts remain code-reviewed assets; no Admin free-text editing of system instructions; integrity hash verified at load", acceptance="REVIEW-02 R1 to R7", tests="loader unit tests; compatibility, missing-version and rollback tests; production_versions parity test; Prompt Lab attribution test; byte-identical prompt output regression for current defaults",
      pr="One PR per prompt family if large: agent; interview; RAG", dod="Defaults produce byte-identical prompts; versions visible in run results; rollback tested"),
    P("01C", "Tool registry parity (REVIEW-03)", "A", 1, 3, 3, (3, 5), ["REVIEW-03"], depends=["01A", "01B"], scope="Registry as the single catalogue: generated model-visible descriptions, Pydantic-derived argument contracts, duplicate rejection, parity tests, no widened tool set.",
      components="src/agent/registry.py; src/agent/policies.py; src/agent/tools.py; src/agent/specialist_tools.py; src/agent/nodes.py (bindings)", backend="Descriptions generated from ToolSpec metadata; parity test across registry, bindings and authorization policy; remove duplicated text after regression", frontend="none",
      security="The tool set must be unchanged (asserted); authorization policy derived from the same catalogue", acceptance="REVIEW-03 R1 to R6", tests="registry parity, duplicate-registration, binding/policy parity, unchanged-tool-set assertion; existing eval_agent and tool-selection cases unchanged", pr="One PR", dod="No manual duplicate descriptions remain; parity test in CI",
      note="Sequenced after 01A and 01B because all three edit src/agent/policies.py or the tool-execution path."),
    # ---------------- Phase 02 Track B
    P("02A", "Permanent Knowledge reliability: persistence, environment identity, restore (REQ-OWN-05)", "B", 2, 1, 2, (10, 15), ["REQ-OWN-05", "DEMO-01", "H-WORKER", "H-KB-INGEST"], decisions=["OD-HOSTED"],
      scope="Persistence and environment architecture for governed and curated knowledge: durable registry, private file storage, persistent indexes, safe environment/database/index identity diagnostics, one authoritative configuration shared by API and worker, lifecycle including replace, retire and reindex, backup and restore, alerts, restart/redeploy/restore tests.",
      components="src/knowledge_admin/ (service, runtime, readiness, wiring, jobs); src/jobs/worker.py; src/copilot/constants.py data_path (anchored root); src/documents/storage.py; src/api/routes/admin_knowledge.py; frontend/components/admin/KnowledgeView.tsx and KnowledgeReadiness.tsx; deploy/docker-compose.staging.yml",
      backend="Environment identity endpoint (safe: database kind, data root, index collection ids, manifest checksums); startup guard that refuses a UI/API pair whose worker or store identity differs; reindex/replace/retire lifecycle completion; backup and restore commands for registry, files and indexes; health alerts", frontend="Admin Knowledge: environment identity panel and clearer curated versus governed views (builds on PR #210)",
      security="Licence and provenance safeguards preserved; no demo fixture labelled production evidence; fail closed on identity mismatch; Admin sees metadata only", acceptance="REQ-OWN-05 K1 to K9 except scanner (02C) and embedding manifest identity (02B)",
      tests="restart persistence; redeployment persistence; restore into a separate environment; identity mismatch refusal; retrieval and citation provenance after restore; Admin Playwright for identity and views", pr="Two PRs: (1) identity, configuration unification, lifecycle; (2) backup/restore and alerts", dod="Drills documented and repeatable; no silent empty-source state; staging topology includes worker and knowledge volumes (see 05A)"),
    P("02B", "Embedding integrity and index manifests (REVIEW-04)", "B", 2, 3, 3, (6, 10), ["REVIEW-04", "B-EMBED-CRED"], depends=["02A"], decisions=["OD-BUDGET", "OD-EMBED"],
      scope="Readiness shows actual embedder and degradation; production refuses hash-embedding fallback and fails closed on missing semantic credentials; manifests record provider, model, version, dimensions and checksums; query/index mismatch detected and refused; rebuild from approved sources; BM25, vector and RRF evaluated separately and combined, multilingual.",
      components="src/copilot/constants.py; src/copilot/config.py; src/copilot/embeddings.py (build_embedder, LocalHashEmbedder); src/copilot/retrieval/hybrid.py, vector.py, fusion.py; knowledge build and readiness (src/knowledge_admin/readiness.py)",
      backend="Provider resolution rewritten with an explicit production mode; manifest schema extension; mismatch guard at query time; rebuild command; retrieval-mode evaluator", frontend="Readiness panel shows embedder, model and degradation state",
      security="Paid embedding builds are budgeted (OD-BUDGET) and go through the AI spend guard; no secrets in manifests", acceptance="REVIEW-04 R1 to R7", tests="readiness tests; production fail-closed tests; manifest and mismatch tests; offline-dev labelling test; retrieval-mode evaluation with sample sizes", pr="Two PRs: (1) resolution, guard, manifest; (2) rebuild and evaluation", dod="No path serves candidates from an unlabelled hash index in production; evaluation report with limitations"),
    P("02C", "Real malware scanning for uploads", "B", 2, 3, 3, (5, 8), ["B-SCANNER", "J-CLAMAV", "EX-12.13"], depends=["02A"], decisions=["OD-MALWARE"],
      scope="Replace the ClamAV stub with a real clamd client and deploy the daemon; fail closed for real uploads; the fake scanner never runs outside development; alert when signatures are stale or the scanner is down.",
      components="src/documents/file_security.py (ClamAvScanner stub, enforce_scan); src/integrations.py (malware_scanner); governed knowledge upload path; Candidate document upload", backend="clamd INSTREAM client, health probe, signature-age check, configuration guard (hosted environments refuse FILE_SCAN_PROVIDER=fake)", frontend="Admin integration status shows scanner state (existing panel)",
      security="Uploads are never reported clean unless a real scan ran and passed; fail closed on unavailability", acceptance="REQ-OWN-05 K6; EX-12 #13 verified in the hosted environment", tests="EICAR test through a real clamd container in a dedicated CI job; fail-closed tests; hosted verification", pr="One PR plus infrastructure change in 05A", dod="Real scan evidence in staging; fake scanner refused outside dev"),
    P("02D", "Market source qualification and licensing (selected EU markets)", "B", 2, 2, 4, (6, 10), ["A-K1", "BL-4", "BL-8", "K-HUMANSRC", "K-LIC-ESCO", "K-LIC-ISCO", "K-LIC-OGL", "K-LIC-DE", "BL-14", "BL-15", "D-08", "REQ-COV-02"], depends=["00A"], decisions=["OD-LANG-02", "OD-US-CONTENT"],
      scope="For each approved market: licence, authority and coverage qualification of the sources actually enabled; exclusion of unsupported or unlicensed evidence from enabled features; decision on US-sourced content (O*NET, BLS) in an EU beta; alias curation ownership.",
      components="docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md; src/knowledge_admin (approval); src/copilot/knowledge/governance.py; data/knowledge manifests; retrieval approval filtering", backend="Approval filter so only qualified, licensed sources reach candidate retrieval for the enabled markets; per-market enable switch tied to an approved register entry", frontend="Admin shows which markets are enabled and why",
      security="Licence integrity; no unlicensed content served; provenance preserved", acceptance="Signed approval entry per enabled market; a candidate cannot retrieve an unqualified source (test); US content decision recorded", tests="retrieval-approval tests; market-enable tests; licence register consistency check", pr="Engineering PR for the approval filter; documentation PRs for the register", dod="Every enabled market has a recorded qualification; unqualified markets are not offered", human="Legal/licensing reviewer and owner (long lead)"),
    P("02E", "Retrieval quality and the frozen beta-scope coverage measure", "B", 2, 4, 4, (6, 9), ["BL-11", "M-DOC-COVERAGE", "L-REL-1", "L-ROUTE-1", "B-SEMCAL", "J-SEMANTIC"], depends=["02B"], decisions=["OD-COVERAGE", "OD-BUDGET"],
      scope="Calibrated relevance floor, language-aware routing, semantic calibration, and a separate frozen R1.0 beta-scope coverage measure reported beside the preserved historical gate (386 of 412, FAIL).",
      components="src/copilot/retrieval/ (adaptive, reranker, fusion); src/copilot/router; scripts/check_product_coverage_baseline.py; evaluations/product_coverage/; docs/capstone coverage records (read-only)", backend="Relevance-floor calibration; routing keyword tables per language; beta-scope coverage evaluator over a frozen case set", frontend="none",
      security="Historical gate results never rewritten; the new measure is never labelled as the original gate", acceptance="Beta-scope measure approved and reported; relevance floor calibrated with evidence; routing verified per language", tests="coverage evaluators on the frozen set; routing tests per language; consistency check that both measures are reported", pr="One PR plus documentation", dod="Both measures reported side by side"),
    # ---------------- Phase 03 Track C
    P("03A", "Admin navigation foundation (REQ-OWN-08)", "C", 3, 1, 1, (5, 7), ["REQ-OWN-08"], decisions=["OD-ADMIN-NAV"],
      scope="Grouped, collapsible Admin sidebar, active highlighting, breadcrumbs, responsive and keyboard-accessible, permission-aware; Review and Diagnostics moved under /admin with redirects; removed from the global Candidate More menu; backend permissions unchanged.",
      components="frontend/components/admin/AdminShell.tsx; frontend/lib/admin/capabilities.ts (ADMIN_DESTINATIONS, 20 destinations); frontend/components/layout/nav-items.ts (INTERNAL_NAV); frontend/app/review/*; frontend/app/admin/*; tests/_admin_matrix.py; frontend/tests/fixtures/admin-role-permissions.json",
      backend="No permission change; if a diagnostics API is moved, keep the old route as a redirect and keep its require_permission guard", frontend="Group definitions, collapsible sidebar, breadcrumbs, quick navigation, /admin/review route group with redirects from /review, Candidate nav cleanup; the owner-scoped run details at /review/agent stay for Candidates",
      security="Hiding is not authorization: backend 403 tests for diagnostic routes remain; no Candidate access to platform-wide diagnostics", acceptance="REQ-OWN-08 N1 to N5", tests="admin-shell vitest; navigation Playwright (expand/collapse, keyboard, breadcrumbs, responsive); redirect tests; backend 403 tests; accessibility checks; existing admin matrix unchanged", pr="One PR (frontend plus redirects)", dod="All existing Admin routes reachable; permission-aware; no regression in the admin Playwright suites"),
    P("03B", "Admin Plans: Basic/Premium management (REQ-OWN-02)", "C", 3, 2, 3, (6, 9), ["REQ-OWN-02"], depends=["03A"], decisions=["OD-PLAN-ENFORCE"],
      scope="Draft plan editing from registered features, per-plan feature toggles and limits, clone/version, comparison, candidate-access preview, user and Workspace assignment, activate/retire, rollback, backend enforcement; no billing.",
      components="src/plans_repository.py; src/entitlements.py (REGISTRY); src/api/routes/admin_plans.py; frontend PlansView/PlanDetailView/PlanControl; src/application/plan_state.py", backend="Feature-and-limit editing on draft plan versions; comparison and preview endpoints; Workspace entitlement assignment; rollback; audit", frontend="Plan editor, comparison and preview views",
      security="Entitlements enforced server-side; privileged changes audited; billing gates stay False", acceptance="REQ-OWN-02 P1 to P8", tests="plan lifecycle; entitlement enforcement at the API boundary; preview-versus-actual parity; audit; rollback; Playwright", pr="Two PRs: backend; frontend", dod="Plans manageable without code; billing untouched"),
    P("03C", "Admin Users: complete user management (REQ-OWN-03)", "C", 3, 2, 3, (7, 10), ["REQ-OWN-03", "A-04"], depends=["03A"], decisions=["OD-BULK-ACTIONS"],
      scope="Search, filter, sort, pagination; membership inspection; restricted bulk actions; communications; support and audit view; self-lockout and escalation protection; no private content.",
      components="src/admin_repository.py; src/api/routes/admin.py; frontend users views; role-change approval (src/admin_security)", backend="List/search/sort/pagination API; membership read model; bulk action framework limited to approved actions; resend of permitted account mail", frontend="User list and detail enhancements",
      security="Privileged actions audited and approval-gated; no CV/story/interview/conversation access", acceptance="REQ-OWN-03 U1 to U9", tests="list/search/pagination; lifecycle and session revocation; role-change approval; self-lockout; bulk guards; privacy sentinels; Playwright", pr="Two PRs", dod="Operational without code changes; sentinels pass"),
    P("03D", "Command Center and AI operations (REQ-OWN-01)", "C", 3, 2, 3, (8, 12), ["REQ-OWN-01"], depends=["03A"], decisions=[],
      scope="Real sourced dashboards with period, numerator, denominator, coverage and missing-data states; AI operations view over models, configuration, prompt versions, provider readiness, agent execution and evaluation.",
      components="frontend CommandCenter.tsx, AIView.tsx; src/reporting/; src/ai_admin/; src/application/admin_readiness.py; ai_usage_facts and operational_metric_events", backend="Metric catalogue with denominators and coverage; dashboard endpoints; AI operations read model (uses 01B version data when available)", frontend="Dashboard tiles and charts chosen by meaning; AI operations view",
      security="Aggregates only; no candidate content; cohort suppression", acceptance="REQ-OWN-01 C1 to C5", tests="metric-source tests; missing-data rendering; permission matrix; Playwright; sentinels", pr="Two PRs: metrics backend; views", dod="Every tile traceable to a query and denominator"),
    P("03E", "Reports and governed custom report builder (REQ-OWN-04)", "C", 3, 4, 5, (10, 15), ["REQ-OWN-04"], depends=["03D"], decisions=["OD-REPORT-EXPORT"],
      scope="Prebuilt reports, approved-metric builder, saved configurations, exports, suppression, permissions.", components="src/reporting/; src/api/routes/admin_reports.py; frontend reports views", backend="Report registry, builder over registered metric and dimension ids, saved configuration table (migration), export", frontend="Report catalogue, builder, charts, export",
      security="No arbitrary SQL; suppression; permission checks", acceptance="REQ-OWN-04 B1 to B5", tests="metric definitions; suppression; builder guard; permissions; exports; Playwright", pr="Two PRs: registry and builder backend; UI and exports", dod="Builder cannot express an unregistered metric"),
    # ---------------- Phase 04 Track D
    P("04A", "Story Bank completion (REQ-OWN-06)", "D", 4, 2, 3, (8, 12), ["REQ-OWN-06"], scope="Manual and evidence-drafted STAR stories, provenance labels, Opportunity links, suggestions with approval, Practice reuse, feedback reflection, privacy and ownership.",
      components="src/application/stories_service.py; src/documents (evidence); frontend stories UI; interview service integration", backend="Story CRUD and provenance fields; suggestion endpoint; Practice integration; deletion", frontend="Story editor, list, filters, Opportunity link, Practice picker, provenance badge",
      security="Strict Candidate ownership; no fabricated achievements; stories are untrusted DATA in prompts", acceptance="REQ-OWN-06 S1 to S7", tests="CRUD and ownership; provenance; suggestion approval; no fabrication; Playwright acceptance journey with restart", pr="Two PRs: backend; frontend and Practice integration", dod="Acceptance journey passes in the browser"),
    P("04B", "Workspaces completion (REQ-OWN-07)", "D", 4, 2, 3, (8, 12), ["REQ-OWN-07"], decisions=["OD-WS-TRANSFER"], scope="Invitation lifecycle UI, membership, ownership transfer, explicit VIEW-only sharing UI, immediate revocation, audit.",
      components="src/application/workspace_service.py, sharing_service.py; src/api/routes/workspaces.py; frontend/app/workspaces", backend="Ownership transfer; pending/cancel/revoke endpoints; share listing", frontend="Invite, accept/decline, membership, share and revoke controls (closes CJ-D-01)",
      security="API-boundary authorization; default VIEW-only; no unshared content access", acceptance="REQ-OWN-07 W1 to W7", tests="invitation lifecycle; API-boundary authorization per resource type; revocation immediacy; transfer; two-user Playwright", pr="Two PRs", dod="Two-user journey passes"),
    P("04C", "Agent streaming and cancellation (REVIEW-05)", "D", 4, 3, 4, (8, 12), ["REVIEW-05"], depends=["01A"], scope="Authenticated SSE endpoint using astream_events v2, safe projections, progress UI, cancellation, timeouts, reconnection safety, cancelled-run cost reconciliation, synchronous fallback.",
      components="src/agent/nodes.py, events.py, graph.py; src/application/agent_service.py; src/api/routes/agent.py; frontend Mo conversation components; src/agent/usage.py", backend="SSE route; event allow-list projection; cancellation token; usage reconciliation", frontend="Progress states and cancel control in the Mo interface",
      security="No chain-of-thought, prompts, private arguments or secrets streamed; owner-scoped events; reconnection safe", acceptance="REVIEW-05 R1 to R7", tests="SSE contract; allow-list negative test; cancellation and timeout; cross-user reconnect; cancelled-run usage; sync fallback; Playwright", pr="Two PRs: backend; UI", dod="Streaming works on staging with fallback intact"),
    P("04D", "Candidate journey reliability (REQ-CAND-01)", "D", 4, 4, 4, (6, 9), ["REQ-CAND-01", "DEMO-02", "IR-AC03-TESTS", "IR-AC18-RUNLIST", "IR-DEMO-KEY", "CJ-D-02", "I-D02"], depends=["05A"],
      scope="Real browser journeys for registration to Progress on a staging stack, provider-mode indicator and accurate provider-unavailable copy, Opportunity persistence tests, owner-scoped run list, provider-key hazard guard, pricing wording consistency.",
      components="frontend/e2e/*; frontend error copy (lib/api/errors.ts); src/api error mapping; Opportunity tests; agent run list route", backend="Provider-mode status exposure (safe); owner-scoped recent runs endpoint; guard for implicit key discovery", frontend="Mode indicator, error copy, pricing wording fix",
      security="No credential or provider detail leaked in error copy; owner scoping", acceptance="REQ-CAND-01; DEMO-02", tests="Playwright journey per language on staging; provider-down simulation; AC-03 and AC-18 tests", pr="Two PRs", dod="Start interview journey test is green against a staging stack"),
    P("04E", "Invitation-only registration (REQ-BETA-01)", "D", 4, 2, 2, (3, 5), ["REQ-BETA-01"], decisions=["OD-INVITE"], scope="Registration succeeds only with a valid invitation; revocable and audited; no open sign-up; no payment path.",
      components="src/application/auth_service.py; src/auth_repository.py; frontend/app/register; Admin users", backend="Invitation model/migration and validation at registration; Admin issue/revoke", frontend="Invitation field on registration; Admin invitation controls",
      security="Prevents uninvited access; tokens stored hashed, single-use, expiring", acceptance="REQ-BETA-01", tests="invitation gate API tests; uninvited-registration Playwright; audit", pr="One PR", dod="Uninvited registration refused server-side"),
    P("04F", "Browser dictation disclosure and verification", "D", 4, 3, 3, (2, 3), ["W12.4E-16", "AC-13/AC-23-A"], scope="Legal/privacy review of the browser dictation disclosure and a live browser STT correction-burden check (browser path only; server speech stays R1.4).",
      components="frontend DictationControl; src/speech/policy (read only)", backend="none", frontend="Copy adjustments after review", security="Disclosure accuracy; no audio stored", acceptance="Reviewed wording; measured correction burden recorded", tests="human review record; measurement run", pr="Small PR if wording changes", dod="Review recorded", human="Legal reviewer and test participants"),
    # ---------------- Phase 05 Track E
    P("05A", "Hosted topology and platform hardening", "E", 5, 1, 2, (8, 12), ["EX-12.1", "EX-12.2", "EX-12.3", "EX-12.4", "EX-12.5", "EX-12.6", "EX-12.14", "EX-12.15", "H-ENV", "H-CSRF", "H-MFA"], decisions=["OD-HOSTED"],
      scope="Create staging and production topology: TLS and HSTS with automatic certificates, same-site cookies, CORS allowlist, readiness gating, single migration step, CSP, documented single-replica limits, environment separation, a worker service and knowledge volumes (missing from the current staging compose), CSRF and step-up posture review.",
      components="deploy/Caddyfile, Dockerfile.api, Dockerfile.web, docker-compose.staging.yml (db, migrate, api, web, caddy only), deploy/scripts; src/api/main.py; docs/operations_deployment.md", backend="Config guards; worker entrypoint; env separation checks", frontend="CSP and cookie behaviour verification",
      security="Production fail-closed settings; secrets only in the managed store", acceptance="PG-01", tests="scripts/eval_hosting_readiness.py; hosted rehearsal checklist EX-12 #1 to #6, #14, #15", pr="Infrastructure PRs (compose/worker/volumes) plus a runbook PR", dod="Staging reachable over TLS from a clean checkout; checklist evidence recorded", note="Needs OD-HOSTED before Phase 05 can begin."),
    P("05B", "Persistence, backup, restore and rollback drills", "E", 5, 3, 3, (6, 9), ["EX-12.7", "EX-12.8", "EX-12.9", "EX-12.10", "H-BACKUP", "PRIV-BACKUP", "H-PG-MULTI", "H-PG-QUERY", "H-PG-SECRETS", "R-96a", "R-96b"], depends=["05A", "02A"],
      scope="PostgreSQL in the hosted environment, backups that restore (database, private files, indexes), a restore drill into a separate database, rollback rehearsal, erasure from backups after account deletion, PostgreSQL-only paths exercised live (job claim, audit triggers, secrets).",
      components="deploy/scripts/backup.sh, restore.sh, migrate.sh; migrations; src/jobs; audit triggers", backend="Backup and restore scripts extended to files and indexes; backup erasure procedure", frontend="none", security="Backups encrypted and access-controlled; deletion honoured in backups within the stated window",
      acceptance="PG-09 (backup, restore, rollback)", tests="restore drill record; PostgreSQL job-claim and trigger tests against a disposable database; rollback rehearsal", pr="One PR plus drill records", dod="Drills repeatable and recorded"),
    P("05C", "Observability, alerting and provider resilience", "E", 5, 3, 3, (6, 9), ["H-MONITOR", "H-RESILIENCE", "H-REAPER", "H-FAILPATH", "EX-12.11", "J-INTEG-READY", "J-OPENROUTER", "M-OR-KEY"], depends=["05A"], decisions=["OD-BUDGET"],
      scope="Monitoring and alerting for API, worker, indexing and provider health; AI spend governor generalised from the demo ledger; quota reservation reaper scheduled; provider failure behaviour tested; pause switch verified hosted.",
      components="src/observability/; src/demo_live (budget ledger pattern); src/application/pause.py; src/jobs; src/integrations.py", backend="Production AI budget governor (hard cap, categories, kill switch); reaper schedule; alert rules", frontend="Admin provider readiness shows alert and budget state", security="Budgets fail closed; no secrets in telemetry",
      acceptance="PG-09", tests="alert tests; budget guard tests (reuse mocked-provider approach); reaper tests; failure-path tests; hosted pause verification", pr="Two PRs: budget governor; monitoring and alerts", dod="A synthetic outage raises an alert; the AI cap cannot be exceeded"),
    P("05D", "Identity, email and rate limiting live", "E", 5, 3, 3, (4, 6), ["J-BREVO", "J-BREVO-HOOK", "J-OIDC", "J-RATE", "J-REDIS", "H-REDIS-LIVE", "EX-12.12"], depends=["05A"], decisions=["OD-HOSTED"],
      scope="Live Brevo verification and recovery round trip and delivery webhooks, Google sign-in validated or disabled, shared rate-limit store validated live.", components="src/mail/; src/auth.py OIDC; src/core rate limit; frontend sign-in", backend="Brevo webhook handler; Redis store validation", frontend="Google sign-in wiring only if validated",
      security="Email tokens, PKCE and webhooks verified; fail closed", acceptance="PG-02", tests="live round trips under owner authorisation; webhook signature tests; Redis integration test", pr="One PR", dod="Round trips recorded on staging"),
    P("05E", "Privacy, legal and data-rights readiness", "E", 5, 1, 4, (4, 7), ["K-PRIV", "K-GDPR", "K-AIGUID", "PRIV-LEGAL", "PRIV-DIFF", "PRIV-DSAR", "W10.10-AUDIT-CTX", "W9.8-D10", "W9.8-D1a", "W9.8-D2", "W9.8-D9"], decisions=["OD-LANG-04"],
      scope="Counsel review of Privacy, Terms and AI-transparency; no GDPR claim without qualified review; deletion safeguards, preparation-chat ownership index, consent version history, audit allow-list; reporting differencing review; DSAR path decision.",
      components="src/privacy/; src/application/account deletion; legal version registry; docs/privacy.md; frontend legal pages", backend="Deletion safeguards, ownership index, consent history, audit allow-list enforcement", frontend="Legal page copy after counsel review", security="Core privacy work", acceptance="PG-04", tests="privacy request and deletion suites; counsel sign-off record; audit allow-list tests", pr="Two PRs", dod="Counsel sign-off per offered language", human="Legal counsel (long lead)"),
    # ---------------- Phase 06 Track F
    P("06A", "Locale audit and language boundaries", "F", 6, 1, 1, (4, 6), ["REQ-LANG-01", "REQ-LANG-07", "REQ-LANG-11", "REQ-LANG-12", "REQ-LANG-13", "REQ-LANG-14"], scope="Per-language audit; remove Russian from active Candidate selection; language/geography separation tests; per-language readiness tracking; claim discipline; Admin English-only check.",
      components="src/locales.py; frontend/lib/i18n/locales.ts (APP_LOCALES incl. ru); scripts/eval_i18n_l10n.py; frontend/scripts/scan-i18n.mjs; RELEASE_READINESS_TRACKER.md", backend="Selectable-locale list excludes ru; catalogue retained", frontend="Language selector, onboarding and settings show seven languages", security="Language never selects geography", acceptance="REQ-LANG-01, 07, 11, 12, 13, 14", tests="selectable-locale tests; separation tests; i18n evaluators", pr="Two PRs: boundaries; audit tooling", dod="Seven languages selectable; Russian code preserved and tested"),
    P("06B", "Per-language journeys, Story Bank and Workspaces", "F", 6, 4, 4, (6, 9), ["REQ-LANG-02", "REQ-LANG-05"], depends=["04A", "04B", "06A"], scope="Run and fix journeys per language including Story Bank and Workspaces.", components="frontend/e2e; i18n catalogues", backend="Fixes as found", frontend="Fixes as found", security="Owner isolation in every language", acceptance="LG-03, LG-09", tests="Playwright per language", pr="Fix PRs per language", dod="Per-language evidence recorded"),
    P("06C", "Per-language AI behaviour: prompts, interview and feedback", "F", 6, 3, 3, (5, 8), ["REQ-LANG-03", "REQ-LANG-04", "D-LANG"], depends=["01B", "06A"], scope="Policy and prompt behaviour per language; scoring invariance; localized policy sentences review.", components="src/copilot/rag/localized.py; src/prompts.py language directive; scoring code", backend="Fixes and invariance tests", frontend="none", security="No policy bypass by language", acceptance="LG-04, LG-05", tests="per-language policy suite; scoring invariance; blinded rating protocol", pr="One PR plus protocol", dod="Suites green per language"),
    P("06D", "Multilingual retrieval and cross-language attribution", "F", 6, 4, 4, (6, 9), ["REQ-LANG-06", "L-XLANG-1"], depends=["02B"], scope="Evaluate and fix multilingual retrieval, citation attribution and abstention.", components="src/copilot/retrieval; citation mapping; evaluators", backend="Evaluator and fixes", frontend="none", security="No invented translations of source claims", acceptance="LG-06", tests="multilingual retrieval evaluation with sample sizes", pr="One PR", dod="Report with limitations"),
    P("06E", "Per-language injection, security and privacy suites", "F", 6, 3, 3, (5, 8), ["REQ-LANG-08"], depends=["01A", "06A"], scope="Extend the injection corpus and privacy/PII suites to all seven languages including mixed-language input.", components="evaluations; src/security.py; privacy redaction", backend="Suites and fixes", frontend="none", security="Core", acceptance="LG-08", tests="per-language suites in CI", pr="One PR", dod="All languages pass or the language is not activated"),
    P("06F", "Native review and legal translation qualification", "F", 6, 2, 5, (2, 4), ["REQ-LANG-09", "REQ-LANG-10", "K-TRANS-LEGAL", "C-NATIVE"], depends=["06A"], decisions=["OD-LANG-03", "OD-LANG-04"], scope="Coordinate native-speaker review and qualified legal translation per language; record sign-offs.", components="review protocol documents; version registry", backend="none", frontend="Text corrections", security="Legal accuracy", acceptance="LG-10, LG-11", tests="signed records", pr="Correction PRs", dod="Signed record per language", human="Seven native reviewers and legal qualifiers (calendar-bound)"),
    P("06G", "Independent human AI evaluation", "F", 6, 4, 5, (3, 5), ["C-CITE", "C-INT-HUMAN", "C-KB-HUMAN", "L-PRODQ", "BL-19", "L-AC24", "P2-01", "P2-02", "P2-03", "P2-04"], depends=["06C", "00A"], decisions=["OD-BUDGET", "OD-GATE-THRESHOLDS"], scope="Blinded human rating of interview questions, feedback and Mo answers per language; targeted human validation; pilot revalidation of sharing, provenance and score interpretation.",
      components="docs/capstone/p10/pilot2; src/model_quality harness; rating protocol", backend="Harness support only", frontend="none", security="Synthetic or consented data only", acceptance="PG-07", tests="rating records with sample size", pr="Protocol and harness PRs", dod="Ratings recorded with reviewers named", human="Independent reviewers and participants (calendar-bound)"),
    # ---------------- Phase 07 / 08
    P("07A", "Deferral inaccessibility and engineering hygiene", "E", 7, 5, 5, (5, 8), ["REQ-DEFER-01", "DEMO-04", "DEMO-05"], depends=["05A", "03A"], scope="Consolidated UI plus API tests proving each deferred feature is unreachable; audit async blocking and optional-dependency tests.", components="gate constants; routes; frontend entry points; CI", backend="Tests", frontend="Tests", security="Core safety rule 10", acceptance="PG-10", tests="inaccessibility suite per gated family", pr="One PR", dod="Suite in CI"),
    P("07B", "Live grounding and agent-policy validation", "A", 7, 4, 4, (4, 6), ["D-NOT-LIVE", "D-MISS-AMB", "D-MISS-INS", "D-MISS-PRAC", "D-MISS-PREP", "D-MISS-5TH", "D-POLB", "D-SRC-LIST", "D-CITE-PROXY", "DEMO-03"], depends=["01B", "01C"], decisions=["OD-BUDGET"],
      scope="Bounded live re-validation of the grounding policies and historical agent misses; investigate the zero RAGAS relevancy and recall scores; larger approved RAGAS run.", components="evaluations/p10e; scripts/eval_ragas.py; demo_live pattern", backend="Evaluator updates", frontend="none", security="Spend guard mandatory", acceptance="Policies validated live with recorded results", tests="live runs under budget; deterministic evaluators unchanged", pr="One PR plus evidence", dod="Results recorded with run identity"),
    P("07C", "Residual live verifications", "E", 7, 4, 4, (2, 3), ["J-OCR"], decisions=["OD-BUDGET"], scope="Live OCR quality sample.", components="src/documents/ocr.py", backend="none", frontend="none", security="Synthetic documents", acceptance="Sample recorded", tests="live sample", pr="Evidence PR", dod="Result recorded"),
    P("08A", "Freeze, release evidence and beta readiness", "E", 8, 5, 5, (3, 5), [], depends=["07A", "06G", "05B", "05C", "05D", "05E", "03E", "04C", "04D", "04E", "02C", "02D", "02E", "06B", "06D", "06E", "06F"], decisions=["OD-SCOPE-01"],
      scope="Freeze at one SHA, assemble the evidence for PG-01 to PG-15 and LG-01 to LG-14, run the reconciliation check, owner go/no-go.", components="docs/production; CI", backend="none", frontend="none", security="No bypass of mandatory gates", acceptance="PG-15", tests="full CI, reconciliation check, release rehearsal", pr="Release evidence PR", dod="Owner go/no-go recorded", human="Owner"),
]
BYID = {p["id"]: p for p in PACKAGES}

BRIEFS = {
    "01A": dict(title="Prompt-injection security (REVIEW-01)", pr1=["Add evaluations/injection/ with a labelled corpus built from evaluations/jailbreak_test_results.csv (30 rows: categories, expected outcome, location); extend with indirect, multilingual, encoded and retrieved-document cases; freeze a held-out split with a recorded hash.",
        "Add scripts/eval_injection_corpus.py: runs detect_injection and the RAG screen over the corpus, reports detection and benign false-positive rates overall and per language/category, writes only to a temp directory unless --write, and exits non-zero below the thresholds from OD-GATE-THRESHOLDS (placeholder thresholds are NOT assumed: until approved the script reports and does not gate).",
        "Add an injection_risk field (float 0 to 1 plus indicator names) to RetrievalResult (src/copilot/models.py); compute it in src/copilot/security/rag_guard.py screen_results using the existing indicator weights; quarantine or exclude chunks above the threshold before context construction in src/copilot/service.py and the agent retrieval tool.",
        "Wire the CI step into .github/workflows/ci.yml (evaluator job) and the shard plan."],
        pr2=["Introduce an authorization layer inside ToolRegistry.validate_and_run (src/agent/registry.py): before the handler runs, verify the authenticated user, the run's declared goal and consent state, the tool's permission, and an argument allow-list; refuse and record a safe event otherwise.",
             "Negative tests: retrieved text instructing a tool call cannot cause a side-effecting tool to run; user A's run cannot read user B's evidence through any tool; invalid argument shapes are refused before side effects.",
             "Retain inspect_output and the output guard in CopilotService.answer(); add a regression asserting both still run."],
        files="src/security.py; src/copilot/security/{injection,rag_guard,output_guard}.py; src/copilot/models.py; src/copilot/service.py; src/agent/registry.py; src/agent/nodes.py; evaluations/injection/ (new); scripts/eval_injection_corpus.py (new); tests/test_injection_*.py (new)",
        out_of_scope="No new tools; no change to grounding policy semantics; no live model calls (the corpus run is offline); no threshold invented", risks="False positives on legitimate job descriptions; multilingual evasion; thresholds undecided",
        verification="eval script report committed as evidence; CI gate once thresholds approved; existing eval_agent, grounding and prompt-injection suites unchanged and green"),
    "01B": dict(title="Externalized prompt versions (REVIEW-02)", pr1=["Audit current prompts and their consumers: src/agent/policies.py SYSTEM_PROMPT, src/prompts.py technique prompts (src/prompt_registry.py PromptTechniqueSpec), src/copilot/rag/prompts.py, and how src/config_versions.py computes prompt_version today (hash based).",
        "Create the prompt asset directory (names are examples; confirm compatibility with each consumer before fixing them): prompts/agent/system.<version>.md, prompts/interview/<technique>.<version>.md, prompts/rag/system.<version>.md, each with front matter (id, semantic version, variables, compatible_with).",
        "Add src/prompt_loader.py: validated loading (front matter schema, variable checks, SHA-256 integrity), declared semantic version independent of the hash, clear errors for missing versions; keep current Python literals as the default until parity tests pass, then switch the consumers to the loader.",
        "Extend production_versions() to report declared version plus hash per prompt family; record effective prompt versions on AgentRunResult (src/agent/models.py) and evaluation results; make Prompt Lab runs record exact prompt, model and configuration.",
        "Rollback: select an existing approved version through the existing governed configuration path; no application code change; audited."],
        pr2=[], files="src/agent/policies.py; src/prompts.py; src/prompt_registry.py; src/copilot/rag/prompts.py; src/config_versions.py; src/agent/models.py; src/application/prompt_lab/; prompts/ (new); src/prompt_loader.py (new); tests/test_prompt_loader.py (new)",
        out_of_scope="No Admin free-text editing of system instructions; no prompt wording change (byte-identical defaults); no new prompt techniques", risks="Hidden formatting differences breaking the byte-identical guarantee; variable mismatches", verification="byte-identical regression for default prompts; loader, compatibility, missing-version and rollback tests; production_versions parity test"),
    "01C": dict(title="Tool registry parity (REVIEW-03)", pr1=["Add description and argument metadata to ToolSpec (src/agent/registry.py) sourced from each tool's Pydantic args model and docstring; add duplicate and invalid-registration rejection.",
        "Generate the model-visible tool section of the agent system prompt from the registry instead of the hand-written text in src/agent/policies.py.",
        "Add a parity test: registered tool names equal bind_schemas names equal the authorization policy's names; descriptions equal the generated text; fail on drift.",
        "Assert the registered tool set is unchanged by the migration (eleven tools today) so parity is never achieved by widening the set; delete the duplicated manual descriptions after the regression passes."],
        pr2=[], files="src/agent/registry.py; src/agent/policies.py; src/agent/tools.py; src/agent/specialist_tools.py; src/agent/nodes.py; tests/test_tool_registry_parity.py (new)",
        out_of_scope="No new or removed tools; no change to retrieval ownership rules", risks="Prompt wording changes alter behaviour: keep the generated text equivalent and run the tool-selection evaluation (56 deterministic cases)", verification="parity test; unchanged-tool-set assertion; existing eval_agent and tool-selection cases green; depends on 01A and 01B merging first"),
    "02A": dict(title="Permanent Knowledge reliability (REQ-OWN-05)", pr1=["Define the authoritative runtime configuration object shared by the API and the worker (database URL, data root, index collection ids) and a startup guard that refuses to serve when the worker's or index's identity differs from the registry's recorded identity (no silent empty-source UI).",
        "Add a safe Admin diagnostics endpoint and panel: database kind and fingerprint (never credentials), data root label, index collections with chunk counts and manifest checksums, worker heartbeat, last indexing result; clearly separate curated and governed views (extends PR #210).",
        "Complete the lifecycle gaps: replace, retire and reindex jobs for governed sources, idempotent and audited.",
        "Fix the staging topology gap found in Phase 00: add a worker service and persistent knowledge and index volumes to deploy/docker-compose.staging.yml (coordinate with 05A)."],
        pr2=["Backup and restore commands for the source registry, private source files and indexes with a documented restore drill into a separate environment.", "Alerts for lost collections, missing sources, incompatible embeddings (field supplied by 02B) and failed jobs.",
             "Tests: restart persistence, redeployment persistence, restore in a separate environment, retrieval and citation provenance afterwards, identity-mismatch refusal."],
        files="src/knowledge_admin/{service,runtime,readiness,wiring,jobs}.py; src/jobs/worker.py; src/copilot/constants.py; src/documents/storage.py; src/api/routes/admin_knowledge.py; frontend/components/admin/{KnowledgeView,KnowledgeReadiness}.tsx; deploy/docker-compose.staging.yml; tests/test_knowledge_persistence_*.py (new)",
        out_of_scope="Malware scanning (02C), embedding manifest fields (02B), source qualification (02D), any change to approval rules", risks="Data loss during restore drills (use disposable environments); SQLite versus PostgreSQL behaviour differences", verification="drills recorded; Admin Playwright; existing eval_admin_knowledge and W12.4A tests unchanged"),
    "03A": dict(title="Admin navigation foundation (REQ-OWN-08)", pr1=["Define six nav groups over the 20 existing destinations in frontend/lib/admin/capabilities.ts (proposed grouping, pending OD-ADMIN-NAV): Command Center (Overview); Customers and Workspaces (Users, Workspaces, Support, Privacy); Products and Commercial (Plans, Billing); AI and Knowledge (AI and models, Knowledge, Speech, Provider status, Review and Diagnostics); Insights and Operations (Reports, Jobs, Integrations); Governance and Settings (Security, Audit, Legal, Configuration, Feature flags).",
        "Replace the flat list in AdminShell.tsx with a grouped, collapsible, keyboard-accessible sidebar with active highlighting, breadcrumbs, responsive behaviour and permission-aware visibility; optional quick navigation.",
        "Move platform-wide Review and Diagnostics under /admin (for example /admin/review) with redirects from /review; remove the Review entry from the global Candidate More menu (INTERNAL_NAV in frontend/components/layout/nav-items.ts); keep the owner-scoped /review/agent run details for Candidates.",
        "Update tests/_admin_matrix.py DOMAINS and regenerate frontend/tests/fixtures/admin-role-permissions.json only if a route or permission changes (none is expected)."],
        pr2=[], files="frontend/components/admin/AdminShell.tsx; frontend/lib/admin/capabilities.ts; frontend/components/layout/nav-items.ts; frontend/app/admin/*; frontend/app/review/*; frontend/tests/admin-shell-w10-1.test.tsx; frontend/e2e/admin*.spec.ts",
        out_of_scope="No new Admin features, permissions or routes beyond the relocation and redirects; backend authorization unchanged", risks="Broken deep links (mitigated by redirects); role-visibility regressions", verification="vitest for grouping and visibility per role; Playwright for expand/collapse, keyboard, breadcrumbs, responsive and redirects; backend 403 tests for diagnostics remain green; accessibility checks"),
}

# ---------------------------------------------------------------- analysis


def load_items() -> dict[str, dict]:
    doc = json.loads(RECON.read_text(encoding="utf-8"))
    return {r["id"]: r for r in doc["items"]}


def r10_items(items: dict[str, dict]) -> list[str]:
    return sorted(i for i, r in items.items() if r["disposition"] in ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0"))


def topo_order() -> list[str]:
    order, seen, temp = [], set(), set()

    def visit(n):
        if n in seen:
            return
        if n in temp:
            raise ValueError(f"dependency cycle at {n}")
        temp.add(n)
        for d in BYID[n]["depends"]:
            visit(d)
        temp.discard(n)
        seen.add(n)
        order.append(n)

    for p in PACKAGES:
        visit(p["id"])
    return order


def critical_path(which: int) -> tuple[list[str], float]:
    """Longest dependency chain by effort days (which=0 min, 1 max): a lower bound on duration regardless of parallelism."""
    best: dict[str, tuple[float, list[str]]] = {}
    for n in topo_order():
        p = BYID[n]
        prev = max((best[d] for d in p["depends"]), default=(0.0, []), key=lambda t: t[0])
        best[n] = (prev[0] + p["effort"][which], prev[1] + [n])
    return max(best.values(), key=lambda t: t[0])[1], max(v[0] for v in best.values())


def totals() -> dict:
    lo = sum(p["effort"][0] for p in PACKAGES)
    hi = sum(p["effort"][1] for p in PACKAGES)
    window_days = 5 * WORKING_DAYS_PER_WEEK   # W1 to W5
    per_stream = window_days * UTILISATION
    return dict(packages=len(PACKAGES), min_days=lo, max_days=hi, window_working_days=window_days, per_stream_productive_days=per_stream,
                streams_needed_min=lo / per_stream, streams_needed_max=hi / per_stream, cp_min=critical_path(0), cp_max=critical_path(1))


def validate() -> list[str]:
    errs: list[str] = []
    items = load_items()
    need = set(r10_items(items))
    owner: dict[str, list[str]] = {}
    for p in PACKAGES:
        for i in p["items"]:
            owner.setdefault(i, []).append(p["id"])
    for i in need:
        if len(owner.get(i, [])) != 1:
            errs.append(f"R1.0 item {i} is in {len(owner.get(i, []))} packages (must be exactly one)")
    for i, pk in owner.items():
        if i not in items:
            errs.append(f"package {pk} lists unknown item {i}")
        elif i not in need:
            errs.append(f"package {pk} lists {i}, which is not an R1.0 fix/verify item (disposition {items[i]['disposition']})")
        if len(pk) > 1:
            errs.append(f"item {i} is in several packages {pk}")
    ids = [p["id"] for p in PACKAGES]
    if len(ids) != len(set(ids)):
        errs.append("duplicate package ids")
    for p in PACKAGES:
        if p["track"] not in TRACKS:
            errs.append(f"{p['id']}: unknown track")
        if p["phase"] not in PHASES or not p["id"].startswith(f"{p['phase']:02d}"):
            errs.append(f"{p['id']}: id must start with its phase number")
        if not (0 <= p["start"] <= p["end"] <= 5):
            errs.append(f"{p['id']}: invalid weeks")
        for k in ("scope", "components", "backend", "frontend", "security", "acceptance", "tests", "pr", "dod"):
            if not str(p[k]).strip():
                errs.append(f"{p['id']}: empty {k}")
        lo, hi = p["effort"]
        if not (0 < lo <= hi):
            errs.append(f"{p['id']}: invalid effort")
        for d in p["depends"]:
            if d not in BYID:
                errs.append(f"{p['id']}: unknown dependency {d}")
            elif p["start"] < BYID[d]["end"]:
                errs.append(f"{p['id']} starts in week {p['start']} before its dependency {d} ends in week {BYID[d]['end']}")
    try:
        topo_order()
    except ValueError as exc:
        errs.append(str(exc))
    for b in BRIEFS:
        if b not in BYID:
            errs.append(f"brief for unknown package {b}")
    for need_brief in ("01A", "01B", "01C", "02A", "03A"):
        if need_brief not in BRIEFS:
            errs.append(f"missing implementation brief {need_brief}")
    return errs


# ---------------------------------------------------------------- rendering


def render_register() -> str:
    items = load_items()
    t = totals()
    L = ["# Implementation Package Register (Phase 00)", "", "**Status:** GENERATED by `scripts/production/execution_packages.py` (single source of truth for package scope, dependencies, effort and schedule). Item dispositions come from `PRODUCTION_ISSUE_RECONCILIATION.json` and are not copied here beyond IDs. Do not edit by hand. No package is started; Phase 01 needs owner approval.", "",
         f"{t['packages']} packages cover all {len(r10_items(items))} R1.0 fix/verify items, each assigned to exactly one package (machine-checked). Effort is in ideal engineering days (low to high) for one engineer or one focused agent session; it excludes calendar-bound human and legal review, shown as `human`.", "",
         "## Packages", "", "| ID | Package | Track | Phase | Weeks | Effort (days) | Depends on | Open decisions | R1.0 items | Human/calendar-bound |", "|---|---|---|---|---|---|---|---|---|---|"]
    for p in PACKAGES:
        L.append(f"| {p['id']} | {p['name']} | {p['track']} | {p['phase']} | {WEEKS[p['start']].split(' ')[0]}-{WEEKS[p['end']].split(' ')[0]} | {p['effort'][0]}-{p['effort'][1]} | {', '.join(p['depends']) or 'none'} | {', '.join(p['decisions']) or 'none'} | {len(p['items'])} | {p['human'] or 'no'} |")
    L += ["", f"Total effort: {t['min_days']} to {t['max_days']} engineering days. Critical path (longest dependency chain): {t['cp_min'][1]:.0f} to {t['cp_max'][1]:.0f} days (see `DEPENDENCY_GRAPH.md`).", "", "## Package detail", ""]
    for p in PACKAGES:
        L += [f"### {p['id']} {p['name']}", "", f"- **Track / phase / weeks:** {p['track']} ({TRACKS[p['track']]}) / {p['phase']} / {WEEKS[p['start']]} to {WEEKS[p['end']]}", f"- **Scope:** {p['scope']}", f"- **Dependencies:** {', '.join(p['depends']) or 'none'}; **owner decisions:** {', '.join(p['decisions']) or 'none'}",
              f"- **Existing components affected:** {p['components']}", f"- **Expected backend changes:** {p['backend']}", f"- **Expected frontend changes:** {p['frontend']}", f"- **Security and privacy:** {p['security']}",
              f"- **Acceptance criteria:** {p['acceptance']}", f"- **Required tests:** {p['tests']}", f"- **Estimated effort:** {p['effort'][0]} to {p['effort'][1]} engineering days" + (f"; calendar-bound: {p['human']}" if p["human"] else ""),
              f"- **PR boundary:** {p['pr']}", f"- **Definition of Done:** {p['dod']}", f"- **R1.0 items ({len(p['items'])}):** {', '.join(p['items']) or 'none'}"]
        if p["note"]:
            L.append(f"- **Note:** {p['note']}")
        L.append("")
    L += ["## First PR briefs (exact implementation briefs; NOT implemented)", ""]
    for k, b in BRIEFS.items():
        L += [f"### {k} {b['title']}", "", "**PR 1 scope**", ""] + [f"{n}. {s}" for n, s in enumerate(b["pr1"], 1)]
        if b["pr2"]:
            L += ["", "**PR 2 scope**", ""] + [f"{n}. {s}" for n, s in enumerate(b["pr2"], 1)]
        L += ["", f"**Files:** {b['files']}", f"**Out of scope:** {b['out_of_scope']}", f"**Risks:** {b['risks']}", f"**Verification:** {b['verification']}", ""]
    return "\n".join(L)


def render_graph() -> str:
    t = totals()
    order = topo_order()
    L = ["# Dependency Graph (Phase 00)", "", "**Status:** GENERATED from the package definitions. Dependencies mean: the dependent package starts no earlier than the week in which its dependency finishes (merged). Owner decisions and human reviews are shown as external gates.", "",
         "## Package dependencies", "", "```mermaid", "graph LR"]
    for p in PACKAGES:
        L.append(f'  {"P" + p["id"]}["{p["id"]} {p["name"][:34]}"]')
    for p in PACKAGES:
        for d in p["depends"]:
            L.append(f'  P{d} --> P{p["id"]}')
    L += ["```", "", "## Dependency order (topological)", "", ", ".join(order), "", "## Critical path", "",
          f"Lowest-effort chain: {' -> '.join(t['cp_min'][0])} = {t['cp_min'][1]:.0f} days. Highest-effort chain: {' -> '.join(t['cp_max'][0])} = {t['cp_max'][1]:.0f} days. These are lower bounds on elapsed effort no matter how many people work in parallel; they exclude calendar-bound human and legal review.", "",
          "## Shared modules and safe integration order", "", "| Shared module | Packages that edit it | Safe order |", "|---|---|---|",
          "| src/agent/policies.py and the tool-execution path (registry.py, nodes.py) | 01A, 01B, 01C, 04C | 01B, then 01A, then 01C; 04C after 01A |", "| src/prompts.py, src/prompt_registry.py, src/config_versions.py | 01B, 06C | 01B before 06C |",
          "| src/copilot/security/ and src/copilot/models.py (RetrievalResult) | 01A, 02B, 06D, 06E | 01A first |", "| src/knowledge_admin/ and src/copilot/embeddings.py, retrieval/ | 02A, 02B, 02C, 02D, 02E | 02A, then 02B and 02C, then 02D and 02E |",
          "| frontend/components/admin/AdminShell.tsx and frontend/lib/admin/capabilities.ts | 03A, 03B, 03C, 03D, 03E | 03A first; the rest rebase on it |", "| frontend/components/layout/nav-items.ts | 03A only | single owner |", "| tests/_admin_matrix.py and the admin role fixture | 03A to 03E | regenerate only when a permission or route changes |",
          "| deploy/docker-compose.staging.yml, Dockerfiles, deploy/scripts | 02A (worker, volumes), 02C (clamd), 05A, 05B | 05A owns the file; 02A and 02C supply fragments |", "| Alembic migrations (head 0039_speech_governance) | 03E, 04A, 04B, 04E (new tables) | one migration per PR, sequential heads, never two heads |",
          "| src/application/agent_service.py and Mo UI | 04C, 04D | 04C then 04D |", "| i18n catalogues (frontend/lib/i18n/messages) | all frontend packages | add keys to all locales in the same PR (existing rule) |", "",
          "## External gates (not engineering dependencies)", "", "- Owner decisions: OD-SCOPE-01, OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS, OD-INVITE, OD-MALWARE, OD-PLAN-ENFORCE, OD-ADMIN-NAV, OD-BULK-ACTIONS, OD-REPORT-EXPORT, OD-WS-TRANSFER, OD-LANG-02, OD-LANG-03, OD-LANG-04, OD-COVERAGE, OD-EMBED, OD-US-CONTENT.",
          "- Human and legal: named reviewers (00A), native review and legal translation (06F), independent human evaluation (06G), counsel review (05E), licence review (02D).", ""]
    return "\n".join(L)


def render_schedule() -> str:
    t = totals()
    L = ["# Delivery Schedule (Phase 00)", "", "**Status:** GENERATED from the package definitions; PROPOSED. R1.0 is the owner's target of 30 November 2026; safety, privacy, licensing and operational gates are not waived to meet it. Weeks run Monday to Friday; the freeze is the end of W5 (27 November) and release is 30 November.", "",
         "## Package schedule by week", "", "| Package | " + " | ".join(WEEKS[w].split(" ")[0] for w in range(6)) + " |", "|---|" + "---|" * 6]
    for p in PACKAGES:
        cells = ["#" if p["start"] <= w <= p["end"] else "" for w in range(6)]
        L.append(f"| {p['id']} {p['name'][:46]} | " + " | ".join(cells) + " |")
    L += ["", "Weeks: " + "; ".join(f"{k.split(' ')[0]} = {k.split(' ', 1)[1]}" for k in WEEKS.values()) + ".", "", "## Phases mapped to weeks", "", "| Phase | Name | Packages | Weeks |", "|---|---|---|---|"]
    for ph, name in PHASES.items():
        ps = [p for p in PACKAGES if p["phase"] == ph]
        if ps:
            L.append(f"| {ph:02d} | {name} | {', '.join(p['id'] for p in ps)} | {WEEKS[min(p['start'] for p in ps)].split(' ')[0]}-{WEEKS[max(p['end'] for p in ps)].split(' ')[0]} |")
    L += ["", "Phases are groupings for sequencing and review, not strict serial stages: Phases 01 to 06 run in parallel across tracks where their dependencies allow; Phases 07 and 08 are sequential at the end.", "", "## Weekly milestones and measurable exit gates", "", "| Week | Milestone | Exit gate (measurable) |", "|---|---|---|",
          "| W0 21-25 Oct | Phase 00 approved; decisions made; people named | Owner approves Phase 00; OD-SCOPE-01, OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS, OD-INVITE, OD-MALWARE answered; reviewers A, B, C appointed (00A) |",
          "| W1 26 Oct-1 Nov | Foundations started; first PRs open | 01A corpus and evaluator merged; 01B loader merged with byte-identical defaults; 02A identity and configuration merged; 03A navigation merged; 05A staging reachable over TLS; 06A seven-language selection; reconciliation delta (00B) decided |",
          "| W2 2-8 Nov | Track A and B core complete; Admin and Story/Workspace build | 01A tool authorization merged; 02A restore drill passed; 04E invitations merged; 03B/03C/03D in review; 04A/04B in review |",
          "| W3 9-15 Nov | Integration of A and B; Track D streaming; hosted drills | 01C parity test in CI; 02B/02C merged; 05B restore drill and rollback recorded; 05C alerts firing on a synthetic outage; 04C streaming on staging; 06C/06E suites green or languages flagged |",
          "| W4 16-22 Nov | Reports, journeys and per-language evidence | 03E merged; 04D journey green on staging for each language that can pass; 06B/06D evidence; 02E both coverage measures reported; 07B live validation within budget; human review in progress |",
          "| W5 23-27 Nov | Freeze, evidence and go/no-go | Freeze at one SHA; 07A inaccessibility suite green; PG-01 to PG-15 and LG-01 to LG-14 evidence assembled; reconciliation check passes; owner go/no-go recorded |",
          "| 30 Nov | R1.0 beta | Invitations sent only for languages and markets whose gates passed |", "",
          "## Work that can safely run in parallel", "", "- Track A (01A, 01B), Track B (02A), Track C (03A) and Track E (05A, 05E) share no files in W1 and start together; 06A also starts in W1.", "- 03B, 03C, 03D, 04A, 04B and 04E run in parallel in W2 once 03A has landed; 04A and 04B touch separate modules.",
          "- 05B, 05C and 05D run in parallel in W3 after 05A; 02B and 02C run in parallel after 02A; 06C and 06E run in parallel after 01A, 01B and 06A.", "- Native review, legal translation, counsel review and licence review (02D, 05E, 06F, 06G) are calendar-bound and start in W1 regardless of engineering.", "",
          "## Capacity and feasibility (computed)", "", f"- Package effort total: **{t['min_days']} to {t['max_days']} ideal engineering days** across {t['packages']} packages.", f"- Window: W1 to W5 = {t['window_working_days']} working days. With {int(UTILISATION * 100)}% utilisation (review, CI waits, rework: an assumption) one stream delivers about {t['per_stream_productive_days']:.1f} productive days.",
          f"- Parallel streams needed to fit the total in the window: **{t['streams_needed_min']:.1f} to {t['streams_needed_max']:.1f}** (one stream = one engineer or one focused agent session; the owner's real capacity is not recorded anywhere and is an input needed for OD-SCOPE-01).",
          f"- Critical path lower bound: {t['cp_min'][1]:.0f} to {t['cp_max'][1]:.0f} days of strictly sequential effort inside a {t['window_working_days']}-working-day window, before any human review lead time.", "",
          "| Parallel streams | Productive days available | Covers minimum estimate | Covers maximum estimate |", "|---|---|---|---|"]
    for n in (1, 2, 3, 4, 6, 8, 10, 12):
        cap = n * t["per_stream_productive_days"]
        L.append(f"| {n} | {cap:.0f} | {'yes' if cap >= t['min_days'] else 'no'} | {'yes' if cap >= t['max_days'] else 'no'} |")
    L += ["", "See `PHASE_00_EXIT_REPORT.md` for the November feasibility assessment and scope options.", ""]
    return "\n".join(L)


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "check"
    errs = validate()
    if errs:
        print("\n".join(errs[:40]))
        return 1
    if cmd == "generate":
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "IMPLEMENTATION_PACKAGE_REGISTER.md").write_text(render_register(), encoding="utf-8")
        (OUT / "DEPENDENCY_GRAPH.md").write_text(render_graph(), encoding="utf-8")
        (OUT / "DELIVERY_SCHEDULE.md").write_text(render_schedule(), encoding="utf-8")
        print(json.dumps({k: v for k, v in totals().items() if k not in ("cp_min", "cp_max")}, indent=1), totals()["cp_min"], totals()["cp_max"])
        return 0
    if cmd == "check":
        for name, fn in (("IMPLEMENTATION_PACKAGE_REGISTER.md", render_register), ("DEPENDENCY_GRAPH.md", render_graph), ("DELIVERY_SCHEDULE.md", render_schedule)):
            f = OUT / name
            if not f.exists() or f.read_text(encoding="utf-8") != fn():
                print(f"{name} is stale: run `generate`")
                return 1
        print(f"OK: {len(PACKAGES)} packages, every R1.0 fix/verify item in exactly one package, dependencies acyclic and schedule consistent")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
