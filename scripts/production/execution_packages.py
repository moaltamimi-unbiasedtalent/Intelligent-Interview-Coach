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
WEEKS = {0: "W0 21-25 Oct", 1: "W1 26 Oct-1 Nov", 2: "W2 2-8 Nov", 3: "W3 9-15 Nov", 4: "W4 16-22 Nov", 5: "W5 23-27 Nov", 6: "W6 30 Nov-4 Dec", 7: "W7 7-11 Dec", 8: "W8 14-18 Dec", 9: "W9 21-25 Dec", 10: "W10 28 Dec-1 Jan", 11: "W11 4-8 Jan", 12: "W12 11-15 Jan"}
WORKING_DAYS_PER_WEEK = 5
UTILISATION = 0.7   # assumption: review, CI waits, context switching and rework leave 70% of a stream's days productive


def P(id_, name, track, phase, start, end, effort, items, depends=(), decisions=(), scope="", components="", backend="", frontend="", security="", acceptance="", tests="", pr="", dod="", human="", note=""):
    return dict(id=id_, name=name, track=track, phase=phase, start=start, end=end, effort=effort, items=list(items), depends=list(depends), decisions=list(decisions), scope=scope, components=components,
                backend=backend, frontend=frontend, security=security, acceptance=acceptance, tests=tests, pr=pr, dod=dod, human=human, note=note)


PACKAGES = [
    P("00A", "Governance, reviewers and owner decisions", "F", 0, 0, 1, (2, 4), ["BL-1", "BL-2", "BL-3", "BL-18", "REQ-SCOPE-01"], decisions=["OD-RESOURCE", "OD-LANG-03", "OD-LANG-04"],
      scope="Owner names reviewers A, B, C, the seven native reviewers and the legal qualifiers; two-person role changes recorded; the owner decides the open decisions that block Phase 01 to 06.",
      components="docs/production/OWNER_DECISION_REGISTER.md; Admin role-change approval flow (existing); audit log", backend="none (uses existing role-change approvals for appointments)", frontend="none",
      security="Appointments are privileged role changes: two-person approval with step-up, audited", acceptance="Appointment table filled; three reviewer accounts verified; audit evidence of the role changes; decision register has an owner answer for every Phase 01 to 03 blocker",
      tests="audit-log evidence; role-change approval tests already exist", pr="Documentation PR recording decisions and appointments (no code)", dod="Named people recorded; decisions recorded; evidence linked", human="Owner and named reviewers"),
    P("00B", "Scope reconciliation delta (documentation only)", "B", 0, 1, 1, (1, 2), ["BL-5", "BL-6", "BL-6.1", "BL-6.2", "BL-6.3", "BL-6.4", "BL-6.5", "BL-9", "BL-12", "W12.4E-12"], decisions=["OD-RECLASS"],
      scope="Ten items classified R1.0 concern capabilities proven inaccessible to Candidates (Compensation V2 and US occupational foundation work, server-side recording client). Propose their reclassification (R1.5, R1.6 or R1.4) for owner confirmation; apply only after the owner confirms. Evidence and the two items that fail the proof (BL-6.6, BL-7) are in R1_SCOPE_RECLASSIFICATION_PROPOSAL.md.",
      components="docs/production/PRODUCTION_ISSUE_RECONCILIATION.json and scripts/production/reconcile_issues.py (regenerated, historical register untouched)", backend="none", frontend="none",
      security="Reclassification must keep REQ-DEFER-01 satisfied: the affected features stay inaccessible", acceptance="Owner confirms or rejects each proposed move; the reconciliation is regenerated with explained deltas and zero unmapped",
      tests="scripts/production/reconcile_issues.py check; tests/test_production_reconciliation.py", pr="Docs-only PR: reconciliation delta", dod="Reconciliation regenerated, counts explained, owner decision recorded", human="Owner"),
    # ---------------- Phase 01 Track A
    P("01A", "Prompt-injection corpus, risk score and quarantine (REVIEW-01 part 1)", "A", 1, 1, 2, (5, 8), ["REVIEW-01", "D-LEX", "D-AGENT-TXT", "D-NONNUM", "D-SENT", "D-EST-FLAG", "D-COUNTRY"], decisions=["OD-GATE-THRESHOLDS"],
      scope="Labelled regression corpus from evaluations/jailbreak_test_results.csv (direct, indirect, multilingual, encoded, retrieved-document); detection and false-positive measurement; CI gate on a frozen held-out set; injection-risk score on RetrievalResult; quarantine of high-risk chunks before context; output guard retained. Touches no agent-policy or tool-execution file, so it does not overlap 01B. REVIEW-01 requirements R4 and R5 (tool-call authorization) are delivered by 01D, which closes REVIEW-01.",
      components="src/security.py (detect_injection); src/copilot/security/ (injection, rag_guard, output_guard, grounding_policy); src/copilot/models.py (RetrievalResult); src/copilot/service.py answer(); src/agent/nodes.py and registry.py validate_and_run; evaluations/",
      backend="Add risk score field to RetrievalResult; extend rag_guard.screen_results to quarantine by score; corpus loader and evaluator script", frontend="none (no user-visible change; optional safe 'content withheld' note reuses existing insufficient-evidence copy)",
      security="Core safety work: no cross-user disclosure, no unauthorized tool side effects, no sole reliance on the prompt; evaluator uses only public/synthetic data", acceptance="REVIEW-01 R1, R2, R3 and R6 (R4 and R5 close in 01D); detection and false-positive rates reported per language and above owner-approved thresholds on the frozen held-out set; cross-user retrieval negative tests pass",
      tests="held-out corpus evaluator in CI (new scripts/eval_injection_corpus.py); cross-user retrieval tests; output-guard regression; existing eval_agent and grounding suites unchanged", pr="One PR: corpus, evaluator, risk score and quarantine", dod="CI gate green on held-out set once thresholds are approved; no regression in existing security suites; documentation of residual risk"),
    P("01D", "Tool-call authorization layer (REVIEW-01 part 2)", "A", 1, 3, 3, (3, 5), [], depends=["01A", "01B"], decisions=[],
      scope="Server-side revalidation of every model-requested tool call against the authenticated user's actual goal, authorization, tool permissions and allowed arguments before any side effect; negative tests that malicious retrieved content cannot trigger an unauthorized tool call. Overlaps the agent-policy and tool-execution path, so it is sequenced after 01B (versioned prompts) and before 01C (registry parity).",
      components="src/agent/registry.py (ToolRegistry.validate_and_run); src/agent/nodes.py (tool node); src/agent/policies.py (read only after 01B); src/agent/state.py (declared goal and consent state)", backend="Authorization step inside validate_and_run: authenticated user, declared run goal, tool permission, argument allow-list; safe refusal event and audit; no new tools", frontend="none",
      security="Decisive authorization before execution or side effects; never relies on the model obeying an instruction", acceptance="REVIEW-01 R4 and R5; with 01A, REVIEW-01 R1 to R6 are complete",
      tests="tool-authorization negative tests (retrieved text instructing a side-effecting tool; cross-user evidence access through tools; invalid argument shapes before side effects); existing eval_agent and tool-selection cases unchanged", pr="One PR", dod="REVIEW-01 can be marked complete; no tool-set change",
      note="Closes REVIEW-01 together with 01A; REVIEW-01 itself is assigned to 01A."),
    P("01B0", "Prompt asset format and loader contract (interface package)", "A", 1, 1, 1, (2, 3), [], decisions=[],
      scope="The prompt asset schema (id, semantic version, variables, compatibility), the loader interface and the declared-version plus SHA contract, with conformance tests. It lets the per-language prompt and policy work (06C) and the prompt consumers proceed against a stable interface while 01B migrates the existing prompt literals.",
      components="src/prompt_registry.py; src/config_versions.py; new src/prompt_loader.py interface", backend="Schema, loader protocol and conformance tests; no prompt text moves yet", frontend="none", security="Integrity hash verified at load; no Admin free-text editing",
      acceptance="Contract merged; 01B and 06C conform to it", tests="schema and conformance tests; existing prompt tests unchanged", pr="One small PR", dod="01B and 06C can start against the merged contract"),
    P("01B", "Externalized, versioned prompts (REVIEW-02)", "A", 1, 1, 2, (5, 8), ["REVIEW-02"], depends=["01B0"], scope="Move agent, interview technique and RAG prompts to versioned assets with a validated loader, semantic versions plus SHA, run attribution and rollback without code.",
      components="src/agent/policies.py (SYSTEM_PROMPT); src/prompts.py (733 lines); src/prompt_registry.py; src/copilot/rag/prompts.py; src/config_versions.py (production_versions); src/agent/models.py (AgentRunResult); Prompt Lab (src/application/prompt_lab/)",
      backend="Prompt asset directory and loader with variable validation; declared versions; production_versions() reports version plus hash; AgentRunResult and evaluation results record effective prompt versions; rollback selection via the existing governed-configuration mechanism", frontend="none (Admin AI operations later surfaces versions: 03D)",
      security="Prompts remain code-reviewed assets; no Admin free-text editing of system instructions; integrity hash verified at load", acceptance="REVIEW-02 R1 to R7", tests="loader unit tests; compatibility, missing-version and rollback tests; production_versions parity test; Prompt Lab attribution test; byte-identical prompt output regression for current defaults",
      pr="One PR per prompt family if large: agent; interview; RAG", dod="Defaults produce byte-identical prompts; versions visible in run results; rollback tested"),
    P("01C", "Tool registry parity (REVIEW-03)", "A", 1, 4, 4, (3, 5), ["REVIEW-03"], depends=["01B", "01D"], scope="Registry as the single catalogue: generated model-visible descriptions, Pydantic-derived argument contracts, duplicate rejection, parity tests, no widened tool set.",
      components="src/agent/registry.py; src/agent/policies.py; src/agent/tools.py; src/agent/specialist_tools.py; src/agent/nodes.py (bindings)", backend="Descriptions generated from ToolSpec metadata; parity test across registry, bindings and authorization policy; remove duplicated text after regression", frontend="none",
      security="The tool set must be unchanged (asserted); authorization policy derived from the same catalogue", acceptance="REVIEW-03 R1 to R6", tests="registry parity, duplicate-registration, binding/policy parity, unchanged-tool-set assertion; existing eval_agent and tool-selection cases unchanged", pr="One PR", dod="No manual duplicate descriptions remain; parity test in CI",
      note="Sequenced after 01B (versioned prompts) and 01D (tool-call authorization) because all three edit src/agent/policies.py or the tool-execution path: 01B, then 01D, then 01C."),
    # ---------------- Phase 02 Track B
    P("02K", "Knowledge runtime and manifest contract (interface package)", "B", 2, 1, 1, (2, 3), [], decisions=[],
      scope="A typed contract for the knowledge runtime identity (database kind and fingerprint, data root label, collection ids), the index manifest v2 (embedding provider, model, version, dimensions, checksums, compatibility metadata) and the scanner interface; contract tests. It lets 02A (persistence and lifecycle), 02B (embedding integrity) and 02C (scanning) proceed in parallel instead of in a chain.",
      components="src/knowledge_admin/readiness.py, runtime.py; src/copilot/embeddings.py (manifest fields); src/documents/file_security.py (scanner protocol)", backend="Contract types, manifest schema and conformance tests; no behaviour change", frontend="none",
      security="Manifests carry identity and checksums, never secrets", acceptance="Contract merged with a conformance suite that 02A, 02B and 02C must pass", tests="schema and conformance tests; existing knowledge tests unchanged", pr="One small PR", dod="Three consumers can start against the merged contract"),
    P("02A", "Permanent Knowledge reliability: persistence, environment identity, restore (REQ-OWN-05)", "B", 2, 1, 2, (10, 15), ["REQ-OWN-05", "DEMO-01", "H-WORKER", "H-KB-INGEST"], decisions=["OD-HOSTED"],
      scope="Persistence and environment architecture for governed and curated knowledge: durable registry, private file storage, persistent indexes, safe environment/database/index identity diagnostics, one authoritative configuration shared by API and worker, lifecycle including replace, retire and reindex, backup and restore, alerts, restart/redeploy/restore tests.",
      components="src/knowledge_admin/ (service, runtime, readiness, wiring, jobs); src/jobs/worker.py; src/copilot/constants.py data_path (anchored root); src/documents/storage.py; src/api/routes/admin_knowledge.py; frontend/components/admin/KnowledgeView.tsx and KnowledgeReadiness.tsx; deploy/docker-compose.staging.yml",
      backend="Environment identity endpoint (safe: database kind, data root, index collection ids, manifest checksums); startup guard that refuses a UI/API pair whose worker or store identity differs; reindex/replace/retire lifecycle completion; backup and restore commands for registry, files and indexes; health alerts", frontend="Admin Knowledge: environment identity panel and clearer curated versus governed views (builds on PR #210)",
      security="Licence and provenance safeguards preserved; no demo fixture labelled production evidence; fail closed on identity mismatch; Admin sees metadata only", acceptance="REQ-OWN-05 K1 to K9 except scanner (02C) and embedding manifest identity (02B)",
      tests="restart persistence; redeployment persistence; restore into a separate environment; identity mismatch refusal; retrieval and citation provenance after restore; Admin Playwright for identity and views", pr="Two PRs: (1) identity, configuration unification, lifecycle; (2) backup/restore and alerts", dod="Drills documented and repeatable; no silent empty-source state; staging topology includes worker and knowledge volumes (see 05A)"),
    P("02B", "Embedding integrity and index manifests (REVIEW-04)", "B", 2, 3, 3, (6, 10), ["REVIEW-04", "B-EMBED-CRED"], depends=["02K"], decisions=["OD-BUDGET", "OD-EMBED"],
      scope="Readiness shows actual embedder and degradation; production refuses hash-embedding fallback and fails closed on missing semantic credentials; manifests record provider, model, version, dimensions and checksums; query/index mismatch detected and refused; rebuild from approved sources; BM25, vector and RRF evaluated separately and combined, multilingual.",
      components="src/copilot/constants.py; src/copilot/config.py; src/copilot/embeddings.py (build_embedder, LocalHashEmbedder); src/copilot/retrieval/hybrid.py, vector.py, fusion.py; knowledge build and readiness (src/knowledge_admin/readiness.py)",
      backend="Provider resolution rewritten with an explicit production mode; manifest schema extension; mismatch guard at query time; rebuild command; retrieval-mode evaluator", frontend="Readiness panel shows embedder, model and degradation state",
      security="Paid embedding builds are budgeted (OD-BUDGET) and go through the AI spend guard; no secrets in manifests", acceptance="REVIEW-04 R1 to R7", tests="readiness tests; production fail-closed tests; manifest and mismatch tests; offline-dev labelling test; retrieval-mode evaluation with sample sizes", pr="Two PRs: (1) resolution, guard, manifest; (2) rebuild and evaluation", dod="No path serves candidates from an unlabelled hash index in production; evaluation report with limitations"),
    P("02C", "Real malware scanning for uploads", "B", 2, 3, 3, (5, 8), ["B-SCANNER", "J-CLAMAV", "EX-12.13"], depends=["02K"], decisions=[],
      scope="Replace the ClamAV stub with a real clamd client and deploy the daemon; fail closed for real uploads; the fake scanner never runs outside development; alert when signatures are stale or the scanner is down.",
      components="src/documents/file_security.py (ClamAvScanner stub, enforce_scan); src/integrations.py (malware_scanner); governed knowledge upload path; Candidate document upload", backend="clamd INSTREAM client, health probe, signature-age check, configuration guard (hosted environments refuse FILE_SCAN_PROVIDER=fake)", frontend="Admin integration status shows scanner state (existing panel)",
      security="Uploads are never reported clean unless a real scan ran and passed; fail closed on unavailability", acceptance="REQ-OWN-05 K6; EX-12 #13 verified in the hosted environment", tests="EICAR test through a real clamd container in a dedicated CI job; fail-closed tests; hosted verification", pr="One PR plus infrastructure change in 05A", dod="Real scan evidence in staging; fake scanner refused outside dev"),
    P("02D", "Market source qualification and licensing (selected EU markets)", "B", 2, 2, 4, (6, 10), ["A-K1", "BL-4", "BL-8", "K-HUMANSRC", "K-LIC-ESCO", "K-LIC-ISCO", "K-LIC-OGL", "K-LIC-DE", "BL-14", "BL-15", "D-08", "REQ-COV-02"], depends=["00A"], decisions=["OD-LANG-02", "OD-US-CONTENT"],
      scope="For each approved market: licence, authority and coverage qualification of the sources actually enabled; exclusion of unsupported or unlicensed evidence from enabled features; decision on US-sourced content (O*NET, BLS) in an EU beta; alias curation ownership.",
      components="docs/capstone/p10/P10C_F1_SOURCE_APPROVAL_REGISTER.md; src/knowledge_admin (approval); src/copilot/knowledge/governance.py; data/knowledge manifests; retrieval approval filtering", backend="Approval filter so only qualified, licensed sources reach candidate retrieval for the enabled markets; per-market enable switch tied to an approved register entry", frontend="Admin shows which markets are enabled and why",
      security="Licence integrity; no unlicensed content served; provenance preserved", acceptance="Signed approval entry per enabled market; a candidate cannot retrieve an unqualified source (test); US content decision recorded. Phase 00 evidence: curated US sources (bls_ooh narratives, bls_oews and ons_ashe compensation records only; no EU compensation records exist) are reachable by Candidates, for example a bls_ooh passage for a UK nurse question, so excluding unqualified US claims needs this package's approval filter or the OD-US-CONTENT decision; it is NOT achieved by the 00B reclassification", tests="retrieval-approval tests; market-enable tests; licence register consistency check", pr="Engineering PR for the approval filter; documentation PRs for the register", dod="Every enabled market has a recorded qualification; unqualified markets are not offered", human="Legal/licensing reviewer and owner (long lead)"),
    P("02E", "Retrieval quality and the frozen beta-scope coverage measure", "B", 2, 4, 4, (6, 9), ["BL-11", "BL-6.6", "BL-7", "M-DOC-COVERAGE", "L-REL-1", "L-ROUTE-1", "B-SEMCAL", "J-SEMANTIC"], depends=["02B"], decisions=["OD-COVERAGE", "OD-BUDGET"],
      scope="Calibrated relevance floor, language-aware routing, semantic calibration, and a separate frozen R1.0 beta-scope coverage measure reported beside the preserved historical gate (386 of 412, FAIL).",
      components="src/copilot/retrieval/ (adaptive, reranker, fusion); src/copilot/router; scripts/check_product_coverage_baseline.py; evaluations/product_coverage/; docs/capstone coverage records (read-only)", backend="Relevance-floor calibration; routing keyword tables per language; beta-scope coverage evaluator over a frozen case set", frontend="none",
      security="Historical gate results never rewritten; the new measure is never labelled as the original gate", acceptance="Beta-scope measure approved and reported; relevance floor calibrated with evidence; routing verified per language", tests="coverage evaluators on the frozen set; routing tests per language; consistency check that both measures are reported", pr="One PR plus documentation", dod="Both measures reported side by side"),
    # ---------------- Phase 03 Track C
    P("03A", "Admin navigation foundation (REQ-OWN-08)", "C", 3, 1, 1, (5, 7), ["REQ-OWN-08"], decisions=[],
      scope="Grouped, collapsible Admin sidebar, active highlighting, breadcrumbs, responsive and keyboard-accessible, permission-aware; Review and Diagnostics moved under /admin with redirects; removed from the global Candidate More menu; backend permissions unchanged.",
      components="frontend/components/admin/AdminShell.tsx; frontend/lib/admin/capabilities.ts (ADMIN_DESTINATIONS, 20 destinations); frontend/components/layout/nav-items.ts (INTERNAL_NAV); frontend/app/review/*; frontend/app/admin/*; tests/_admin_matrix.py; frontend/tests/fixtures/admin-role-permissions.json",
      backend="No permission change; if a diagnostics API is moved, keep the old route as a redirect and keep its require_permission guard", frontend="Group definitions, collapsible sidebar, breadcrumbs, quick navigation, /admin/review route group with redirects from /review, Candidate nav cleanup; the owner-scoped run details at /review/agent stay for Candidates",
      security="Hiding is not authorization: backend 403 tests for diagnostic routes remain; no Candidate access to platform-wide diagnostics", acceptance="REQ-OWN-08 N1 to N5", tests="admin-shell vitest; navigation Playwright (expand/collapse, keyboard, breadcrumbs, responsive); redirect tests; backend 403 tests; accessibility checks; existing admin matrix unchanged", pr="One PR (frontend plus redirects)", dod="All existing Admin routes reachable; permission-aware; no regression in the admin Playwright suites"),
    P("03B", "Admin Plans: Basic/Premium management (REQ-OWN-02)", "C", 3, 2, 3, (6, 9), ["REQ-OWN-02"], depends=[], decisions=["OD-PLAN-LIMITS"],
      scope="Draft plan editing from registered features, per-plan feature toggles and limits, clone/version, comparison, candidate-access preview, user and Workspace assignment, activate/retire, rollback, backend enforcement; no billing.",
      components="src/plans_repository.py; src/entitlements.py (REGISTRY); src/api/routes/admin_plans.py; frontend PlansView/PlanDetailView/PlanControl; src/application/plan_state.py", backend="Feature-and-limit editing on draft plan versions; comparison and preview endpoints; Workspace entitlement assignment; rollback; audit", frontend="Plan editor, comparison and preview views",
      security="Entitlements enforced server-side; privileged changes audited; billing gates stay False", acceptance="REQ-OWN-02 P1 to P8", tests="plan lifecycle; entitlement enforcement at the API boundary; preview-versus-actual parity; audit; rollback; Playwright", pr="Two PRs: backend; frontend", dod="Plans manageable without code; billing untouched"),
    P("03C", "Admin Users: complete user management (REQ-OWN-03)", "C", 3, 2, 3, (7, 10), ["REQ-OWN-03", "A-04"], depends=[], decisions=["OD-BULK-ACTIONS"],
      scope="Search, filter, sort, pagination; membership inspection; restricted bulk actions; communications; support and audit view; self-lockout and escalation protection; no private content.",
      components="src/admin_repository.py; src/api/routes/admin.py; frontend users views; role-change approval (src/admin_security)", backend="List/search/sort/pagination API; membership read model; bulk action framework limited to approved actions; resend of permitted account mail", frontend="User list and detail enhancements",
      security="Privileged actions audited and approval-gated; no CV/story/interview/conversation access", acceptance="REQ-OWN-03 U1 to U9", tests="list/search/pagination; lifecycle and session revocation; role-change approval; self-lockout; bulk guards; privacy sentinels; Playwright", pr="Two PRs", dod="Operational without code changes; sentinels pass"),
    P("03K", "Admin metric and report contract (interface package)", "C", 3, 1, 1, (2, 3), [], decisions=[],
      scope="A typed contract for Admin metrics, dimensions, dashboards and reports (extends src/reporting/definitions.py): metric id, source, numerator, denominator, period, coverage rule, missing-data behaviour; report definition schema; API response schemas and the matching frontend types; contract tests. Lets the dashboard backend (03D1), the report backend (03E1) and their UIs proceed in parallel instead of in a chain.",
      components="src/reporting/definitions.py; src/api/routes/admin_reports.py schemas; frontend/lib/admin/types.ts", backend="Contract schemas and a conformance test harness; no new metrics yet", frontend="Generated or hand-written TypeScript types for the contract",
      security="Contract forbids free-text SQL or column names by construction; aggregates only", acceptance="Contract merged with conformance tests that 03D1 and 03E1 must pass", tests="schema tests; a conformance suite run by both consumers; existing reporting tests unchanged", pr="One small PR", dod="Both consumers can start against the merged contract"),
    P("03D1", "Command Center metrics and AI operations read model (REQ-OWN-01, backend)", "C", 3, 1, 3, (5, 8), ["REQ-OWN-01"], depends=["03K"], decisions=[],
      scope="Real sourced metrics with period, numerator, denominator, coverage and missing-data states, and the AI operations read model over models, configuration, prompt versions, provider readiness, agent execution and evaluation.",
      components="src/reporting/; src/ai_admin/; src/application/admin_readiness.py; ai_usage_facts and operational_metric_events; src/api/routes/admin.py (home)", backend="Metric implementations against the 03K contract; dashboard and AI operations endpoints (prompt versions appear when 01B lands)", frontend="none (03D2)",
      security="Aggregates only; no candidate content; cohort suppression", acceptance="REQ-OWN-01 C1 to C5 backend half: every tile traceable to a query and denominator", tests="metric-source tests; missing-data tests; permission matrix; privacy sentinels", pr="One or two PRs", dod="Contract conformance suite passes; every metric traceable"),
    P("03D2", "Command Center and AI operations views (REQ-OWN-01, frontend)", "C", 3, 2, 4, (4, 6), [], depends=["03D1", "03A"], decisions=[],
      scope="Dashboard tiles and charts chosen by meaning, with period, numerator, denominator, coverage and missing-data state, and the AI operations view, inside the grouped Admin shell.",
      components="frontend CommandCenter.tsx, AIView.tsx; Admin shell (03A)", backend="none", frontend="Charts and views over the 03K contract types", security="No candidate content", acceptance="REQ-OWN-01 C1 to C5 frontend half; unavailable metrics render as unavailable, never zero", tests="vitest for chart and missing-data rendering; Playwright dashboard specs", pr="One PR", dod="Acceptance journeys pass in the browser", note="Closes REQ-OWN-01 together with 03D1; the requirement itself is assigned to 03D1."),
    P("03E1", "Reports registry, governed builder, saved configurations and exports (REQ-OWN-04, backend)", "C", 3, 1, 3, (6, 9), ["REQ-OWN-04"], depends=["03K"], decisions=["OD-REPORT-EXPORT"],
      scope="Prebuilt report registry, builder over registered metric and dimension ids only, saved configurations (one additive migration), exports, suppression, permissions.", components="src/reporting/; src/api/routes/admin_reports.py", backend="Report registry, builder, saved configuration table, export", frontend="none (03E2)",
      security="No arbitrary SQL; suppression; permission checks", acceptance="REQ-OWN-04 B1 to B5 backend half; builder cannot express an unregistered metric", tests="metric definitions; suppression; builder guard; permissions; exports", pr="Two PRs: registry and builder; saved configurations and exports", dod="Contract conformance suite passes"),
    P("03E2", "Reports catalogue, builder and export views (REQ-OWN-04, frontend)", "C", 3, 3, 5, (4, 7), [], depends=["03E1", "03A"], decisions=["OD-REPORT-EXPORT"],
      scope="Report catalogue, builder UI, charts, saved configuration management and export, in the Admin shell.", components="frontend reports views", backend="none", frontend="Catalogue, builder, charts, export", security="No candidate content; suppression displayed truthfully", acceptance="REQ-OWN-04 acceptance journeys pass in the browser", tests="vitest; Playwright report specs", pr="One or two PRs", dod="Builder UI cannot submit an unregistered metric", note="Closes REQ-OWN-04 together with 03E1; the requirement itself is assigned to 03E1."),
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
    P("04E", "Invitation-only registration (REQ-BETA-01)", "D", 4, 2, 2, (3, 5), ["REQ-BETA-01"], decisions=[], scope="Registration succeeds only with a valid invitation; revocable and audited; no open sign-up; no payment path.",
      components="src/application/auth_service.py; src/auth_repository.py; frontend/app/register; Admin users", backend="Invitation model/migration and validation at registration; Admin issue/revoke", frontend="Invitation field on registration; Admin invitation controls",
      security="Prevents uninvited access; tokens stored hashed, single-use, expiring", acceptance="REQ-BETA-01", tests="invitation gate API tests; uninvited-registration Playwright; audit", pr="One PR", dod="Uninvited registration refused server-side"),
    P("04F", "Browser dictation disclosure and verification", "D", 4, 3, 3, (2, 3), ["W12.4E-16", "AC-13/AC-23-A"], scope="Legal/privacy review of the browser dictation disclosure and a live browser STT correction-burden check (browser path only; server speech stays R1.4).",
      components="frontend DictationControl; src/speech/policy (read only)", backend="none", frontend="Copy adjustments after review", security="Disclosure accuracy; no audio stored", acceptance="Reviewed wording; measured correction burden recorded", tests="human review record; measurement run", pr="Small PR if wording changes", dod="Review recorded", human="Legal reviewer and test participants"),
    # ---------------- Phase 05 Track E
    P("05A", "Hosted topology and platform hardening", "E", 5, 1, 2, (8, 12), ["EX-12.1", "EX-12.2", "EX-12.3", "EX-12.4", "EX-12.5", "EX-12.6", "EX-12.14", "EX-12.15", "H-ENV", "H-CSRF", "H-MFA"], decisions=["OD-HOSTED"],
      scope="Create staging and production topology: TLS and HSTS with automatic certificates, same-site cookies, CORS allowlist, readiness gating, single migration step, CSP, documented single-replica limits, environment separation, a worker service and knowledge volumes (missing from the current staging compose), CSRF and step-up posture review.",
      components="deploy/Caddyfile, Dockerfile.api, Dockerfile.web, docker-compose.staging.yml (db, migrate, api, web, caddy only), deploy/scripts; src/api/main.py; docs/operations_deployment.md", backend="Config guards; worker entrypoint; env separation checks", frontend="CSP and cookie behaviour verification",
      security="Production fail-closed settings; secrets only in the managed store", acceptance="PG-01", tests="scripts/eval_hosting_readiness.py; hosted rehearsal checklist EX-12 #1 to #6, #14, #15", pr="Infrastructure PRs (compose/worker/volumes) plus a runbook PR", dod="Staging reachable over TLS from a clean checkout; checklist evidence recorded", note="DEPLOYMENT FREEZE: deploy/docker-compose.staging.yml must NOT be deployed as it stands (no worker, no knowledge or index volume, no ClamAV service). The first 05A PR completes the topology as code without deploying; deployment waits for OD-HOSTED and for that PR plus 02A."),
    P("05B", "Persistence, backup, restore and rollback drills", "E", 5, 3, 3, (6, 9), ["EX-12.7", "EX-12.8", "EX-12.9", "EX-12.10", "H-BACKUP", "PRIV-BACKUP", "H-PG-MULTI", "H-PG-QUERY", "H-PG-SECRETS", "R-96a", "R-96b"], depends=["05A", "02A", "02K"],
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
    P("06C", "Per-language AI behaviour: prompts, interview and feedback", "F", 6, 3, 3, (5, 8), ["REQ-LANG-03", "REQ-LANG-04", "D-LANG"], depends=["01B0", "06A"], scope="Policy and prompt behaviour per language; scoring invariance; localized policy sentences review.", components="src/copilot/rag/localized.py; src/prompts.py language directive; scoring code", backend="Fixes and invariance tests", frontend="none", security="No policy bypass by language", acceptance="LG-04, LG-05", tests="per-language policy suite; scoring invariance; blinded rating protocol", pr="One PR plus protocol", dod="Suites green per language"),
    P("06D", "Multilingual retrieval and cross-language attribution", "F", 6, 4, 4, (6, 9), ["REQ-LANG-06", "L-XLANG-1"], depends=["02B"], scope="Evaluate and fix multilingual retrieval, citation attribution and abstention.", components="src/copilot/retrieval; citation mapping; evaluators", backend="Evaluator and fixes", frontend="none", security="No invented translations of source claims", acceptance="LG-06", tests="multilingual retrieval evaluation with sample sizes", pr="One PR", dod="Report with limitations"),
    P("06E", "Per-language injection, security and privacy suites", "F", 6, 3, 3, (5, 8), ["REQ-LANG-08"], depends=["01A", "06A"], scope="Extend the injection corpus and privacy/PII suites to all seven languages including mixed-language input.", components="evaluations; src/security.py; privacy redaction", backend="Suites and fixes", frontend="none", security="Core", acceptance="LG-08", tests="per-language suites in CI", pr="One PR", dod="All languages pass or the language is not activated"),
    P("06F", "Native review and legal translation qualification", "F", 6, 2, 5, (2, 4), ["REQ-LANG-09", "REQ-LANG-10", "K-TRANS-LEGAL", "C-NATIVE"], depends=[], decisions=["OD-LANG-03", "OD-LANG-04"], scope="Coordinate native-speaker review and qualified legal translation per language; record sign-offs. Reviewer and counsel engagement starts immediately (it does not wait for the audit); each language is reviewed as its catalogue is frozen.", components="review protocol documents; version registry", backend="none", frontend="Text corrections", security="Legal accuracy", acceptance="LG-10, LG-11", tests="signed records", pr="Correction PRs", dod="Signed record per language", human="Seven native reviewers and legal qualifiers (calendar-bound)"),
    P("06G", "Independent human AI evaluation", "F", 6, 4, 5, (3, 5), ["C-CITE", "C-INT-HUMAN", "C-KB-HUMAN", "L-PRODQ", "BL-19", "L-AC24", "P2-01", "P2-02", "P2-03", "P2-04"], depends=["06C", "00A"], decisions=["OD-BUDGET", "OD-GATE-THRESHOLDS"], scope="Blinded human rating of interview questions, feedback and Mo answers per language; targeted human validation; pilot revalidation of sharing, provenance and score interpretation.",
      components="docs/capstone/p10/pilot2; src/model_quality harness; rating protocol", backend="Harness support only", frontend="none", security="Synthetic or consented data only", acceptance="PG-07", tests="rating records with sample size", pr="Protocol and harness PRs", dod="Ratings recorded with reviewers named", human="Independent reviewers and participants (calendar-bound)"),
    P("06H", "Language activation control: fail-closed enforcement of LG-01 to LG-14 before real-user activation", "F", 6, 2, 3, (4, 6), [], depends=["06A"], decisions=["OD-LANG-03", "OD-LANG-04"],
      scope="Server-side enforcement that a locale is offered to real users only when it has a COMPLETE, APPROVED qualification record: all fourteen gates PASS, each with an evidence artefact reference, a named human approver, an approval date and the release SHA, and no gate stale. In production a locale without such a record is neither offered nor accepted for new sessions (fail closed, including when no locale qualifies); staging and development keep the seven languages selectable but visibly labelled UNQUALIFIED for synthetic testing. The mechanism is code-defined (it cannot be flipped from Admin or the environment alone) and is testable now with synthetic readiness fixtures. REQ-LANG-13 is assigned to 06A; 06H completes its enforcement.",
      components="src/locales.py (ACTIVE_CANDIDATE_LOCALES, effective_locale: 06A); docs/production/execution/language_readiness.json (06A readiness record); GET /api/v1/capabilities; registration, onboarding, preferences, career chat, agent run and interview creation (the places 06A made reject a non-active locale); frontend language selectors and onboarding; scripts/eval_marketing_product_trust.py (claims gate)",
      backend="A pure activation resolver (reads a validated qualification record, never the network), the environment mode (enforced in production, labelled elsewhere; fails closed on an unknown or missing record), capabilities exposing the real-user locales and the activation mode, the same refusal at every entry point 06A guards, and a read-only per-language readiness view for Admin (metadata only)", frontend="Selectors offer only the capabilities' real-user locales in production and label unqualified locales in staging; a clear unavailable state when no locale is qualified",
      security="Fails closed; no Admin or environment toggle can activate a locale; qualification records need a named approver and evidence; no private data involved", acceptance="LG-13 enforcement: tests with synthetic fixtures prove a locale is enabled only with a complete approved record; production offers nothing for a locale with any gate not PASS, missing evidence, missing approver, stale evidence or SHA mismatch; an empty qualified set blocks real-user registration with a clear message instead of silently falling back; the claims gate rejects any production-qualified claim without the record; release acceptance PG-04 and PG-13 reference it",
      tests="resolver unit tests over synthetic readiness fixtures (complete, each single missing gate, NOT RUN, ENGINEERING DRAFT, no evidence, no approver, stale, SHA mismatch, unknown locale, empty set); API tests at each guarded entry point in production and staging modes; capabilities contract test; frontend vitest and Playwright for the labelled and unavailable states; claims-gate test; the 06A language boundary tests unchanged", pr="One PR stacked on 06A", dod="Production fails closed for every language today (none has an approved record); the synthetic complete record enables exactly its locale; no path activates a locale without the record", human="Named approvers (native reviewer and legal qualifier sign-offs feed the records)"),
    # ---------------- Phase 07 / 08
    P("07A", "Deferral inaccessibility and engineering hygiene", "E", 7, 5, 5, (5, 8), ["REQ-DEFER-01", "DEMO-04", "DEMO-05"], depends=["05A", "03A"], scope="Consolidated UI plus API tests proving each deferred feature is unreachable; audit async blocking and optional-dependency tests.", components="gate constants; routes; frontend entry points; CI", backend="Tests", frontend="Tests", security="Core safety rule 10", acceptance="PG-10", tests="inaccessibility suite per gated family", pr="One PR", dod="Suite in CI"),
    P("07B", "Live grounding and agent-policy validation", "A", 7, 4, 4, (4, 6), ["D-NOT-LIVE", "D-MISS-AMB", "D-MISS-INS", "D-MISS-PRAC", "D-MISS-PREP", "D-MISS-5TH", "D-POLB", "D-SRC-LIST", "D-CITE-PROXY", "DEMO-03"], depends=["01B", "01D"], decisions=["OD-BUDGET"],
      scope="Bounded live re-validation of the grounding policies and historical agent misses; investigate the zero RAGAS relevancy and recall scores; larger approved RAGAS run.", components="evaluations/p10e; scripts/eval_ragas.py; demo_live pattern", backend="Evaluator updates", frontend="none", security="Spend guard mandatory", acceptance="Policies validated live with recorded results", tests="live runs under budget; deterministic evaluators unchanged", pr="One PR plus evidence", dod="Results recorded with run identity"),
    P("07C", "Residual live verifications", "E", 7, 4, 4, (2, 3), ["J-OCR"], decisions=["OD-BUDGET"], scope="Live OCR quality sample.", components="src/documents/ocr.py", backend="none", frontend="none", security="Synthetic documents", acceptance="Sample recorded", tests="live sample", pr="Evidence PR", dod="Result recorded"),
    P("08A0", "Release evidence pipeline (continuous integration of evidence)", "E", 8, 1, 1, (3, 5), [], decisions=[],
      scope="Automate the collection of gate evidence from the first merged package onward: per-package acceptance results, CI links, SHA, the readiness tracker rows (PG-01 to PG-15, LG-01 to LG-14) and the reconciliation check, so the freeze assembles evidence that already exists instead of creating it at the end.",
      components="docs/production/execution/RELEASE_READINESS_TRACKER.md; scripts/production/; CI", backend="Evidence collector and tracker generator", frontend="none", security="No claims without evidence; PASS only with an artefact link", acceptance="Tracker rows update from CI artefacts; stale evidence is flagged", tests="tracker generator tests; reconciliation check", pr="One PR", dod="Evidence for a merged package appears in the tracker without manual copying"),
    P("08A", "Freeze and owner go/no-go", "E", 8, 5, 5, (2, 3), [], depends=["08A0", "07B", "07C", "04F", "00B", "07A", "06H", "06G", "05B", "05C", "05D", "05E", "03A", "03B", "03C", "03D2", "03E2", "04C", "04D", "04E", "02C", "02D", "02E", "06B", "06D", "06E", "06F"], decisions=["OD-RESOURCE"],
      scope="Freeze at one SHA, assemble the evidence for PG-01 to PG-15 and LG-01 to LG-14, run the reconciliation check, owner go/no-go.", components="docs/production; CI", backend="none", frontend="none", security="No bypass of mandatory gates", acceptance="PG-15", tests="full CI, reconciliation check, release rehearsal", pr="Release evidence PR", dod="Owner go/no-go recorded", human="Owner"),
]
BYID = {p["id"]: p for p in PACKAGES}

TIER_NAMES = {0: "Non-negotiable for any real-user beta (safety, privacy, hosting, knowledge, identity, language gates)", 1: "Reviewer corrections and operator safety", 2: "Owner core capabilities (candidate journeys, Story Bank, Workspaces, quality evidence)",
              3: "Admin 2.0 expansion beyond the existing Admin", 4: "Verification extras and proposals"}
TIERS = {"00A": 0, "01A": 0, "01D": 0, "02A": 0, "02B": 0, "02C": 0, "02D": 0, "04E": 0, "05A": 0, "05B": 0, "05C": 0, "05D": 0, "05E": 0, "06A": 0, "06E": 0, "06F": 0, "06H": 0, "07A": 0, "08A": 0,
         "01B": 1, "01C": 1, "04C": 1, "03A": 1,
         "04A": 2, "04B": 2, "04D": 2, "06B": 2, "06C": 2, "06D": 2, "03C": 2, "02E": 2, "06G": 2,
         "01B0": 1, "08A0": 0, "03B": 3, "03K": 3, "03D1": 3, "03D2": 3, "03E1": 3, "03E2": 3, "02K": 0,
         "07B": 4, "07C": 4, "04F": 4, "00B": 4}
# Early parallel workstream (owner correction): deployment topology and Knowledge persistence are long poles that need a decision, a topology fix and drills,
# so they start in the first implementation wave alongside Track A, with the highest staffing priority.
EARLY_PARALLEL = ["02A", "05A", "05E"]

BRIEFS = {
    "01A": dict(title="Prompt-injection corpus, risk score and quarantine (REVIEW-01 part 1)", pr1=["Add evaluations/injection/ with a labelled corpus built from evaluations/jailbreak_test_results.csv (30 rows: categories, expected outcome, location); extend with indirect, multilingual, encoded and retrieved-document cases; freeze a held-out split with a recorded hash.",
        "Add scripts/eval_injection_corpus.py: runs detect_injection and the RAG screen over the corpus, reports detection and benign false-positive rates overall and per language/category, writes only to a temp directory unless --write, and exits non-zero below the thresholds from OD-GATE-THRESHOLDS (no threshold is assumed: until approved the script reports and does not gate).",
        "Add an injection_risk field (float 0 to 1 plus indicator names) to RetrievalResult (src/copilot/models.py); compute it in src/copilot/security/rag_guard.py screen_results using the existing indicator weights; quarantine or exclude chunks above the threshold before context construction in src/copilot/service.py and the agent retrieval tool.",
        "Retain inspect_output and the output guard in CopilotService.answer(); add a regression asserting both still run.", "Wire the CI step into .github/workflows/ci.yml (evaluator job) and the shard plan."],
        pr2=[], files="src/security.py; src/copilot/security/{injection,rag_guard,output_guard}.py; src/copilot/models.py; src/copilot/service.py; evaluations/injection/ (new); scripts/eval_injection_corpus.py (new); tests/test_injection_*.py (new)",
        out_of_scope="No change to src/agent/policies.py, registry.py or nodes.py (the tool-call authorization is package 01D, sequenced after 01B); no new tools; no change to grounding policy semantics; no live model calls (the corpus run is offline); no threshold invented", risks="False positives on legitimate job descriptions; multilingual evasion; thresholds undecided",
        verification="eval script report committed as evidence; CI gate once thresholds are approved; existing eval_agent, grounding and prompt-injection suites unchanged and green; REVIEW-01 R1, R2, R3, R6"),
    "01D": dict(title="Tool-call authorization layer (REVIEW-01 part 2)", pr1=["After 01B has merged, add an authorization step inside ToolRegistry.validate_and_run (src/agent/registry.py): verify the authenticated user, the run's declared goal and consent state, the tool's permission, and an argument allow-list; refuse and record a safe event otherwise.",
        "Negative tests: retrieved text instructing a side-effecting tool cannot cause it to run; user A's run cannot read user B's evidence through any tool; invalid argument shapes are refused before side effects.", "Assert the tool set is unchanged."],
        pr2=[], files="src/agent/registry.py; src/agent/nodes.py; src/agent/state.py; tests/test_tool_authorization_*.py (new)", out_of_scope="No new tools; no prompt wording change", risks="Over-blocking legitimate tool calls (mitigated by the 56 deterministic tool-selection cases)",
        verification="negative tests; existing eval_agent and tool-selection cases green; closes REVIEW-01 together with 01A; must merge after 01B and before 01C"),
    "06H": dict(title="Language activation control (LG-01 to LG-14, fail closed)", pr1=["Define the qualification record schema (per locale: fourteen gates, each PASS with an evidence artefact reference, named human approver, approval date, release SHA; stale-evidence rule) and validate the existing docs/production/execution/language_readiness.json against it (today every locale is incomplete).",
        "Add the pure activation resolver and environment mode in src/locales.py (or a small src/language_activation.py): enforced in staging-as-production and production (a locale without a complete approved record is not offered and is refused for new sessions, including when the qualified set is empty), labelled-unqualified in staging for synthetic testing, development unchanged; code-defined, no Admin or environment toggle can override it.",
        "Wire it into capabilities and every entry point 06A guards (registration, preferences, onboarding, career chat, agent run, interview create); frontend selectors offer the real-user locales and show a clear unavailable state when none is qualified.", "Tests with synthetic readiness fixtures only (never mark a real language PASS): complete record enables exactly its locale; each single defect disables it; unknown locale and empty set fail closed; claims gate rejects an unsupported qualified claim."],
        pr2=[], files="src/locales.py or src/language_activation.py (new); src/api (capabilities and the guarded entry points); docs/production/execution/language_readiness.json (schema only, no gate marked PASS); frontend language selectors and tests; tests/test_language_activation_06h.py (new)",
        out_of_scope="No language is qualified or activated by this package; no change to the seven selectable target languages; no weakening of 06A", risks="An empty qualified set blocks real-user registration in production until the first locale is qualified (intended: the owner decided a failed gate prevents activation)",
        verification="synthetic-fixture tests under both venvs; 06A tests unchanged; production mode refuses all seven languages today"),
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
    "03A": dict(title="Admin navigation foundation (REQ-OWN-08)", pr1=["Define six nav groups over the 20 existing destinations in frontend/lib/admin/capabilities.ts (grouping approved by the owner at the Phase 00 sign-off): Command Center (Overview); Customers and Workspaces (Users, Workspaces, Support, Privacy); Products and Commercial (Plans, Billing); AI and Knowledge (AI and models, Knowledge, Speech, Provider status, Review and Diagnostics); Insights and Operations (Reports, Jobs, Integrations); Governance and Settings (Security, Audit, Legal, Configuration, Feature flags).",
        "Replace the flat list in AdminShell.tsx with a grouped, collapsible, keyboard-accessible sidebar with active highlighting, breadcrumbs, responsive behaviour and permission-aware visibility; optional quick navigation.",
        "Move platform-wide Review and Diagnostics under /admin (for example /admin/review) with redirects from /review; remove the Review entry from the global Candidate More menu (INTERNAL_NAV in frontend/components/layout/nav-items.ts); keep the owner-scoped /review/agent run details for Candidates.",
        "Update tests/_admin_matrix.py DOMAINS and regenerate frontend/tests/fixtures/admin-role-permissions.json only if a route or permission changes (none is expected)."],
        pr2=[], files="frontend/components/admin/AdminShell.tsx; frontend/lib/admin/capabilities.ts; frontend/components/layout/nav-items.ts; frontend/app/admin/*; frontend/app/review/*; frontend/tests/admin-shell-w10-1.test.tsx; frontend/e2e/admin*.spec.ts",
        out_of_scope="No new Admin features, permissions or routes beyond the relocation and redirects; backend authorization unchanged", risks="Broken deep links (mitigated by redirects); role-visibility regressions", verification="vitest for grouping and visibility per role; Playwright for expand/collapse, keyboard, breadcrumbs, responsive and redirects; backend 403 tests for diagnostics remain green; accessibility checks"),
}

# ---------------------------------------------------------------- measured status and throughput (first engineering wave; updated by hand as evidence arrives)
PACKAGE_STATUS = {   # id: (state, branch, head SHA, verification evidence). GitHub CI is reported separately in the integration dashboard; "no PR" means no CI could run
    "05A": ("BRANCH PUSHED, VERIFIED OFFLINE", "feat/05a-staging-topology", "0a7d6fb", "114 passed/1 skipped under both venvs; ruff; hosting readiness PASS; nothing deployed"),
    "01A": ("BRANCH PUSHED, VERIFIED OFFLINE", "feat/01a-injection-corpus", "6b2dbc2", "293 passed under both venvs; eval_agent PASS; held-out detection 54.5% (report only)"),
    "02K": ("BRANCH PUSHED, VERIFIED OFFLINE", "feat/02k-knowledge-contract", "f5eb3dc", "125 passed under both venvs after 1 rework round"),
    "01B0": ("BRANCH PUSHED, VERIFIED OFFLINE", "feat/01b0-prompt-contract", "6f6d383", "462 passed under both venvs"),
    "03K": ("BRANCH PUSHED, VERIFIED OFFLINE", "feat/03k-admin-metric-contract", "8afe350", "183 passed under both venvs; tsc, lint, vitest 28"),
    "03A": ("BRANCH PUSHED, VERIFIED OFFLINE", "feat/03a-admin-navigation", "7a6f484", "vitest 1114, Playwright 89, pytest 107, tsc, lint, ruff"),
    "06A": ("BRANCH PUSHED, CORRECTIONS IN PROGRESS", "feat/06a-locale-boundaries", "f7b2e03", "full Python suite 5172 passed on the repo venv and 5170 on the fresh venv; vitest 1087; affected Playwright; documentation corrections pending"),
    "01B": ("IN PROGRESS (stacked on 01B0)", "feat/01b-versioned-prompts", "", "not yet reported"),
    "02A": ("IN PROGRESS (stacked on 02K)", "feat/02a-knowledge-persistence", "", "not yet reported"),
}
THROUGHPUT = [   # (package, estimate low-high days, authoring wall-clock minutes, rework rounds, review latency, CI duration)
    ("05A", "8-12", 11, 0, "no PR yet", "no PR yet"), ("01A", "5-8", 24, 0, "no PR yet", "no PR yet"), ("02K", "2-3", 32, 1, "no PR yet", "no PR yet"), ("01B0", "2-3", 24, 0, "no PR yet", "no PR yet"),
    ("03K", "2-3", 34, 0, "no PR yet", "no PR yet"), ("03A", "5-7", 29, 0, "no PR yet", "no PR yet"), ("06A", "4-6", 43, 0, "no PR yet", "no PR yet"),
]


# ---------------------------------------------------------------- resource-constrained schedule (the weeks of each package are COMPUTED, not hand-assigned)

# Calendar-bound human and legal lead times: working days of ELAPSED time that engineering cannot compress. They are ASSUMPTIONS to be replaced by real quotes from the named
# reviewers, counsel and licensors; they are not owner decisions and not measurements.
ELAPSED_FLOOR = {"02D": 15, "05E": 15, "06F": 20, "06G": 10, "04F": 5}
FIRST_WAVE = ["05A", "01A", "02A", "01B0", "01B", "03A", "06A", "02K", "03K", "05E", "06F", "08A0"]     # owner-authorised first wave (plus the two small interface-contract packages that unblock parallel work)
FIXED_WEEKS = {"00A": (0, 1)}                                                # owner-led governance, not an engineering stream
PAR_EFFICIENCY = 0.85        # ASSUMPTION: each additional stream on the same package delivers 85% of a first stream (coordination and merge overhead)
MAX_STREAMS = {**{k: 4 for k in ("06B", "06C", "06D", "06E")}, **{k: 2 for k in ("04A", "04B", "04C", "03B", "03C", "03D1", "03E1", "03D2", "03E2", "02A", "05A", "01A", "02B", "02E", "04D", "05B", "05C", "07A")}, "01B": 3}     # language work parallelises by language
PROFILES = {                                                                 # parallel engineering streams available in week 1, 2, 3 and after (the last value repeats)
    "A constant 12": [12], "B ramp 12, 12, 16": [12, 12, 16], "C ramp 12, 16, 20": [12, 16, 20], "D ramp 12, 18, 24": [12, 18, 24], "E ramp 12, 24, 32": [12, 24, 32],
}
FREEZE_DAY = 25            # end of W5 (27 November) in working days from the start of W1 (26 October)
STEP = 0.25


def _rank() -> dict[str, float]:
    """Longest remaining dependency chain (by maximum effort, respecting elapsed floors) from each package to the end: the scheduling priority."""
    succ: dict[str, list[str]] = {p["id"]: [] for p in PACKAGES}
    for p in PACKAGES:
        for d in p["depends"]:
            succ[d].append(p["id"])
    memo: dict[str, float] = {}

    def r(n):
        if n not in memo:
            own = max(BYID[n]["effort"][1], ELAPSED_FLOOR.get(n, 0))
            memo[n] = own + max((r(x) for x in succ[n]), default=0.0)
        return memo[n]

    return {p["id"]: r(p["id"]) for p in PACKAGES}


def simulate(profile: list[int], which: int = 1, scale: float = 1.0) -> dict[str, tuple[float, float, int]]:
    """List-schedule every package onto the available streams. A stream delivers UTILISATION productive days per working day; a package of 10 or more days may use two streams."""
    rank = _rank()
    pk = {p["id"]: dict(rem=float(p["effort"][which]) * scale, start=None, fin=None, streams=0, floor=ELAPSED_FLOOR.get(p["id"], 0)) for p in PACKAGES}
    for k in FIXED_WEEKS:
        pk.pop(k)
    order = sorted(pk, key=lambda i: ((FIRST_WAVE.index(i) if i in FIRST_WAVE else 99), -rank[i], i))
    t = 0.0
    while any(v["fin"] is None for v in pk.values()):
        cap = profile[min(int(t // 5), len(profile) - 1)]
        used = sum(v["streams"] for v in pk.values() if v["start"] is not None and v["fin"] is None)
        for i in order:
            v = pk[i]
            if v["start"] is None and all(d in FIXED_WEEKS or (pk[d]["fin"] is not None and pk[d]["fin"] <= t + 1e-9) for d in BYID[i]["depends"]):
                want = MAX_STREAMS.get(i, 2 if BYID[i]["effort"][which] >= 10 else 1)
                give = min(want, cap - used)
                if give >= 1:
                    v.update(start=t, streams=give)
                    used += give
        for i, v in pk.items():
            if v["start"] is not None and v["fin"] is None:
                v["rem"] -= (1 + (v["streams"] - 1) * PAR_EFFICIENCY) * UTILISATION * STEP
                if v["rem"] <= 1e-9 and t + STEP - v["start"] >= v["floor"] - 1e-9:
                    v["fin"] = t + STEP
        t += STEP
        if t > 400:
            raise RuntimeError("schedule did not converge")
    return {i: (v["start"], v["fin"], v["streams"]) for i, v in pk.items()}


def date_of(working_day: float) -> str:
    """Calendar date (Mon-Fri, no public holidays) for a working-day offset from Monday 26 October 2026; 0 is the start of that day."""
    import datetime as dt

    d = dt.date(2026, 10, 26)
    n = int(working_day + 1e-9)
    while n > 0:
        d += dt.timedelta(days=1)
        if d.weekday() < 5:
            n -= 1
    return d.strftime("%a %d %b %Y")


def completion(profile: list[int], which: int = 1, scale: float = 1.0) -> float:
    return max(f for _, f, _ in simulate(profile, which, scale).values())


def recommended_profile() -> tuple[str, list[int]]:
    """The smallest profile whose maximum-estimate completion meets the freeze; if none does, the smallest profile within one working day of the best achievable completion
    (more streams beyond that only add cost), and the report says the date moves."""
    for name, prof in PROFILES.items():
        if completion(prof, 1) <= FREEZE_DAY + 1e-9:
            return name, prof
    best = min(completion(prof, 1) for prof in PROFILES.values())
    for name, prof in PROFILES.items():
        if completion(prof, 1) <= best + 1.0:
            return name, prof
    return list(PROFILES.items())[-1]


def apply_schedule() -> None:
    name, prof = recommended_profile()
    plan = simulate(prof, 1)
    for p in PACKAGES:
        if p["id"] in FIXED_WEEKS:
            p["start"], p["end"] = FIXED_WEEKS[p["id"]]
        else:
            st, fin, _ = plan[p["id"]]
            p["start"], p["end"] = int(st // 5) + 1, int((fin - 1e-9) // 5) + 1


def peak_streams(profile: list[int], which: int = 1) -> int:
    plan = simulate(profile, which)
    ev = []
    for i, (st, fin, n) in plan.items():
        ev += [(st, n), (fin, -n)]
    cur = peak = 0
    for _, d in sorted(ev, key=lambda e: (e[0], e[1])):
        cur += d
        peak = max(peak, cur)
    return peak


apply_schedule()


# ---------------------------------------------------------------- staffing model
ROLES = {
    "TIL": "Technical integration lead (owns interface contracts, merge order, CI health, integration branches; reviews every cross-track PR)",
    "AIE": "AI and security engineer (injection defence, prompts, tool authorization, retrieval and embeddings quality)",
    "BE": "Backend and data engineer (APIs, persistence, knowledge lifecycle, reporting, migrations)",
    "FE": "Frontend engineer (Admin and Candidate UI, accessibility, i18n)",
    "DEVOPS": "DevOps and reliability engineer (topology, hosting, backup and restore, monitoring, scanner deployment)",
    "QA": "QA and test-automation engineer (journeys, contract and integration tests, evidence)",
    "LOC": "Localisation engineer (seven-language audit, per-language fixes, reviewer coordination)",
    "PO": "Product Owner (decisions, approvals, merge authority)",
}
ROLE_SPLIT = {
    "00A": {"PO": 1}, "00B": {"TIL": 1}, "01A": {"AIE": 1}, "01B0": {"AIE": 1}, "01B": {"AIE": 1}, "01D": {"AIE": 1}, "01C": {"AIE": 1}, "02K": {"BE": 1}, "02A": {"BE": .7, "DEVOPS": .3},
    "02B": {"BE": .7, "AIE": .3}, "02C": {"DEVOPS": .5, "BE": .5}, "02D": {"BE": 1}, "02E": {"AIE": .6, "QA": .4}, "03A": {"FE": 1}, "03K": {"BE": .5, "FE": .5}, "03B": {"BE": .5, "FE": .5},
    "03C": {"BE": .5, "FE": .5}, "03D1": {"BE": 1}, "03D2": {"FE": 1}, "03E1": {"BE": 1}, "03E2": {"FE": 1}, "04A": {"BE": .5, "FE": .5}, "04B": {"BE": .5, "FE": .5}, "04C": {"BE": .5, "FE": .3, "QA": .2},
    "04D": {"QA": .7, "FE": .3}, "04E": {"BE": .7, "FE": .3}, "04F": {"FE": 1}, "05A": {"DEVOPS": 1}, "05B": {"DEVOPS": 1}, "05C": {"DEVOPS": .5, "BE": .5}, "05D": {"DEVOPS": .5, "BE": .5},
    "05E": {"BE": 1}, "06A": {"LOC": .6, "FE": .4}, "06B": {"QA": .5, "LOC": .5}, "06C": {"AIE": .5, "LOC": .5}, "06D": {"AIE": .6, "QA": .4}, "06E": {"AIE": .6, "QA": .4}, "06F": {"LOC": 1},
    "06G": {"QA": 1}, "06H": {"BE": .5, "FE": .2, "QA": .3}, "07A": {"QA": 1}, "07B": {"AIE": 1}, "07C": {"QA": 1}, "08A0": {"TIL": .5, "QA": .5}, "08A": {"TIL": 1},
}
EXTERNAL = [
    ("Native-language reviewers (one per language, seven)", "Interface text, Mo samples, interview questions and feedback, legal text", "LG-11", "unnamed (OD-LANG-03)", f"{ELAPSED_FLOOR['06F']} working days elapsed (assumed)"),
    ("Legal counsel and qualified legal translators", "Privacy, Terms, AI-transparency in each offered language; provider data handling; licensing of source content", "LG-10, PG-04, 02D", "unnamed (OD-LANG-04)", f"{ELAPSED_FLOOR['05E']} working days elapsed (assumed)"),
    ("Independent human AI evaluators (per language) and a rating lead", "Blinded rating of interview questions, feedback and Mo answers; pilot revalidation", "PG-07, 06G", "unnamed (00A reviewers A, B, C)", f"{ELAPSED_FLOOR['06G']} working days after a frozen build (assumed)"),
    ("Licensing and source-qualification reviewer", "Licence, authority and coverage qualification of sources per approved market", "02D, REQ-COV-02", "unnamed", f"{ELAPSED_FLOOR['02D']} working days elapsed (assumed)"),
    ("Independent security reviewer or penetration tester (part time)", "Review of injection defence, tool authorization, hosting hardening before real users", "PG-03, PG-01", "unnamed", "5 to 10 working days late in the programme (assumed)"),
]


def _pr_count(text: str) -> int:
    t = text.lower()
    for word, n in (("three", 3), ("two", 2), ("one", 1)):
        if t.startswith(word) or f" {word} pr" in t or f"{word} prs" in t:
            return n
    return 1


def role_demand() -> dict[str, tuple[float, float]]:
    out: dict[str, list[float]] = {r: [0.0, 0.0] for r in ROLES}
    for p in PACKAGES:
        for r, w in ROLE_SPLIT[p["id"]].items():
            out[r][0] += w * p["effort"][0]
            out[r][1] += w * p["effort"][1]
    return {r: (v[0], v[1]) for r, v in out.items()}


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


def critical_path_subset(ids: set[str], which: int) -> tuple[list[str], float]:
    """Longest dependency chain by effort inside a subset of packages (a dependency outside the subset is treated as already satisfied)."""
    best: dict[str, tuple[float, list[str]]] = {}
    for n in topo_order():
        if n not in ids:
            continue
        prev = max((best[d] for d in BYID[n]["depends"] if d in best), default=(0.0, []), key=lambda t: t[0])
        best[n] = (prev[0] + BYID[n]["effort"][which], prev[1] + [n])
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
        if not (0 <= p["start"] <= p["end"] <= 12):
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
    for p in PACKAGES:
        rs = ROLE_SPLIT.get(p["id"])
        if not rs or abs(sum(rs.values()) - 1) > 1e-9 or any(r not in ROLES for r in rs):
            errs.append(f"{p['id']}: invalid role split")
    for p in PACKAGES:
        if p["id"] not in TIERS:
            errs.append(f"{p['id']}: no scope tier")
    for k in TIERS:
        if k not in BYID:
            errs.append(f"tier entry for unknown package {k}")
    for k in EARLY_PARALLEL:
        if k not in BYID or BYID[k]["start"] > 1:
            errs.append(f"early-parallel package {k} must start in W1 or earlier")
    # shared-file order for the agent policy and tool-execution path: 01B before 01D, 01D before 01C
    if not ("01B" in BYID["01D"]["depends"] and "01B" in BYID["01C"]["depends"] and "01D" in BYID["01C"]["depends"]):
        errs.append("agent-policy shared-file order must be 01B, then 01D, then 01C")
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
         "## Packages", "", "| ID | Package | Track | Phase | Tier | Weeks | Effort (days) | Depends on | Open decisions | R1.0 items | Human/calendar-bound |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for p in PACKAGES:
        L.append(f"| {p['id']} | {p['name']}{' (early parallel)' if p['id'] in EARLY_PARALLEL else ''} | {p['track']} | {p['phase']} | T{TIERS[p['id']]} | {WEEKS[p['start']].split(' ')[0]}-{WEEKS[p['end']].split(' ')[0]} | {p['effort'][0]}-{p['effort'][1]} | {', '.join(p['depends']) or 'none'} | {', '.join(p['decisions']) or 'none'} | {len(p['items'])} | {p['human'] or 'no'} |")
    L += ["", "Scope tiers: " + "; ".join(f"T{k} = {v}" for k, v in TIER_NAMES.items()) + ". Early-parallel packages (deployment topology and Knowledge persistence, highest staffing priority, start in the first implementation wave): " + ", ".join(EARLY_PARALLEL) + ".", "",
          f"Total effort: {t['min_days']} to {t['max_days']} engineering days. Critical path (longest dependency chain): {t['cp_min'][1]:.0f} to {t['cp_max'][1]:.0f} days (see `DEPENDENCY_GRAPH.md`).", "", "## Package detail", ""]
    for p in PACKAGES:
        st = PACKAGE_STATUS.get(p["id"])
        L += [f"### {p['id']} {p['name']}", "", f"- **Status:** {st[0]} ({st[1]} {st[2] or 'no SHA yet'}; {st[3]})" if st else "- **Status:** NOT STARTED", f"- **Scope tier:** T{TIERS[p['id']]} ({TIER_NAMES[TIERS[p['id']]]})" + ("; **early parallel workstream**" if p["id"] in EARLY_PARALLEL else ""), f"- **Track / phase / weeks:** {p['track']} ({TRACKS[p['track']]}) / {p['phase']} / {WEEKS[p['start']]} to {WEEKS[p['end']]}", f"- **Scope:** {p['scope']}", f"- **Dependencies:** {', '.join(p['depends']) or 'none'}; **owner decisions:** {', '.join(p['decisions']) or 'none'}",
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
          "| src/agent/policies.py and the tool-execution path (registry.py, nodes.py) | 01B, 01D, 01C (01A touches none of them; 04C reads events) | 01B, then 01D (tool-call authorization, the overlapping part of REVIEW-01), then 01C; 01A is independent and runs first |", "| src/prompts.py, src/prompt_registry.py, src/config_versions.py | 01B, 06C | 01B before 06C |",
          "| src/copilot/security/ and src/copilot/models.py (RetrievalResult) | 01A, 02B, 06D, 06E | 01A first |", "| src/knowledge_admin/ and src/copilot/embeddings.py, retrieval/ | 02A, 02B, 02C, 02D, 02E | 02A, then 02B and 02C, then 02D and 02E |",
          "| frontend/components/admin/AdminShell.tsx and frontend/lib/admin/capabilities.ts | 03A, 03B, 03C, 03D, 03E | 03A first; the rest rebase on it |", "| frontend/components/layout/nav-items.ts | 03A only | single owner |", "| tests/_admin_matrix.py and the admin role fixture | 03A to 03E | regenerate only when a permission or route changes |",
          "| deploy/docker-compose.staging.yml, Dockerfiles, deploy/scripts | 02A (worker, volumes), 02C (clamd), 05A, 05B | 05A owns the file; 02A and 02C supply fragments |", "| Alembic migrations (head 0039_speech_governance) | 03E, 04A, 04B, 04E (new tables) | one migration per PR, sequential heads, never two heads |",
          "| src/application/agent_service.py and Mo UI | 04C, 04D | 04C then 04D |", "| i18n catalogues (frontend/lib/i18n/messages) | all frontend packages | add keys to all locales in the same PR (existing rule) |", "",
          "## External gates (not engineering dependencies)", "", "- Owner decisions still open: OD-RESOURCE, OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS, OD-EMBED, OD-PLAN-LIMITS, OD-BULK-ACTIONS, OD-REPORT-EXPORT, OD-WS-TRANSFER, OD-LANG-02, OD-LANG-03, OD-LANG-04, OD-COVERAGE, OD-US-CONTENT, OD-RECLASS (resolved at the Phase 00 sign-off: OD-SCOPE-01 = S1, OD-ADMIN-NAV, OD-INVITE, OD-MALWARE).",
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
          "| W0 21-25 Oct | PR #212 merged by the owner; people named; first-wave decisions made | OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS and OD-RESOURCE answered (OD-SCOPE-01, OD-ADMIN-NAV, OD-INVITE and OD-MALWARE are already resolved); integration lead, DevOps lead and QA lead named; reviewers A, B, C appointed (00A) |",
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
    L += ["", "## Early parallel workstream: deployment topology and Knowledge persistence", "", "02A (Knowledge persistence, environment identity, restore), 05A (hosted topology) and 05E (privacy and legal readiness, calendar-bound) are long poles: they need an owner decision, a topology fix, repeatable drills and human lead time, and nothing else can be proven on a hosted stack without them. They start in W1 alongside Track A with the highest staffing priority and are tracked as a separate early workstream. **The existing `deploy/docker-compose.staging.yml` must not be deployed as it stands** (it has no worker, no knowledge or index volume and no ClamAV service); the first 05A PR completes the topology as code without deploying it.", ""]
    L += tier_section()
    L += measured_section()
    L += ["", "See `PHASE_00_EXIT_REPORT.md` for the Phase 00 assessment and `STAFFING_AND_CRITICAL_PATH_PLAN.md` for the S1 staffing plan.", ""]
    return "\n".join(L)


def measured_section() -> list[str]:
    rec = recommended_profile()
    L = ["", "## Measured first-wave throughput and what it does and does not say", "", "| Package | Estimate (days) | Authoring wall-clock (minutes) | Rework rounds | Review latency | GitHub CI duration |", "|---|---|---|---|---|---|"]
    for pk, est, mins, rw, rev, ci in THROUGHPUT:
        L.append(f"| {pk} | {est} | {mins} | {rw} | {rev} | {ci} |")
    tot = sum(m for _, _, m, _, _, _ in THROUGHPUT)
    L += ["", f"Seven first-wave packages were authored in {tot} agent-minutes in total (each agent ran in parallel; roughly 10 to 45 minutes per package, including about 15 minutes lost to the shared interpreter fault), against estimates of 2 to 12 engineering days each. **This measures authoring of contract, scaffolding and test-writing work only.** It excludes human review, GitHub CI (no PR exists, so none ran), integration, live validation, rework after review, native and legal review and every calendar-bound step, and the first wave was deliberately the smallest, best-bounded packages. It is NOT evidence about the heavier packages (02A, 02B, 03D1, 03E1, 04A to 04D, 05B to 05D) and no estimate has been changed because of it.", "",
          "Sensitivity of the full-scope completion date to the true effort (profile '" + rec[0] + "', high estimate scaled; a sensitivity table, not a forecast):", "", "| Effort relative to the estimate | Completes | Binding constraint |", "|---|---|---|"]
    for scale in (1.0, 0.5, 0.25, 0.1):
        c = completion(rec[1], 1, scale)
        L.append(f"| {int(scale * 100)}% | day {c:.0f}, {date_of(c)} | {'engineering chain' if scale >= 0.5 else 'calendar-bound human and legal lead times (assumed), then review capacity'} |")
    L += ["", "If engineering effort proves much smaller than estimated, the date stops being engineering-bound and becomes bound by the assumed human lead times (native review, legal qualification, licensing, independent evaluation) and by review capacity for roughly 60 pull requests. That is why the first-wave PRs need real reviewers and real CI evidence before the forecast is changed.", ""]
    return L


def tier_totals() -> list[tuple[int, int, int, int, int]]:
    out, lo, hi = [], 0, 0
    for k in sorted(TIER_NAMES):
        ps = [p for p in PACKAGES if TIERS[p["id"]] == k]
        lo += sum(p["effort"][0] for p in ps)
        hi += sum(p["effort"][1] for p in ps)
        out.append((k, len(ps), sum(p["effort"][0] for p in ps), sum(p["effort"][1] for p in ps), lo, hi))
    return out


def strategy_sets() -> dict[str, tuple[str, set[str]]]:
    allp = {p["id"] for p in PACKAGES}
    t0, t1, t2 = ({k for k, v in TIERS.items() if v == n} for n in (0, 1, 2))
    return {
        "S1 Full R1.0 scope (OWNER-SELECTED)": ("Every package (tiers T0 to T4)", allp),
        "S2 Restricted free private beta (REJECTED)": ("Tiers T0 to T2; Admin 2.0 expansion (03B, 03D, 03E) to R1.2; verification extras (07B, 07C, 04F, 00B) as follow-ups", t0 | t1 | t2),
        "S3 Minimum safe beta (REJECTED)": ("Tiers T0 and T1 plus candidate journey reliability (04D); Story Bank and Workspaces completion (04A, 04B), Admin user management (03C), retrieval calibration (02E), per-language AI and journey work beyond the activation gates (06B, 06C, 06D) and independent human evaluation (06G) are limited to what the activation gates strictly require or move to R1.2; this moves owner-requested R1.0 items out of R1.0 and needs explicit owner approval", t0 | t1 | {"04D"}),
    }


def tier_section() -> list[str]:
    t = totals()
    per = t["per_stream_productive_days"]
    L = ["## Scope tiers and the strategies considered for OD-SCOPE-01 (the owner SELECTED S1, the full scope; S2 and S3 were REJECTED as release plans and are kept only as capacity analysis)", "",
         "| Tier | Meaning | Packages | Effort (days) | Cumulative effort (days) | Streams for the cumulative total |", "|---|---|---|---|---|---|"]
    for k, n, lo, hi, clo, chi in tier_totals():
        L.append(f"| T{k} | {TIER_NAMES[k]} | {n} | {lo}-{hi} | {clo}-{chi} | {clo / per:.1f}-{chi / per:.1f} |")
    t012 = [r for r in tier_totals() if r[0] == 2][0]
    L += ["", f"**Rejected alternative S2 (restricted free private beta), kept for information:** deliver tiers T0 to T2 ({t012[4]} to {t012[5]} days, {t012[4] / per:.1f} to {t012[5] / per:.1f} streams) and defer tier T3 (Admin 2.0 expansion) to R1.2 and tier T4 (verification extras) to follow-up, with these restrictions, every one an owner decision still to be made:", "",
          "1. A small invitation-only cohort capped by the owner (size is an owner decision), limiting support, abuse and AI-cost exposure.",
          "2. Languages and markets are activated only where their gates pass at the freeze; expect fewer than seven languages and one or two qualified EU markets at launch (a failed mandatory gate prevents activation, as the owner decided). The others stay hidden and documented.",
          "3. Candidate core only: Mo, Practice, Story Bank, Workspaces with VIEW-only sharing, History, Progress, privacy controls.",
          "4. Safety, privacy, hosting, knowledge and identity gates are unchanged (tier T0); reviewer corrections REVIEW-01 to REVIEW-05 stay in scope (T0 and T1).",
          "5. Admin: owner-operated with the new navigation and user management; the existing Command Center, plan assignment and six aggregate reports stay as built; dashboards, the plan editor, comparison and preview, and the report builder move to R1.2.",
          "6. No live billing; Basic and Premium as free beta tiers.", "7. Live re-validation extras (07B, 07C) and the dictation review (04F) are follow-ups; the deterministic evaluators still run.", "",
          "**Owner decision (2026-10-21): S1, the full originally agreed R1.0 scope, is selected; S2 and S3 are rejected as November release plans.** The restrictions listed above are NOT in force: no R1.0 product requirement is removed, downgraded or postponed to meet a delivery target. See `STAFFING_AND_CRITICAL_PATH_PLAN.md` for the staffing and critical-path plan for S1.", "", "## Capacity analysis (information only)", "", "Which cumulative tiers fit a given number of parallel streams in the W1 to W5 window (one stream = one engineer or one focused agent session at 70% utilisation, an assumption; the real capacity is not recorded):", "",
          "| Parallel streams | Productive days | Tiers that fit the MAXIMUM estimate | Tiers that fit the MINIMUM estimate |", "|---|---|---|---|"]
    for n in (3, 5, 8, 11, 14, 17):
        cap = n * per
        fit_hi = max([r[0] for r in tier_totals() if r[5] <= cap], default=None)
        fit_lo = max([r[0] for r in tier_totals() if r[4] <= cap], default=None)
        L.append(f"| {n} | {cap:.0f} | {('T0 to T' + str(fit_hi)) if fit_hi is not None else 'not even T0'} | {('T0 to T' + str(fit_lo)) if fit_lo is not None else 'not even T0'} |")
    L += ["", "### Strategy comparison (S1 selected by the owner; S2 and S3 rejected as release plans)", "", "| Strategy | Content | Effort (days) | Streams needed | Packages | Critical path (days) |", "|---|---|---|---|---|---|"]
    for name, (desc, ids) in strategy_sets().items():
        lo = sum(BYID[i]["effort"][0] for i in ids)
        hi = sum(BYID[i]["effort"][1] for i in ids)
        c0, c1 = critical_path_subset(ids, 0), critical_path_subset(ids, 1)
        L.append(f"| {name} | {desc} | {lo}-{hi} | {lo / per:.1f}-{hi / per:.1f} | {len(ids)} | {c0[1]:.0f}-{c1[1]:.0f} via {' > '.join(c1[0])} |")
    L += ["", "Reading: with 3 to 5 streams not even the non-negotiable tier T0 fits at its maximum estimate, so a real-user beta by 30 November needs a larger effort or a later date regardless of what else is cut. The tiers define the order in which scope is added as capacity allows.", ""]
    return L


def render_staffing() -> str:
    t = totals()
    per = UTILISATION
    rec_name, rec = recommended_profile()
    prs = sum(_pr_count(p["pr"]) for p in PACKAGES)
    demand = role_demand()
    unl0, unl1 = completion([200], 0), completion([200], 1)
    L = ["# Staffing and Critical-Path Plan for the Full R1.0 Scope (S1)", "",
         "**Status:** GENERATED by `scripts/production/execution_packages.py` from the package definitions; PROPOSED for owner approval. The owner selected **S1, the full originally agreed R1.0 scope** (OD-SCOPE-01) and is prepared to allocate additional time and engineering resources. **Nothing in this plan assumes that any person has been hired or assigned**; every role below is unfilled until the owner names someone. No product requirement is removed, downgraded or postponed to meet a delivery target, and no acceptance test is weakened.", "",
         "## 1. Basis and assumptions (all stated, none measured yet)", "",
         f"- **Effort:** {len(PACKAGES)} packages, **{t['min_days']} to {t['max_days']} ideal engineering days** (the Phase 00 figure was 196 to 304; the extra days are the interface-contract and continuous-evidence packages added below, accepted as the cost of parallelism). These are my estimates and have not been validated against real throughput.",
         f"- **Productive time:** a stream delivers {int(per * 100)}% of a working day as productive effort (review, CI waits, rework; assumption). A second stream on the same package delivers {int(PAR_EFFICIENCY * 100)}% of a first (merge and coordination overhead; assumption).",
         "- **Calendar-bound human and legal lead times** engineering cannot compress (assumed working days of elapsed time, to be replaced by real quotes): " + ", ".join(f"{k} {v}" for k, v in ELAPSED_FLOOR.items()) + ".",
         "- Working days are Monday to Friday from Monday 26 October 2026, with no public holidays modelled (late December will reduce capacity). The owner-authorised first wave starts when PR #212 is merged; the plan assumes that is on or about 26 October.", "",
         "## 2. Human capacity versus Claude Code sessions", "",
         "A **stream** is one unit of parallel engineering: one human engineer or one Claude Code session working one bounded package. They are not interchangeable:", "",
         "| | Human engineer | Claude Code session |", "|---|---|---|",
         "| Implements a well-bounded package with a written brief, tests and acceptance criteria | yes | yes (the first-wave briefs are written for this) |",
         "| Runs in parallel without hiring or onboarding delay | no (hiring and ramp-up take weeks; none is assumed) | yes, limited by review capacity, budget and tool access |",
         "| Merge authority, owner decisions, approvals | PO and the technical integration lead only | never |",
         "| Production credentials, hosting accounts, DNS, provider contracts | yes, under the owner's authority | only when separately authorised; none is assumed |",
         "| Native-language review, legal qualification, independent human AI evaluation, licensing review | yes, external specialists | no: these are human by definition and cannot be replaced |",
         "| Throughput on this codebase | unknown | unknown until measured: the first wave measures it (section 7) |", "",
         "**Review is the binding constraint for Claude Code streams:** every package becomes pull requests that a human must review and the technical integration lead must sequence. The plan counts "
         f"**about {prs} pull requests**; at an assumed 0.5 reviewer-day each (1.0 for security- or privacy-sensitive ones) that is roughly {prs * 0.5:.0f} to {prs * 0.75:.0f} reviewer-days before rework, which is why a dedicated integration lead and at least two further reviewers are required whatever mix of humans and sessions the owner chooses.", "",
         "## 3. Roles needed (all unfilled)", "", "| Role | Responsibility | Effort demand (days, low to high) | FTE to deliver in the chosen window* |", "|---|---|---|---|"]
    window = completion(rec, 1)
    for r, desc in ROLES.items():
        lo, hi = demand.get(r, (0, 0))
        fte = f"{hi / (window * per):.1f}" if hi else "n/a"
        L.append(f"| {r} | {desc} | {lo:.0f}-{hi:.0f} | {fte} |")
    L += ["", f"*FTE = highest effort demand divided by the productive days available in the {window:.0f}-working-day window of profile '{rec_name}'. The sum is the number of parallel streams the profile needs at peak, more than the number of people if sessions are used.", "",
          "**Minimum human core (cannot be sessions):** one technical integration lead, one DevOps and reliability engineer with hosting authority, one QA lead, plus the owner as merge authority. **Specialists to engage now (calendar-bound):**", "",
          "| External role | Scope | Gate | Status | Assumed lead time |", "|---|---|---|---|---|"] + [f"| {a} | {b} | {c} | {d} | {e} |" for a, b, c, d, e in EXTERNAL]
    L += ["", "## 4. Critical path: analysed and shortened", "",
          "The Phase 00 plan had a 26 to 39-day sequential chain (03A, 03D, 03E, 08A) and a chain through Knowledge persistence (02A, 02B, 02E) because later packages waited for earlier ones. It was shortened **without removing any feature or weakening any test**:", "",
          "| Change | Mechanism | Effect |", "|---|---|---|",
          "| 03K Admin metric and report contract | Interface contract: dashboards (03D1) and reports (03E1) both build on the same typed metric and report definitions instead of 03E waiting for 03D | Removes the 03D then 03E chain; backends run in parallel |",
          "| 03D and 03E split into backend (03D1, 03E1) and views (03D2, 03E2) | Independent implementation boundaries | Backends no longer wait for the Admin shell; views merge after 03A |",
          "| 03B and 03C no longer depend on 03A | Backend-first; the grouped shell (03A) merges first and the others rebase on it (CI enforces) | Parallel from day one |",
          "| 02K Knowledge runtime and manifest contract | Interface contract for identity, manifest v2 and the scanner interface | 02B (embeddings) and 02C (scanning) no longer wait for 02A |",
          "| 01B0 Prompt asset and loader contract | Interface contract | 06C (per-language AI behaviour) no longer waits for 01B; the 01B, 01D, 01C shared-file order is unchanged |",
          "| 08A0 continuous release-evidence pipeline | Continuous integration of evidence from the first merge | The final freeze is 2 to 3 days of assembly, not 3 to 5 days of creation |",
          "| Per-language packages (06B to 06E) use up to four streams; heavy packages up to two to three | Parallelism by language and by PR | Shorter elapsed time for the same effort |",
          "| 06F native review and legal translation engage reviewers immediately | Starts at day 0, per language as catalogues freeze | Removes a dependency on the audit |",
          "| 07B depends on 01B and 01D, not 01C | 01C does not change behaviour (parity only); CI re-runs the tool-selection suite | One fewer package in the chain |", "",
          f"**Result.** With unlimited streams the full scope finishes after **{unl0:.1f} working days at the low estimate ({date_of(unl0)})**, bounded by the assumed {ELAPSED_FLOOR['06F']}-day human review lead time, and **{unl1:.1f} working days at the high estimate ({date_of(unl1)})**, bounded by the owner-mandated shared-file order (01B0, 01B, 01D, then 07B live validation and the freeze). The Phase 00 chain of 26 to 39 effort-days is replaced by effort-day chains of {t['cp_min'][1]:.0f} to {t['cp_max'][1]:.0f} days (`DEPENDENCY_GRAPH.md`). More streams cannot go below these figures; only a better estimate, shorter lead times or a later date can.", "",
          "## 5. Completion by staffing profile (resource-constrained schedule)", "",
          "Streams available in week 1, week 2, week 3 and after. Week 1 always starts the owner-authorised first wave (05A, 01A, 02A, 01B, 03A, 06A) plus the contract and early-engagement packages. The 30 November target needs completion by working day 25 (the end of Friday 27 November).", "",
          "| Profile (streams) | Peak streams used | Completes, low estimate | Completes, high estimate | Meets 30 November? |", "|---|---|---|---|---|"]
    for name, prof in PROFILES.items():
        lo_d, hi_d = completion(prof, 0), completion(prof, 1)
        meets = "low estimate only" if lo_d <= FREEZE_DAY and hi_d > FREEZE_DAY else ("yes" if hi_d <= FREEZE_DAY else "no")
        L.append(f"| {name} | {peak_streams(prof, 1)} | day {lo_d:.0f}, {date_of(lo_d)} | day {hi_d:.0f}, {date_of(hi_d)} | {meets} |")
    L += [f"| Unlimited streams | n/a | day {unl0:.0f}, {date_of(unl0)} | day {unl1:.0f}, {date_of(unl1)} | {'low estimate only' if unl0 <= FREEZE_DAY < unl1 else ('yes' if unl1 <= FREEZE_DAY else 'no')} |", "",
          f"**Reading.** No staffing level completes the full scope by 30 November if the high effort estimate is right, and only an unlimited team on the low estimate reaches it, with nothing left for rework. The realistic window for a gate-complete S1 is **{date_of(completion(PROFILES['D ramp 12, 18, 24'], 0))} to {date_of(completion(PROFILES['D ramp 12, 18, 24'], 1))}** with a ramp to 24 streams, later with fewer. The owner's rule is that the deadline never overrides a mandatory gate, so **the plan's date is the gates' date**: the 30 November target holds only as the low-estimate, unlimited-staffing bound; the owner should treat mid December as the planning date for S1 until the first wave re-baselines the estimates.", "",
          "## 6. Staffing ramp (proposed)", "", "| Week | Streams | Composition (proposed) | Gate to proceed |", "|---|---|---|---|",
          "| W0 (21-25 Oct) | 0 engineering | Owner merges PR #212 and appoints the integration lead, DevOps lead and QA lead; engages native reviewers, counsel, evaluators and the licensing reviewer; answers OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS | Merge; people named |",
          "| W1 (26 Oct-1 Nov) | 12 | The authorised first wave as eight Claude Code sessions (05A, 01A, 02A, 01B0 then 01B, 03A, 06A, 02K, 03K) under the integration lead, plus the two engagement streams (05E, 06F) and 08A0 | First-wave PRs open with green CI; throughput measured |",
          "| W2 (2-8 Nov) | 18 | Add 02B, 02C, 03B, 03C, 03D1, 03E1, 04A, 04B, 04E, 05B to 05D, 06C, 06E as contracts merge; recruit humans for the integration, DevOps and QA roles | Contracts merged; review latency under two days |",
          "| W3 (9-15 Nov) | 24 | Admin views (03D2, 03E2), 04C streaming, 04D journeys, per-language journeys and retrieval (06B, 06D), 02E | Re-baseline estimates against measured throughput |",
          "| W4 onward | up to 24, falling | Language qualification runs, human evaluation, hosted rehearsal, security review, fixes, freeze | Evidence complete per gate |", "",
          "Streams above what the owner can staff and review simply move the dates in section 5 later; they never justify skipping a gate.", "",
          "## 7. Measuring actual throughput (after the first wave)", "",
          "For every package the tracker records estimated days, actual productive days, review latency, rework rounds and CI first-pass rate. After the first wave and again after the second, the estimates and the table in section 5 are re-generated from measured values; if measured throughput is below the assumption the dates move and the owner is told immediately with the recovery options (more streams, reviewers or time), never by silently re-scoping.", "",
          "## 8. Risks to the full-scope date", "",
          "1. Review bandwidth (the largest): without an integration lead and extra reviewers, session output queues rather than ships.", "2. Calendar-bound human work: the five external roles above are unnamed; any slip moves the freeze one-for-one.",
          "3. Decisions: OD-HOSTED, OD-BUDGET, OD-GATE-THRESHOLDS and OD-EMBED block packages if not answered in W0 to W1.", "4. Estimate error: all estimates are unvalidated; the high estimate is the planning figure.",
          "5. Environment and credentials: hosting, scanner, provider budgets and embeddings credentials are not provisioned and must not be before the owner authorises them.", "6. Dependency drift: the PR #212 CI failure was a fresh-install drift; pinning and a periodic fresh-install canary are part of 08A0.", ""]
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
        (OUT / "STAFFING_AND_CRITICAL_PATH_PLAN.md").write_text(render_staffing(), encoding="utf-8")
        print(json.dumps({k: v for k, v in totals().items() if k not in ("cp_min", "cp_max")}, indent=1), totals()["cp_min"], totals()["cp_max"])
        return 0
    if cmd == "check":
        for name, fn in (("IMPLEMENTATION_PACKAGE_REGISTER.md", render_register), ("DEPENDENCY_GRAPH.md", render_graph), ("DELIVERY_SCHEDULE.md", render_schedule), ("STAFFING_AND_CRITICAL_PATH_PLAN.md", render_staffing)):
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
