"""Production roadmap V2.2: reconcile the deferred-issue register into release dispositions.

    python scripts/production/reconcile_issues.py generate   write docs/production/PRODUCTION_ISSUE_RECONCILIATION.json, MASTER_REQUIREMENTS_TRACEABILITY.md, RELEASE_BLOCKER_DASHBOARD.md
    python scripts/production/reconcile_issues.py check      fail unless the committed JSON is internally valid AND matches the register (no unmapped active issue, no rewritten history)

Everything here is a PROPOSED disposition computed by documented rules (``RULES``); no historical status, gate result or closure evidence is changed. The register file
``docs/capstone/post_submission_deferred_issues.json`` is read, never written. No provider is contacted.
"""

from __future__ import annotations

import difflib  # noqa: F401  (kept for reviewers who want to experiment with other similarity measures)
import importlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
REGISTER = ROOT / "docs/capstone/post_submission_deferred_issues.json"
OUT = ROOT / "docs/production"
RECON = OUT / "PRODUCTION_ISSUE_RECONCILIATION.json"

DISPOSITIONS = ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0", "OWNER DECISION", "DEFER TO NAMED RELEASE", "CLOSE WITH EVIDENCE")
RELEASES = ("R1.0", "R1.1", "R1.2", "R1.3", "R1.4", "R1.5", "R1.6", "R1.7", "R2.0")
DEFER_RELEASES = RELEASES[1:]
UNSCHEDULED = "UNSCHEDULED"   # only an OWNER DECISION may be unscheduled (e.g. a future Russian activation decision)

# Proposed release themes (the owner fixed only R1.0 = 30 Nov 2026 and R1.3 = Mandarin/Hindi/Arabic; the rest are PROPOSED).
RELEASE_THEMES = {
    "R1.0": "30 November 2026: free, invitation-only private production beta; seven languages each subject to individual qualification; Admin 2.0 essentials; reliable Knowledge Sources; Story Bank and Workspaces; core reporting; the five reviewer corrections; no live billing",
    "R1.1": "Indicative December 2026: paid beta and plan expansion (Stripe and subscription lifecycle after provider/legal qualification; pricing, tax, cancellation, refunds, reconciliation; new plan families)",
    "R1.2": "Indicative December 2026 to January 2027: advanced Admin and automation (scheduled reporting, advanced analytics, automation, bulk administration, expanded alerts)",
    "R1.3": "Indicative January to February 2027: Mandarin, Hindi, Arabic (new locale, prompt, safety, retrieval, accessibility, legal and native review; Arabic RTL)",
    "R1.4": "Indicative February 2027: voice interview experience (qualified STT, TTS and live voice practice; licensing and consent; latency; native speech quality)",
    "R1.5": "Indicative February to March 2027: global career intelligence (additional countries, qualified occupational sources, provenance, multilingual geographic retrieval)",
    "R1.6": "Indicative March 2027: Compensation Intelligence V2 (qualified salary datasets, geographic comparison, freshness, methodology, legal and human approval)",
    "R1.7": "After R1.6, date not committed: teams and enterprise (enterprise Workspaces, organization subscriptions, SSO and governance, qualified external integrations)",
    "R2.0": "Evidence-led, subsequent: expanded intelligent career platform (personalized guidance, agentic workflows, deeper career development)",
}

# Code constants that keep gated features disabled; a deferral is only valid while every one of them is False (checked by `check`).
GATE_CONSTANTS = [
    ("src.billing.policy", "LIVE_BILLING_ENABLED"), ("src.billing.policy", "EXTERNAL_CHECKOUT_AUTHORIZED"), ("src.billing.policy", "STRIPE_WEBHOOK_AUTHORIZED"),
    ("src.billing.policy", "RECONCILE_SCHEDULER_ENABLED"), ("src.billing.policy", "PROVIDER_READS_AUTHORIZED"),
    ("src.speech.policy", "SERVER_SPEECH_PROVIDERS_AUTHORIZED"), ("src.speech.policy", "WHISPER_API_TRANSPORT_AUTHORIZED"), ("src.speech.policy", "MODEL_DOWNLOADS_AUTHORIZED"),
    ("src.speech.policy", "VOICE_CLONING_ENABLED"), ("src.application.history_access", "HISTORY_RESTRICTIONS_ENFORCED"), ("src.application.model_profile_access", "MODEL_PROFILE_ENFORCED"),
]
GATE_NAMES = [f"{m}.{n}" for m, n in GATE_CONSTANTS]
FEATURE_GATES = {
    "commercial": ["src.billing.policy.LIVE_BILLING_ENABLED", "src.billing.policy.EXTERNAL_CHECKOUT_AUTHORIZED", "src.billing.policy.STRIPE_WEBHOOK_AUTHORIZED"],
    "speech": ["src.speech.policy.SERVER_SPEECH_PROVIDERS_AUTHORIZED", "src.speech.policy.WHISPER_API_TRANSPORT_AUTHORIZED"],
    "gating": ["src.application.history_access.HISTORY_RESTRICTIONS_ENFORCED", "src.application.model_profile_access.MODEL_PROFILE_ENFORCED"],
}

WORK_PACKAGES = {
    "WP-01": ("Governance, reviewers and owner decisions", "Product Owner"),
    "WP-02": ("Hosted deployment, operations and resilience", "Platform and operations lead"),
    "WP-03": ("Identity, email and access", "Security lead"),
    "WP-04": ("Privacy, data rights and legal", "Privacy and legal lead"),
    "WP-05": ("AI security and grounding policy", "AI safety lead"),
    "WP-06": ("Knowledge sources and retrieval (seven markets)", "Knowledge and data lead"),
    "WP-07": ("Candidate journeys, Mo and Practice quality", "Product lead (candidate)"),
    "WP-08": ("Multilingual programme (seven languages)", "Localisation lead"),
    "WP-09": ("Story Bank, Workspaces and shared reports", "Product lead (collaboration)"),
    "WP-10": ("Admin 2.0 (English-only): users, plans, reports, knowledge, navigation", "Product lead (operations)"),
    "WP-11": ("Commercial and billing (gated)", "Commercial lead"),
    "WP-12": ("Speech and realtime voice (gated)", "Speech lead"),
    "WP-13": ("External integrations", "Integrations lead"),
    "WP-14": ("Human validation and native review", "Quality and human-review lead"),
    "WP-15": ("Quality engineering, accessibility and technical debt", "Engineering lead"),
    "WP-16": ("Live evaluation and measurement", "Evaluation lead"),
    "WP-17": ("AI platform engineering: versioned prompts, tool catalogue, streaming", "AI platform lead"),
}
CATEGORY_WP = {"A": "WP-06", "B": "WP-06", "C": "WP-16", "D": "WP-05", "E": "WP-12", "F": "WP-04", "G": "WP-10", "H": "WP-02", "I": "WP-11", "J": "WP-13", "K": "WP-04", "L": "WP-14", "M": "WP-15", "N": "WP-07"}

WP_TESTS = {
    "WP-01": "Signed appointment/decision records in the repository; audit-log evidence for role changes",
    "WP-02": "Hosted rehearsal (TLS/HSTS, migration, backup and restore, rollback, pause), scripts/eval_hosting_readiness.py, deployment checklist",
    "WP-03": "Auth/session/step-up suites, live email and OIDC verification under owner authorisation, tests/test_auth*.py",
    "WP-04": "Privacy request, retention and deletion suites; legal counsel sign-off record; scripts/eval_admin_privacy_legal.py",
    "WP-05": "Language-specific injection/grounding suites; tests/test_candidate_grounding_policy.py; scripts/eval_agent.py",
    "WP-06": "Source approval register, licence check, retrieval and citation suites, scripts/eval_kb_requalification.py, product coverage gate",
    "WP-07": "Candidate journey Playwright specs, tests/test_integrated_requalification.py, human-rated question/evaluation sample",
    "WP-08": "Per-language gates LG-01..LG-14 in MULTILINGUAL_RELEASE_QUALIFICATION.md; scripts/eval_i18n_l10n.py; native-reviewer sign-off",
    "WP-09": "Story/Workspace/share owner-isolation suites (eval_workspace_security), Playwright share flows, report export tests",
    "WP-10": "Admin permission matrix, route invariant, Admin Playwright specs, eval_admin_* gates",
    "WP-11": "Mock-billing suites stay green; sandbox qualification only after owner approval; gates remain False until R1.2",
    "WP-12": "scripts/eval_speech_providers.py; governed-speech tests; live quality only after owner approval",
    "WP-13": "Integration probes with owner-supplied credentials; eval_admin_integrations",
    "WP-14": "Blinded human rating protocol results; named reviewers; sign-off documents",
    "WP-15": "pytest, vitest, Playwright, ruff, lint, typecheck, accessibility specs, CI aggregate gate",
    "WP-16": "Bounded live evaluations under a separately approved budget; deterministic evaluators; reports with run identity",
    "WP-17": "Prompt loader/rollback tests, registry parity tests, SSE contract/cancellation/cross-user tests, browser progress tests",
}

ACADEMIC_ONLY = {  # historical capstone-submission tasks that are not production dependencies (rationale shown in the item)
    "IR-DEADLINE": "the course deadline and time zone concern the capstone submission",
    "IR-TURING-RUBRIC": "the course brief and rubric concern the capstone submission",
    "IR-DEPLOY-EXPECT": "the course deployment expectation concerns the capstone submission (production hosting is tracked separately in WP-02)",
    "IR-AC-LEDGER": "single reconciled capstone acceptance ledger for the submission (the historical ledger stays as recorded)",
    "IR-RC004-SPEC": "RC-P10-004 entry specification for the capstone release-candidate convention",
    "G-WALK-ENV": "the capstone Admin walkthrough used a development server and seeded data",
}

# Phase 00 review: proposed R1.0 scope reclassification (PROPOSED ONLY, NOT APPLIED: item dispositions above stay as generated until the owner confirms).
# An item is proposed only if the capability it concerns is provably inaccessible in the R1.0 Candidate API and UI. Evidence keys are verified by
# tests/test_r1_scope_exclusions.py. Two of the twelve candidates failed the proof and are withdrawn.
EVIDENCE = {
    "E-IMPORT": "no module under src/ outside src/knowledge_foundation imports it (AST scan): the Compensation V2 and US occupational foundation code is unreachable from any API, application, agent or retrieval path",
    "E-ROUTES": "the OpenAPI path table (266 paths, 114 non-admin) has no compensation, foundation, qualification, alias or recording route",
    "E-UI": "no frontend source (app, components, lib) references Compensation V2, the knowledge foundation, US SOC or BLS OEWS alias review",
    "E-READY": "knowledge_foundation.readiness.assess reports operational_today False, 0 linkable Compensation V2 records and 0 approved Compensation V2 sources",
    "E-REGISTER": "the register's own candidate-impact text records no Candidate effect while Compensation V2 and candidate-facing use stay disabled",
    "E-SPEECH": "the frontend never calls /speech/transcriptions or /speech/synthesis (only /speech/capabilities), the backend answers 503 speech_unavailable by default, and the server speech gate constants are False",
}
RECLASSIFICATION_PROPOSAL = {
    "BL-5": ("R1.6", "12 batches of Compensation V2 records awaiting reviewer decisions: Compensation Intelligence V2 work", ["E-IMPORT", "E-ROUTES", "E-UI", "E-READY", "E-REGISTER"]),
    "BL-6": ("R1.5", "Five US occupational alias proposals: qualified occupational sources for additional countries", ["E-IMPORT", "E-ROUTES", "E-UI", "E-READY", "E-REGISTER"]),
    "BL-6.1": ("R1.5", "US alias decision Software Developer to 15-1252", ["E-IMPORT", "E-ROUTES", "E-UI", "E-REGISTER"]),
    "BL-6.2": ("R1.5", "US alias decision Human Resources Manager to 11-3121", ["E-IMPORT", "E-ROUTES", "E-UI", "E-REGISTER"]),
    "BL-6.3": ("R1.5", "US alias decision Sales Manager to 11-2022", ["E-IMPORT", "E-ROUTES", "E-UI", "E-REGISTER"]),
    "BL-6.4": ("R1.5", "US alias decision Accountant to 13-2011", ["E-IMPORT", "E-ROUTES", "E-UI", "E-REGISTER"]),
    "BL-6.5": ("R1.5", "US alias decision Financial Analyst to 13-2051", ["E-IMPORT", "E-ROUTES", "E-UI", "E-REGISTER"]),
    "BL-9": ("R1.5", "Promotion of us_soc_2018 and bls_oews into the persistent source registry", ["E-IMPORT", "E-ROUTES", "E-READY", "E-REGISTER"]),
    "BL-12": ("R1.6", "Runtime authorisation and deployment review for Compensation V2", ["E-IMPORT", "E-ROUTES", "E-UI", "E-READY", "E-REGISTER"]),
    "W12.4E-12": ("R1.4", "Server-side browser recording client (server speech)", ["E-SPEECH"]),
}
RECLASSIFICATION_WITHDRAWN = {
    "BL-6.6": "Data Analyst and Product Manager remain unresolved: the register states it affects 13 of the 26 insufficient coverage cases (ambiguous titles), i.e. the enabled role-resolution and abstention behaviour Candidates use today; the proof fails, so it stays in R1.0 (package 02E)",
    "BL-7": "Resolve the Data Analyst and Product Manager evidence gaps: needed for any legitimate coverage close and concerns enabled role resolution; the proof fails, so it stays in R1.0 (package 02E)",
}

MARKETS = ["Ireland", "Germany", "Spain", "Italy", "Portugal", "France", "Netherlands"]
SEVEN_MARKET_RE = re.compile(r"\b(ireland|irish|germany|german|deutschland|spain|spanish|italy|italian|portugal|portuguese|france|french|netherlands|dutch|eu\b|europe|esco|eurostat)", re.I)
OTHER_MARKET_RE = re.compile(r"\b(united kingdom|\buk\b|canada|australia|india|china|japan|brazil|mexico|singapore|uae|gulf|saudi|africa|latin america)\b", re.I)
LANG_RE = re.compile(r"(locale|language|translat|multilingual|native-|native review|i18n|l10n|cross-language|xlang|dutch|german|french|spanish|italian|portuguese|russian|\bru\b|conversation language)", re.I)
RUSSIAN_RE = re.compile(r"(russian|\bru\b|cyrillic)", re.I)
FUTURE_LANG_RE = re.compile(r"(mandarin|chinese|hindi|arabic)", re.I)
COMMERCIAL_RE = re.compile(r"(stripe|billing|checkout|invoice|\btax\b|refund|premium|revenue|merchant|seller|payment|subscription|pricing|entitlement|plan price|mrr)", re.I)
CLAIM_RE = re.compile(r"(claim|label|preview|banner|disclos|public page|marketing|honest|wording|copy|page)", re.I)
SPEECH_SERVER_RE = re.compile(r"(whisper|kyutai|pocket|self-hosted|server|realtime|c1|model download|hosted speech|voice clon|gpu|latency budget)", re.I)
SPEECH_BROWSER_RE = re.compile(r"(dictation|browser|disclos|privacy|audio stor|consent)", re.I)
INTEGRATION_LATER_RE = re.compile(r"(adzuna|paging|pagerduty|on-call|slack|k4)", re.I)
NO_IMPACT = {"", "none", "n/a", "na", "not applicable"}

LANGUAGE_GATES = {  # keyword -> per-language gate ids (defined in MULTILINGUAL_RELEASE_QUALIFICATION.md)
    r"translat|native|locale catalog|key.parity|fallback": "LG-02,LG-12",
    r"journey|onboarding|opportunit|practice|interview": "LG-03,LG-05",
    r"prompt|policy|system": "LG-04",
    r"rag|retriev|citation|attribution|source": "LG-06",
    r"geograph|market|country": "LG-07",
    r"inject|secur|privacy|redact": "LG-08",
    r"legal|terms|privacy polic": "LG-10",
    r"story|workspace|share": "LG-09",
    r"human|review|rating": "LG-11",
}


def load_register():
    raw = json.loads(REGISTER.read_text(encoding="utf-8"))
    return raw, raw["issues"]


def _tok(text: str) -> set[str]:
    stop = set("the a an of and or to in for on is are not no with by be as at from this that it its into than live".split())
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if w not in stop and len(w) > 2}


def _blob(i: dict) -> str:
    return " ".join(str(i.get(k) or "") for k in ("title", "description", "remaining", "release_impact", "security_privacy", "candidate_impact"))


def work_package(i: dict) -> str:
    b = _blob(i)
    strict = re.search(r"(locale|translat|multilingual|native-|native review|i18n|l10n|cross-language|xlang|conversation language)", i["title"], re.I)
    loose = LANG_RE.search(i["title"])
    if re.search(r"(appoint|reviewer identit|release approver|named (human )?reviewer|verify reviewer|reviewers? a, b)", i["title"], re.I):
        return "WP-01"
    if (strict if i["category"] in ("A", "B", "C", "D") else loose) and not re.search(r"(speech|dictation|tts|stt|whisper)", b, re.I):
        return "WP-08"
    if re.search(r"(story bank|workspace|share|invite|report export)", i["title"], re.I):
        return "WP-09"
    if i["category"] == "J" and re.search(r"(oidc|brevo|email|sso|google)", b, re.I):
        return "WP-03"
    return CATEGORY_WP[i["category"]]


def scope_group(i: dict) -> str:
    """Which R1.0-excluded feature family an issue belongs to (or 'core')."""
    b = _blob(i)
    if RUSSIAN_RE.search(b) and re.search(r"(russian|\bru\b)", i["title"] + i["description"], re.I):
        return "russian"
    if FUTURE_LANG_RE.search(b):
        return "future_language"
    if i["category"] == "I" or (COMMERCIAL_RE.search(i["title"]) and not CLAIM_RE.search(i["title"])):
        return "claims" if CLAIM_RE.search(i["title"]) else "commercial"
    if i["category"] == "E":
        if SPEECH_SERVER_RE.search(b) and not SPEECH_BROWSER_RE.search(i["title"]):
            return "speech_server"
        return "speech_browser" if SPEECH_BROWSER_RE.search(b) else "speech_server"
    if i["category"] == "A":
        if OTHER_MARKET_RE.search(i["title"]) and not SEVEN_MARKET_RE.search(i["title"]):
            return "intl_knowledge"
        return "seven_markets" if SEVEN_MARKET_RE.search(i["title"]) else "core"
    if INTEGRATION_LATER_RE.search(i["title"]):
        return "integration_later"
    return "core"


def decide(i: dict) -> dict:
    """Proposed disposition. Returns disposition, release, rule_id, reason, feature_gate."""
    st, prio, blocks = i["status"], i["priority"], i.get("blocks_production")
    grp = scope_group(i)
    sec = str(i.get("security_privacy") or "").strip().lower()
    if st == "CLOSED - VERIFIED":
        return dict(disposition="CLOSE WITH EVIDENCE", release="n/a", rule_id="C0", reason="historically CLOSED - VERIFIED; closure evidence preserved verbatim", feature_gate="")
    if st == "PENDING OWNER DECISION":
        inner = dict(i, status="DEFERRED - POST SUBMISSION")
        d = decide(inner)
        d.update(disposition="OWNER DECISION", rule_id="O0", reason="historically PENDING OWNER DECISION; release shown is proposed if the owner approves the underlying work")
        return d
    def deferred(release, rule, reason, gates):
        return dict(disposition="DEFER TO NAMED RELEASE", release=release, rule_id=rule, reason=reason, feature_gate=" + ".join(gates) if gates else reason)
    if i["original_id"] in ACADEMIC_ONLY:
        return dict(disposition="OWNER DECISION", release=UNSCHEDULED, rule_id="A0", reason="ACADEMIC ONLY: " + ACADEMIC_ONLY[i["original_id"]] + "; not a production dependency; the owner confirms retirement (OD-ACADEMIC-01)", feature_gate="")
    if grp == "russian":
        return dict(disposition="OWNER DECISION", release=UNSCHEDULED, rule_id="U-RU", reason="Russian is excluded from R1.0; eventual activation is a separate future owner decision, not an automatic R2.0 commitment (OD-RU-FUTURE)",
                    feature_gate="Russian removed from active Candidate language selection (REQ-LANG-14); code preserved")
    if grp == "future_language":
        return deferred("R1.3", "D-FL", "Mandarin, Hindi, Arabic are the R1.3 languages (owner decision)", ["no zh/hi/ar locale is registered in src/locales.py"])
    if grp == "commercial":
        return deferred("R1.1", "D-COM", "paid beta: Stripe, pricing, tax, refunds, reconciliation and new plan families are R1.1; R1.0 is a free beta with billing disabled", FEATURE_GATES["commercial"])
    if grp == "intl_knowledge":
        comp = re.search(r"(compensation|salary|salaries|pay\b|wage)", i["title"] + " " + i["description"], re.I)
        return deferred("R1.6" if comp else "R1.5", "D-INTL", "additional-country or compensation evidence is outside the R1.0 selected-market scope; Compensation V2 and international sources stay disabled",
                        ["Compensation V2 and international sources not operational (src/knowledge_foundation/readiness.py: operational_today False)"])
    if grp == "speech_server":
        return deferred("R1.4", "D-SPEECH", "server speech, qualified STT/TTS and live voice practice are R1.4; governed speech stays disabled", FEATURE_GATES["speech"])
    if grp == "integration_later":
        if re.search(r"adzuna|k4", i["title"], re.I):
            return deferred("R1.5", "D-INT", "additional market data integration belongs with global career intelligence; not enabled", ["integration not configured; no live provider call is possible without owner credentials"])
        if re.search(r"paging|pagerduty|on-call|slack", i["title"], re.I):
            return deferred("R1.2", "D-INT", "expanded alerts and management workflows are R1.2; not enabled", ["no external paging configured"])
        return deferred("R1.7", "D-INT", "qualified external integrations belong with teams and enterprise", ["integration not configured"])
    verify_status = st in ("NOT RUN", "NOT VERIFIED", "PENDING HUMAN REVIEW")
    if grp == "seven_markets" and blocks != "YES":
        return dict(disposition="VERIFY BEFORE R1.0", release="R1.0", rule_id="M1", reason="source qualification for one of the seven R1.0 markets (proposed mapping; owner approval and qualification required before use)", feature_gate="")
    if blocks == "YES":
        disp = "VERIFY BEFORE R1.0" if verify_status else "FIX BEFORE R1.0"
        return dict(disposition=disp, release="R1.0", rule_id="B1", reason="blocks any production release and is not in an R1.0-excluded feature family", feature_gate="")
    if i["category"] in ("D", "F", "K") and (prio in ("P0", "P1", "P2") or sec not in NO_IMPACT):
        return dict(disposition="VERIFY BEFORE R1.0", release="R1.0", rule_id="S1", reason="AI-safety, privacy or legal dependency of a feature that stays enabled: never deferred while the feature is on (rule 10)", feature_gate="")
    if grp in ("claims", "speech_browser") or (sec not in NO_IMPACT and prio in ("P0", "P1")):
        return dict(disposition="VERIFY BEFORE R1.0", release="R1.0", rule_id="B2", reason="safety, privacy or public-claim relevance for an R1.0 feature that stays enabled", feature_gate="")
    if blocks == "UNKNOWN" and prio in ("P0", "P1"):
        return dict(disposition="VERIFY BEFORE R1.0", release="R1.0", rule_id="B3", reason="production impact unknown at P0/P1: verification is required before R1.0 (never assumed harmless)", feature_gate="")
    if work_package(i) == "WP-10":
        return deferred("R1.2", "D-ADM", "advanced Admin and automation window (placement proposed; no agreed theme for this item)", ["no enabled feature depends on it"])
    return deferred("R1.1", "D-GEN", "does not block production and has no safety, privacy or claim impact on an enabled feature; first post-beta release (placement proposed; the agreed R1.1 theme is paid beta)", ["no enabled feature depends on it"])


def language_gates_for(text: str) -> str:
    out = []
    for pat, gates in LANGUAGE_GATES.items():
        if re.search(pat, text, re.I):
            out.extend(gates.split(","))
    return ",".join(sorted(set(out))) or "LG-01"


def _row(id_, title, desc, wp, prio, disp, release, accept, tests, sec, deps, status, provenance, origin_class, source, impl="", gate="", test_evidence="none yet", lang_gates=""):
    return dict(id=id_, title=title, description=desc, wp=wp, priority=prio, disposition=disp, release=release, acceptance_criteria=accept, required_tests=tests, security_privacy_impact=sec,
                dependencies=deps, current_status=status, provenance=provenance, origin_class=origin_class, source=source, proposed_implementation=impl, feature_gate=gate, test_evidence=test_evidence,
                language_gates=lang_gates, origin="NEW", scope_class="PRODUCTION")


SRC = "docs/production/OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md"
PREV_BASELINE = dict(commit="4084eb9", items=433, r1_0_must_fix=70, r1_0_must_verify=74, owner_decisions=91, deferred=146, deferred_by_release={"R1.1": 94, "R1.2": 15, "R1.3": 2, "R2.0": 35}, closed=52, new_items=39)


def new_requirements() -> list[dict]:
    """Requirements that are NOT in the 394-row register, recovered from the owner's authoritative statement (see the source-of-truth document)."""
    out: list[dict] = []
    # ---- Turing College review findings (REVIEW-01..05): actual reviewer findings, each a separate testable requirement
    reviews = [
        ("REVIEW-01", "Prompt-injection defence depth", "WP-05", "P0",
         "Defences rely on deterministic heuristics in src/security.py and on RAG prompt instructions. Extend detection with a labelled regression corpus (direct, indirect, multilingual, encoded, retrieved-document), measure detection and benign false positives, fail CI on regression against an approved held-out corpus, add an injection-risk score to each RetrievalResult, quarantine high-risk chunks before context construction, revalidate every model-requested tool action against the authenticated user's goal, authorization, tool permissions and allowed arguments before any side effect, keep output-side safeguards in answer(), and never rely solely on the LLM obeying an instruction.",
         ["R1 corpus derived from evaluations/jailbreak_test_results.csv covering direct, indirect, multilingual, encoded and retrieved-document attacks, with a frozen held-out split", "R2 attack detection rate and benign false-positive rate are measured and reported per language; CI fails below the owner-approved thresholds (OD-GATE-THRESHOLDS)",
          "R3 every RetrievalResult carries an injection-risk score; chunks above the threshold are quarantined or excluded before the model context is built", "R4 a model-requested tool call is re-authorised server-side (goal, user authorization, tool permission, allowed arguments) before execution",
          "R5 malicious source content cannot trigger an unauthorised tool call or cross-user disclosure (negative tests)", "R6 output-side safeguards in answer() retained and tested; no sole dependence on prompt instructions"],
         "held-out injection corpus run in CI; tool-authorization negative tests; cross-user retrieval tests; output-guard tests; per-language injection suite",
         "src/security.py; src/copilot/security/; src/copilot/service.py; src/copilot/rag/; src/agent/; evaluations/jailbreak_test_results.csv", "PG-03; thresholds need OD-GATE-THRESHOLDS", "PARTIAL - heuristic detector and tool allow-list exist; none of R1 to R6 is complete"),
        ("REVIEW-02", "Externalized, versioned prompts", "WP-17", "P1",
         "Production prompts are mainly Python literals without declared version identities. Externalize agent, interview and RAG prompts into versioned assets with a validated loader, stable semantic versions independent of content hashes, retained SHA integrity hashes, production_versions() reporting declared version plus hash, effective prompt versions recorded on AgentRunResult and evaluation results, Prompt Lab attribution to exact prompt, model and configuration, and safe rollback to an approved version without new application code.",
         ["R1 agent system, interview technique and RAG prompts load from versioned assets through a validated loader (variables checked, missing version is a clear error)", "R2 each prompt has a declared semantic version independent of its SHA; the SHA is verified at load",
          "R3 production_versions() reports declared version plus hash", "R4 AgentRunResult and evaluation results record the effective prompt versions", "R5 Prompt Lab runs are attributable to exact prompt, model and configuration",
          "R6 rollback to an existing approved version needs no code change and is audited", "R7 template variables, compatibility, missing versions and rollback are tested"],
         "prompt loader unit tests; compatibility/rollback tests; production_versions parity test; Prompt Lab attribution test",
         "src/agent/policies.py; src/prompts.py; src/copilot/rag/prompts.py; src/config_versions.py; src/prompt_registry.py; src/agent/models.py", "PG-12", "NOT STARTED - prompts are code literals; a prompt registry and config versioning exist"),
        ("REVIEW-03", "Tool catalogue parity", "WP-17", "P1",
         "src/agent/policies.py duplicates tool descriptions already in the authoritative registry. Make the allow-listed registry the single catalogue, generate model-visible descriptions from registered metadata, derive argument contracts from Pydantic models, prevent drift, reject duplicate or invalid registrations, assert parity between registry, model bindings and authorization policy, remove duplicated descriptions after migration, and never widen the tool set to satisfy parity.",
         ["R1 model-visible tool descriptions are generated from registered metadata", "R2 argument contracts derive from the Pydantic models", "R3 a parity test fails if tool names, signatures or descriptions drift between registry, bindings and policy",
          "R4 duplicate or invalid registrations are rejected at registration", "R5 manually duplicated descriptions are removed after regression tests pass", "R6 the set of available tools is unchanged by this work (asserted)"],
         "registry parity test; duplicate-registration test; binding/authorization parity test; unchanged-tool-set assertion", "src/agent/registry.py; src/agent/policies.py; Pydantic tool schemas; binding and execution layers", "PG-12 (registry parity)", "NOT STARTED - registry exists; descriptions are duplicated in policies"),
        ("REVIEW-04", "Silent embedding degradation", "WP-06", "P0",
         "DEFAULT_EMBEDDING_PROVIDER = auto can resolve to the lexical LocalHashEmbedder without a semantic configuration. Surface provider, model and degradation in readiness, prevent silent fallback in production, fail closed when required credentials are missing, keep a clearly labelled offline development mode, record provider, model, version and dimensions in every index manifest, detect index/query mismatch, never query an incompatible index, rebuild qualified indexes from approved sources when necessary, evaluate BM25, vector and RRF separately and combined, and include multilingual and cross-language attribution.",
         ["R1 readiness shows the actual embedding provider, model and degradation state", "R2 in production the hash embedder is refused and a missing semantic credential fails closed (no silent fallback)", "R3 offline development mode remains and is clearly labelled",
          "R4 every index manifest records provider, model, version, dimensions and compatibility metadata", "R5 an index/query embedding mismatch is detected and the query is refused", "R6 qualified indexes can be rebuilt from approved material",
          "R7 BM25, vector and RRF are evaluated separately and combined, including multilingual retrieval and cross-language attribution"],
         "readiness tests; production-mode fail-closed tests; manifest and mismatch tests; retrieval-mode evaluation; multilingual retrieval evaluation",
         "src/copilot/constants.py; src/copilot/embeddings.py; src/copilot/retrieval/hybrid.py; knowledge build and readiness tools", "PG-05; paid embedding calls need OD-BUDGET", "PARTIAL - local hash embedder is the working default; readiness does not yet expose degradation"),
        ("REVIEW-05", "Agent streaming and feedback", "WP-17", "P1",
         "Agent execution is synchronous for the Candidate. Add an authenticated SSE endpoint beside POST /api/v1/agent/run using LangGraph astream_events version v2 where compatible, forward only safe allow-listed projections of existing AgentEvent types, never stream chain-of-thought, prompts, private tool arguments or secrets, show useful progress states, support cancellation and timeouts, preserve durable run identity, checkpointing and authorization, prevent cross-user exposure on reconnection, reconcile provider usage and cost even when cancelled, and keep the synchronous API as a tested fallback.",
         ["R1 an authenticated SSE endpoint exists beside POST /api/v1/agent/run", "R2 events are safe allow-listed projections; a negative test proves no chain-of-thought, system prompt, private tool argument or secret is emitted", "R3 the Candidate sees useful progress states",
          "R4 cancellation and timeouts work and leave a consistent durable run", "R5 reconnection cannot expose another user's events (cross-user test)", "R6 usage and cost are reconciled for a cancelled run", "R7 the synchronous API remains and is tested as a fallback"],
         "SSE contract tests; event-allow-list negative test; cancellation and timeout tests; cross-user reconnect test; cancelled-run usage test; sync fallback test; browser test of progress states",
         "src/agent/nodes.py; src/agent/events.py; src/application/agent_service.py; agent routes; Candidate Mo interface", "PG-06", "NOT STARTED - synchronous run API only"),
    ]
    for id_, title, wp, prio, desc, accept, tests, areas, pg, status in reviews:
        e = _row(id_, f"{title} (Turing College review finding)", desc, wp, prio, "FIX BEFORE R1.0", "R1.0", "; ".join(accept), tests, "Safety, privacy and integrity of AI behaviour", "owner-approved thresholds where noted (OD-GATE-THRESHOLDS); " + pg, status,
                 "REVIEWER_FINDING", "TURING-REVIEW", SRC + f" section 2 ({id_})", impl="Main areas: " + areas)
        e["requirements_list"] = accept
        out.append(e)

    # ---- Demo-observed engineering findings (kept separate from the reviewer findings)
    demo = [
        ("DEMO-01", "Admin Knowledge Sources looked empty although the curated corpus was intact", "Curated sources (31) and governed sources (4 synthetic) are different layers; the Sources page listed only governed records. A read-only curated panel was added (PR #210). The permanent fix is REQ-OWN-05.", "WP-10", "P1", "VERIFY BEFORE R1.0", "Page explains curated versus governed; walkthrough passes without the empty-state confusion", "Admin Knowledge Playwright; walkthrough", "CLOSED IN CODE (PR #210); verification pending"),
        ("DEMO-02", "Wrong stack mode silently broke Start interview (keyless stack, generic unavailable message)", "A keyless review stack and the live stack look identical in the UI; interview creation failed with a generic message. Needs a visible environment/mode indicator and clearer provider-unavailable copy, and a real Candidate journey test (REQ-CAND-01).", "WP-02", "P1", "FIX BEFORE R1.0", "Candidate and Admin show the active provider mode; the unavailable message distinguishes AI-not-configured from transient failure", "Mode-indicator tests; real-UI Start interview journey test", "NEW - NOT STARTED"),
        ("DEMO-03", "Live RAGAS result is PARTIAL (7 of 8 valid), relevancy 0.0 and context recall 0.0", "The only live RAGAS run covered 2 cases; the scores are valid but unexplained and low. Investigate before any quality claim.", "WP-16", "P1", "VERIFY BEFORE R1.0", "Root cause of the zero scores recorded; a larger approved run reaches COMPLETE", "Bounded live evaluation under an approved budget (OD-BUDGET)", "NEW - NOT STARTED"),
        ("DEMO-04", "Blocking calls inside async request paths can deadlock the event loop", "The live-demo spend guard blocked the event loop (fixed, regression test added). Audit other synchronous waits in async paths.", "WP-15", "P2", "VERIFY BEFORE R1.0", "Audit recorded; async-safety tests for provider chokepoints", "Async regression tests", "FIXED IN GUARD; audit not started"),
        ("DEMO-05", "Optional-dependency tests failed in the base CI install", "A test imported the optional RAGAS package (fixed in PR #209 with an evaluation-extras CI job). Audit other optional-dependency tests.", "WP-15", "P2", "VERIFY BEFORE R1.0", "Audit recorded; every optional-extra test runs in a provisioned job or skips by importorskip", "CI matrix", "FIXED FOR RAGAS; audit not started"),
    ]
    for id_, title, desc, wp, prio, disp, accept, tests, status in demo:
        out.append(_row(id_, title, desc, wp, prio, disp, "R1.0", accept, tests, "Reliability and honest representation of AI quality", "none beyond the item", status, "ENGINEERING_OBSERVED", "DEMO-OBSERVED",
                        "live-demonstration preparation, 2026-10-19 to 2026-10-21 (ENGINEERING-OBSERVED, not a reviewer finding; formerly RF-01..RF-05)"))

    # ---- Owner-requested capabilities: REQ-OWN-01..08 as specified, testable R1.0 requirements
    own = [
        ("REQ-OWN-01", "Admin Platform 2.0: Command Center and AI operations", "WP-10", "P1",
         "Operational Command Center dashboards (ADMIN-04) and AI operations administration (ADMIN-06). Charts use real sourced data with period, numerator, denominator, coverage and missing-data state. High-impact AI configuration changes are validated, permissioned and audited; system instructions and tool permissions are never directly editable.",
         ["C1 dashboards: active users and registration trends; candidate activation; interview start and completion rates; AI failure rate and latency; model usage and cost; retrieval and source health; worker and indexing failures; support ticket trends; security and incident indicators; deployment and provider readiness",
          "C2 every chart shows period, numerator, denominator, coverage and a missing-data state; no invented figures and no misleading zeros; chart type chosen by meaning", "C3 AI operations view: registered models, effective configuration, approved prompt versions, model readiness and cost, safe feature flags, provider readiness, agent execution status, evaluation results, incidents, audit",
          "C4 high-impact configuration changes are validated, permissioned and audited; no route edits system instructions or tool permissions", "C5 owner-operated Platform Admin still has no path to private CVs, stories, interviews or conversations"],
         "metric-source tests (each tile traced to a query and denominator); missing-data rendering tests; permission matrix and route invariant; Playwright dashboard specs; sentinel privacy tests",
         "Admin reads aggregates only; no candidate content", "REVIEW-02 (prompt versions) for C3; ADMIN-01 navigation", "PARTIAL - Command Center, AI administration, provider readiness and aggregate reporting foundations exist (W10.x, W12.x); the listed dashboards and AI operations view are not complete"),
        ("REQ-OWN-02", "Admin Plans: Basic/Premium management", "WP-10", "P1",
         "Manage the existing Basic and Premium plans without code changes (ADMIN-02). Billing is not enabled by a Premium plan existing; new plan families and paid activation are R1.1.",
         ["P1 edit draft plan versions; choose from implemented registered features only", "P2 enable or disable features per plan; configure usage limits and allowances", "P3 clone or version plans; compare plan configurations; preview the effect on candidate access",
          "P4 assign plans to users; apply authorized Workspace entitlements", "P5 activate and retire versions; existing subscriber rights preserved until an explicit migration decision", "P6 immutable audit trail; safe rollback", "P7 entitlements enforced in backend services, never by the frontend",
          "P8 no billing, checkout or payment path is enabled by any of the above"],
         "plan lifecycle tests; entitlement enforcement at the API boundary; preview-versus-actual parity test; audit immutability tests; rollback test; billing gates stay False",
         "Entitlement changes are privileged and audited; no secret or payment data", "OD-PLAN-ENFORCE (which entitlements are enforced during the free beta)", "PARTIAL - versioned plans, assignment and an entitlement service exist (W10.4); feature selection, comparison, preview and limits editing are not complete"),
        ("REQ-OWN-03", "Admin Users: complete operational user management", "WP-10", "P1",
         "Expand user administration into a complete operational experience (ADMIN-03) without granting access to private candidate content.",
         ["U1 search, filter, sort and paginate users; safe account metadata", "U2 activate, suspend, close and delete accounts through the existing deletion engine", "U3 role changes only through the two-person approval flow", "U4 revoke active sessions; resend permitted account communications",
          "U5 assign Basic or Premium; inspect Workspace memberships; permitted membership actions", "U6 support status and audit history per user", "U7 restricted bulk actions (the permitted set needs OD-BULK-ACTIONS)", "U8 owner self-lockout and privilege escalation are prevented server-side",
          "U9 no view of CVs, stories, interviews or conversations"],
         "user list/search/pagination tests; lifecycle and session-revocation tests; role-change approval tests; self-lockout tests; bulk-action guard tests; privacy sentinel tests; Playwright user admin specs",
         "Privileged account actions; deletion; never reads private content", "OD-BULK-ACTIONS", "PARTIAL - user list, lifecycle, role-change approval and session revocation exist (W10.2, W10.13); search/sort, membership inspection, bulk actions and communications are not complete"),
        ("REQ-OWN-04", "Admin Reports: prebuilt reports and governed custom report builder", "WP-10", "P1",
         "Enhance the aggregate reporting foundation (ADMIN-05). Scheduled distribution and advanced automation are R1.2.",
         ["B1 prebuilt reports: acquisition and onboarding; candidate engagement; interview practice and completion; AI feedback quality; Story Bank adoption and reuse; Workspace invitations and sharing; model performance and economics; agent/tool execution outcomes; knowledge and RAG quality; support operations; security and privacy; commercial performance only once real billing is qualified (R1.1)",
          "B2 custom report builder over approved metrics and approved dimensions with date-range filters, comparisons, appropriate chart types and saved configurations", "B3 export in supported formats (the set needs OD-REPORT-EXPORT)", "B4 no arbitrary SQL; no private candidate-data access", "B5 permission checks and small-cohort suppression enforced; missing data is shown as missing, never as zero"],
         "metric definition tests; small-cohort suppression tests; no-arbitrary-SQL test (builder accepts only registered metric and dimension ids); permission tests; export tests; chart-type rule tests; Playwright report specs",
         "Aggregates only; cohort suppression; never candidate content", "ADMIN-04 metric sources; OD-REPORT-EXPORT", "PARTIAL - aggregate reporting with suppression exists (W10.12); the listed reports, builder, saved configurations and exports are not complete"),
        ("REQ-OWN-05", "Knowledge Sources: permanent persistence and reliability", "WP-06", "P0",
         "Permanently fix missing or empty Knowledge Sources by correcting persistence and environment architecture, not the empty state (owner requirements 1 to 19, source-of-truth section 4). Definition of done: sources survive restarts, deployments and restore drills, remain compatible with their indexes, and produce attributable candidate-facing retrieval.",
         ["K1 persistent SQL source registry and durable private storage for uploaded files; persistent curated and governed indexes", "K2 separate, clearly labelled curated and governed views", "K3 safe Admin diagnostics show the environment, database and index identity; API and workers use compatible authoritative configuration",
          "K4 index manifests persist embedding model identity and checksums (links to REVIEW-04)", "K5 lifecycle: register, scan, parse, review, approve, index, activate, replace, retire, reindex; licensing and source-qualification safeguards preserved", "K6 genuine fail-closed malware scanning for real user uploads (the fake scanner never runs outside development)",
          "K7 monitoring and alerts for lost collections, missing sources, incompatible embeddings and failed jobs; authorized backup, restore, retry, rebuild and rollback", "K8 restart, redeployment and separate-environment restore tests pass; retrieval, citation provenance and candidate access verified after each",
          "K9 a production UI can never silently connect to an empty local demonstration database; no invented source counts; demonstration fixtures are never labelled production-approved evidence"],
         "restart persistence test; redeployment persistence test; restore-in-new-environment drill; manifest/embedder mismatch test; malware-scan fail-closed test; alert tests; retrieval and citation provenance tests; environment-identity diagnostics test",
         "Upload handling, licensing, malware and data integrity", "OD-MALWARE (scanner choice); OD-HOSTED; REVIEW-04", "PARTIAL - governed lifecycle, worker, readiness and curated-corpus listing exist; durability, restore, environment identity, alerts and a real scanner are not complete"),
        ("REQ-OWN-06", "Story Bank: complete functional Story Bank", "WP-09", "P1",
         "R1.0 includes a functional Story Bank (source-of-truth section 5).",
         ["S1 create stories manually; draft from approved Candidate evidence; full STAR editing", "S2 evidence provenance preserved; user-created, source-backed, user-corrected and model-suggested content visibly distinguished", "S3 search, filter and competency tags; connect stories to Opportunities",
          "S4 suggest relevant stories for interviews; Candidate approval before use; reuse during Practice; story evidence reflected in feedback", "S5 never invent achievements or numbers", "S6 persists across sessions; deletion and privacy controls; strict Candidate ownership",
          "S7 acceptance journey passes in the browser: create, edit, link to Opportunity, reuse in Practice, receive feedback, retrieve after restart"],
         "story CRUD and ownership tests; provenance-label tests; suggestion/approval tests; no-fabrication tests; Playwright acceptance journey including restart; per-language run (LG-09)",
         "Candidate private content; owner scoping; deletion", "WP-08 for per-language qualification", "PARTIAL - source-backed, revocation-aware story bank exists (P4); manual STAR editing UX, suggestion path, provenance badge, Opportunity link and Practice reuse are incomplete (CJ-D-05)"),
        ("REQ-OWN-07", "Workspaces: complete functional Workspaces", "WP-09", "P1",
         "R1.0 includes functional Workspaces with explicit VIEW-only sharing (source-of-truth section 6).",
         ["W1 create and manage Workspaces; invite members by email; accept and decline; pending invitations; cancel or revoke invitations", "W2 display membership and roles; remove members where authorized; safe ownership transfer", "W3 share supported resources explicitly, default VIEW-only; display what is shared and with whom; immediate revocation",
          "W4 no access to unshared private content; activity and audit data recorded", "W5 authorization tested at the API boundary, not only the frontend", "W6 acceptance journey: A creates and invites B; B accepts; A shares one resource; B sees only that; A revokes; B loses access immediately", "W7 qualified in all seven Candidate languages (LG-09)"],
         "invitation lifecycle tests; API-boundary authorization tests for every shared resource type; revocation-immediacy test; ownership transfer tests; two-user Playwright journey; per-language run",
         "Collaboration access control; cross-user isolation", "OD-WS-TRANSFER (ownership transfer rules)", "PARTIAL - Workspaces, invitations, VIEW-only shares and revocation exist in the backend (P6.5); candidate controls to invite and share are missing (CJ-D-01)"),
        ("REQ-OWN-08", "Admin navigation redesign and Review and Diagnostics relocation", "WP-10", "P1",
         "Replace the flat Admin destination list with a grouped, collapsible sidebar and relocate platform-wide Review and Diagnostics under /admin (ADMIN-01).",
         ["N1 grouped, collapsible sidebar (proposed groups: Command Center; Customers and Workspaces; Products and Commercial; AI and Knowledge; Insights and Operations; Governance and Settings; owner to confirm via OD-ADMIN-NAV)", "N2 expand and collapse, active highlighting, breadcrumbs, responsive layout, keyboard accessibility, permission-aware items, quick navigation where useful; route compatibility preserved when safe",
          "N3 platform-wide Review and Diagnostics reachable only through /admin; entry removed from global Candidate navigation; old routes redirect", "N4 a Candidate keeps access to their own authorized run details through a separate owner-scoped experience", "N5 backend permissions remain mandatory: a Candidate or unpermitted Admin gets 403 on diagnostic APIs regardless of the UI"],
         "navigation Playwright specs (expand/collapse, keyboard, breadcrumbs, responsive); permission-aware rendering tests; redirect tests; backend 403 tests for diagnostic routes; accessibility checks",
         "Frontend hiding is not authorization", "OD-ADMIN-NAV", "PARTIAL - flat Admin navigation exists; Review and Diagnostics currently sit outside the Admin shell (G-category issues)"),
    ]
    for id_, title, wp, prio, desc, accept, tests, sec, deps, status in own:
        e = _row(id_, title, desc, wp, prio, "FIX BEFORE R1.0", "R1.0", "; ".join(accept), tests, sec, deps, status, "OWNER_CAPABILITY", "OWNER-REQUIREMENT", SRC + " sections 3 to 6",
                 impl="Specified from the owner's requirement text; design and sequencing are engineering proposals")
        e["requirements_list"] = accept
        out.append(e)

    # ---- Further owner-stated requirements from the recovered text
    out += [
        _row("REQ-BETA-01", "Invitation-only registration for the private beta", "R1.0 is a free, invitation-only private production beta: registration must be restricted to invited people, with no open sign-up and no payment path.", "WP-03", "P0", "FIX BEFORE R1.0", "R1.0",
             "Registration succeeds only with a valid invitation; uninvited registration is refused server-side; the invitation mechanism is audited and revocable", "invitation-gate API tests; Playwright uninvited-registration test; audit tests; no payment route reachable", "Controls who can reach the product", "OD-INVITE (invitation mechanism)", "NOT VERIFIED - no invitation-only registration control is recorded in the register", "OWNER_DECISION_IMPLEMENTATION", "OWNER-REQUIREMENT", SRC + " section 1 (OWN-D03)"),
        _row("REQ-CAND-01", "Real Candidate end-to-end journey tests including Start interview", "A real browser journey test (not a backend unit test) covers registration, onboarding, Opportunity, Mo, Practice start, answer, feedback, History and Progress, including the Start interview 503/unavailable regression, with explicit labelling of offline versus live model evidence.", "WP-07", "P0", "FIX BEFORE R1.0", "R1.0",
             "One Playwright journey per language passes against a staging stack; a provider-unavailable condition produces a recoverable, accurate message; every result states whether it is offline, mocked or live", "Playwright journeys (7 languages); provider-down simulation; evidence labelling check", "Reliability; honest evidence classes", "DEMO-02; WP-08", "NOT STARTED", "OWNER_CAPABILITY", "OWNER-REQUIREMENT", SRC + " section 7"),
        _row("REQ-COV-01", "Define a separate frozen R1.0 beta-scope coverage measure", "The historical 95% product-coverage gate (386 of 412 against 392) is preserved with its FAILED result. Define a separate, frozen and qualified coverage measure for the R1.0 beta scope, limited to enabled features and licensed, supported market evidence.", "WP-06", "P0", "OWNER DECISION", "R1.0",
             "A frozen beta-scope case set and method are approved by the owner; the historical gate result is reported unchanged beside the new measure; the new measure is never labelled as the original gate", "coverage evaluator run on the frozen set; consistency check that both measures are reported", "Prevents relabelling a failed gate", "OD-COVERAGE", "AWAITING OWNER APPROVAL OF THE MEASURE", "AWAITING_APPROVAL", "OWNER-REQUIREMENT", SRC + " section 10 items 9 and 10"),
        _row("REQ-COV-02", "Exclude unsupported or unlicensed market evidence from enabled features", "Evidence from markets or sources that are not qualified and licensed for R1.0 must not feed any enabled candidate feature; unqualified markets are not offered.", "WP-06", "P0", "FIX BEFORE R1.0", "R1.0",
             "Retrieval and Mo answers use only approved sources for the enabled markets; a test proves an unqualified source cannot be retrieved by a candidate", "retrieval-approval tests; market-offering tests", "Licensing and provenance integrity", "OD-LANG-02 (per-country approval); REQ-OWN-05", "NOT VERIFIED", "OWNER_DECISION_IMPLEMENTATION", "OWNER-REQUIREMENT", SRC + " section 10 item 11"),
        _row("REQ-DEFER-01", "Verify every deferral leaves the feature inaccessible through UI and backend", "For every item deferred to a later release, a test proves the affected feature is unreachable from both the UI and the API while deferred (not only a code constant).", "WP-15", "P0", "FIX BEFORE R1.0", "R1.0",
             "A consolidated test per gated feature family (billing, speech, Compensation V2, international sources, Russian locale, history/model gating) exercises the API route and the UI entry point and expects refusal or absence", "consolidated gate-inaccessibility test suite; UI and API probes", "Deferral safety (rule 10)", "REQ-LANG-14 for Russian", "PARTIAL - gate constants are checked False; no consolidated UI plus API test exists", "OWNER_DECISION_IMPLEMENTATION", "OWNER-REQUIREMENT", SRC + " section 10 item 13"),
        _row("REQ-SCOPE-01", "A disabled feature must not block an unrelated safe beta feature", "Compensation V2 and speech stay disabled; their issues must not block shipping unrelated safe beta features, provided the disabled features are inaccessible (REQ-DEFER-01).", "WP-01", "P1", "VERIFY BEFORE R1.0", "R1.0",
             "Release rules and the reconciliation assign disabled-feature issues to their own release and do not count them as R1.0 blockers while inaccessible", "reconciliation check; REQ-DEFER-01", "none", "REQ-DEFER-01", "APPLIED IN THIS RECONCILIATION", "OWNER_DECISION_IMPLEMENTATION", "OWNER-REQUIREMENT", SRC + " section 10 item 12"),
    ]

    # ---- The agreed later releases as owner-stated scope (so every release R1.1 to R2.0 has at least one traced requirement)
    later = [
        ("REL-R1.1", "R1.1", "WP-11", "Paid beta and plan expansion", "Stripe and subscription lifecycle only after provider and legal qualification; live payments, pricing, tax, cancellation, refunds, reconciliation; new plan families and expanded commercial entitlement management.", FEATURE_GATES["commercial"]),
        ("REL-R1.2", "R1.2", "WP-10", "Advanced Admin and automation", "Scheduled reporting, advanced custom analytics, operational automation, enhanced bulk administration, expanded alerts and management workflows.", ["scheduled reporting and automation not enabled in R1.0"]),
        ("REL-R1.3", "R1.3", "WP-08", "New languages: Mandarin, Hindi, Arabic", "New locale, prompt, safety, retrieval, accessibility, legal and native review for each language; RTL handled appropriately for Arabic.", ["no zh/hi/ar locale is registered in src/locales.py"]),
        ("REL-R1.4", "R1.4", "WP-12", "Voice interview experience", "Qualified speech-to-text, text-to-speech and live voice practice; provider licensing and consent; latency and accessibility; native speech quality evaluation.", FEATURE_GATES["speech"]),
        ("REL-R1.5", "R1.5", "WP-06", "Global career intelligence", "Additional country coverage, qualified occupational sources, global evidence and source provenance, multilingual geographic retrieval.", ["international sources not operational (src/knowledge_foundation/readiness.py)"]),
        ("REL-R1.6", "R1.6", "WP-06", "Compensation Intelligence V2", "Qualified salary datasets, geographic comparisons, source freshness, methodology and confidence controls, legal and human evidence approval.", ["Compensation V2 not operational (src/knowledge_foundation/readiness.py: operational_today False)"]),
        ("REL-R1.7", "R1.7", "WP-13", "Teams and enterprise", "Enterprise Workspaces, organization subscriptions, advanced collaboration, SSO and governance, qualified external integrations. After R1.6; date not committed.", ["no enterprise or SSO feature is enabled in R1.0"]),
        ("REL-R2.0", "R2.0", "WP-07", "Expanded intelligent career platform", "Expanded personalized career guidance, intelligent agentic workflows and deeper career-development capabilities; evidence-led. Russian activation is NOT part of this commitment.", ["no R2.0 feature exists or is enabled"]),
    ]
    for id_, rel, wp, title, desc, gates in later:
        out.append(_row(id_, f"{rel} release scope: {title}", desc, wp, "P3", "DEFER TO NAMED RELEASE", rel, "Scope, acceptance criteria and gates are specified when the release is planned; the window is indicative, not a promise",
                        "to be defined at release planning", "Each release needs its own safety, privacy and legal qualification", "R1.0 complete", "PLANNED (indicative window)", "OWNER_CAPABILITY", "OWNER-REQUIREMENT", SRC + " section 8", gate=" + ".join(gates)))

    # ---- Language programme (REQ-LANG-01..16); provenance reflects the owner's confirmed decisions
    L = SRC + " sections 1 and 9"
    spec = [
        ("REQ-LANG-01", "Audit every existing locale", "Inventory interface catalogues, Mo conversation, interview and report text, legal and privacy pages and email templates for the seven languages; record gaps per language.", "Audit report per language with counts of missing, machine-translated and unreviewed strings", "scripts/eval_i18n_l10n.py plus a per-language audit table", "LG-01,LG-02", "[DECISION]"),
        ("REQ-LANG-02", "Verify all Candidate journeys in all seven languages", "Onboarding, Opportunity, Company research, Prepare/Mo, Practice, History, Progress, Documents, Settings and privacy controls work end to end in each language.", "One recorded run per language per journey with no English fallback leaking into chrome or Mo text", "Playwright per-language journey matrix", "LG-03", "[DECISION]"),
        ("REQ-LANG-03", "Prompts and system policies work correctly in each language", "Grounding, safety, coaching-style and language directives behave in each language with no policy bypass by switching language.", "Per-language policy regression suite passes", "tests/test_candidate_grounding_policy.py extended; scripts/eval_agent.py", "LG-04", "[DECISION]"),
        ("REQ-LANG-04", "Validate localized interview questions, scoring, feedback and explanations", "Question generation, rubric scoring, feedback and Deep Dive explanations in each language; scoring is not recomputed or biased by language.", "Blinded native-reader rating plus deterministic scoring-invariance checks", "Human rating protocol; scoring invariance tests", "LG-05,LG-11", "[DECISION]"),
        ("REQ-LANG-05", "Verify Story Bank and Workspaces in all seven languages", "Story capture, verification, sharing grants, invitations and export render and behave correctly in each language with owner isolation intact.", "Per-language Story Bank and Workspace flow passes", "eval_workspace_security plus per-language Playwright", "LG-09", "[DECISION]"),
        ("REQ-LANG-06", "Evaluate multilingual RAG and cross-language source attribution", "Question in language X over sources in language Y with correct attribution, abstention and no invented translation of source claims (links to REVIEW-04).", "Per-language retrieval and citation evaluation with sample sizes and limitations", "multilingual retrieval evaluator; citation validity tests", "LG-06", "[DECISION]"),
        ("REQ-LANG-07", "Language must never change labour-market country silently", "Selecting a language never changes career geography; the proposed market mappings are used only as an explicit, user-visible suggestion after per-country approval.", "Tests prove geography is unchanged by any language switch", "language/geography separation tests; Playwright", "LG-07", "[DECISION]"),
        ("REQ-LANG-08", "Language-specific injection, security and privacy regression suites", "Prompt-injection, PII/redaction, privacy-request and abuse suites run in each language including mixed-script and mixed-language input (links to REVIEW-01).", "All suites pass in each language; a failure blocks that language", "per-language security suites", "LG-08", "[DECISION]"),
        ("REQ-LANG-09", "Native-language human review", "A named native reviewer per language signs off interface text, Mo samples, interview questions and feedback and legal text.", "Signed review record per language", "human review protocol and sign-off", "LG-11,LG-12", "[DECISION]"),
        ("REQ-LANG-10", "Qualify legal and privacy translations before real-user access", "Terms, Privacy, AI-transparency and consent text reviewed by a qualified person in each language before any real-user access in that language.", "Signed legal translation qualification per language", "legal review record; version registry entries", "LG-10", "[DECISION]"),
        ("REQ-LANG-11", "Track readiness and quality separately per language", "A per-language readiness record (gate state, evidence date, SHA, sample size); no aggregate multilingual-ready claim.", "One status row per language per gate in the acceptance matrix", "consistency check against aggregate claims", "LG-13", "[DECISION]"),
        ("REQ-LANG-12", "Keep Platform Admin English-only for R1.0", "Admin stays English; no Admin translation in R1.0 and no candidate-content path through localisation.", "Admin catalogue stays English", "existing Admin invariants", "LG-14", "[DECISION]"),
        ("REQ-LANG-13", "No language is called production-qualified before its gates pass", "Public pages, documents and Admin must not claim a language is qualified until LG-01 to LG-14 pass for it; a locale that fails a mandatory gate is not activated for real users.", "Claims gate extended; per-language activation switch off until qualified", "claim-discipline test; owner review", "LG-13", "[DECISION]"),
        ("REQ-LANG-14", "Remove Russian from active Candidate language selection for R1.0", "Russian code is preserved where safe but Russian must not appear in Candidate language choices (it is an exposed eighth locale today; this change has NOT been made).", "Language selector, onboarding and settings offer exactly seven languages; Russian catalogue retained and tested", "frontend selectable-locale tests; scripts/eval_i18n_l10n.py updated", "LG-14", "[DECISION]"),
        ("REQ-LANG-15", "R1.3 languages: Mandarin, Hindi, Arabic", "Each needs new locale, prompt, safety, retrieval, accessibility, legal and native review work; Arabic needs RTL handling.", "A separate qualification plan per language approved by the owner", "plan documents", "LG-01..LG-14 (future)", "[DECISION]"),
        ("REQ-LANG-16", "Approve and qualify each proposed primary market individually", "The seven mappings are NOT individually approved qualifications. Each needs owner approval and source qualification (licence, authority, coverage) before use.", "Signed owner decision and a source approval register entry per market", "source approval register; coverage evidence", "LG-07", "[AWAITING]"),
    ]
    for id_, title, desc, accept, tests, gates, tag in spec:
        e = _row(id_, title, desc, "WP-08", "P1" if id_ != "REQ-LANG-15" else "P2", "FIX BEFORE R1.0", "R1.0", accept, tests, "Language-specific injection and PII handling; legal text accuracy",
                 "REQ-LANG-01 precedes 02 to 13; per-country approval (OD-LANG-02)", "NOT STARTED", "AWAITING_APPROVAL" if tag == "[AWAITING]" else "EXPLICIT_OWNER_DECISION", "LANGUAGE-DECISION", L, lang_gates=gates)
        if id_ == "REQ-LANG-15":
            e.update(disposition="DEFER TO NAMED RELEASE", release="R1.3", feature_gate="no zh/hi/ar locale is registered in src/locales.py")
        if id_ == "REQ-LANG-16":
            e.update(disposition="OWNER DECISION")
        out.append(e)
    return out


def cross_check(register: list[dict]) -> tuple[list[dict], list[dict]]:
    """Cross-check other matrices against the register. Returns (cross-check rows, NEW issue rows for unmapped open items)."""
    known: dict[str, str] = {}
    for i in register:
        for k in [i["original_id"]] + list(i.get("aliases") or []) + [str(i.get("id"))]:
            known[k] = i["original_id"]
    fam: dict[str, set[str]] = defaultdict(set)
    for i in register:
        if "." in i["original_id"]:
            fam[i["original_id"].split(".", 1)[0]].add(i["original_id"])
    idx = [(i["original_id"], _tok(i["title"] + " " + i["description"] + " " + str(i.get("remaining") or ""))) for i in register]

    def refs(text: str) -> list[str]:
        out = set()
        for k, o in known.items():
            if len(k) >= 3 and re.search(r"(?<![A-Za-z0-9.-])" + re.escape(k) + r"(?![A-Za-z0-9-])", text):
                out.add(o)
        for base, members in fam.items():
            if re.search(r"(?<![A-Za-z0-9.-])" + re.escape(base) + r"(?![A-Za-z0-9.-])", text):
                out.update(members)
        return sorted(out)

    def lexical(text: str) -> list[str]:
        t = _tok(text)
        sc = sorted(((len(t & s) / max(1, len(t)), o) for o, s in idx), reverse=True)
        return [o for sc_, o in sc[:2] if sc_ >= 0.6 and len(t) >= 2]

    rows: list[dict] = []
    new: list[dict] = []

    def add(source, sid, title, state, text, kind):
        mapped = refs(text)
        method = "explicit-reference" if mapped else ""
        if not mapped and kind == "open":
            mapped = lexical(title) or lexical(title + " " + text)
            method = "lexical-match" if mapped else ""
        if kind == "pass":
            rows.append(dict(source=source, id=sid, title=title, historical_state=state, handling="CLOSE WITH EVIDENCE (historical PASS, not re-opened, not upgraded)", mapped_issue_ids=mapped, method=method or "n/a"))
            return
        if mapped:
            rows.append(dict(source=source, id=sid, title=title, historical_state=state, handling="TRACKED by register issue(s)", mapped_issue_ids=mapped, method=method))
        else:
            tag = {"Acceptance ledger (current)": "AC", "Release acceptance matrix (P10B)": "REL", "P9 quality register (carried items)": "P9"}.get(source, "X")
            nid = f"XC-{tag}-{sid.strip('-')}"
            rows.append(dict(source=source, id=sid, title=title, historical_state=state, handling=f"NEW ISSUE {nid} (no register issue found)", mapped_issue_ids=[nid], method="none"))
            new.append(dict(id=nid, title=f"{source} {sid}: {title}"[:200], description=f"Open or accepted-limitation row in {source} with no matching register issue. Original text: {text[:400]}", wp="WP-15", priority="P2",
                            disposition="OWNER DECISION", release="R1.0", acceptance_criteria="Owner decides: track as an issue, accept as a documented limitation, or close with evidence", required_tests="per owner decision",
                            security_privacy_impact="unknown", dependencies="none", current_status=f"NEW - UNMAPPED ({state})", source=source, feature_gate="", origin="NEW"))

    led = (ROOT / "docs/capstone/CAPSTONE_ACCEPTANCE_LEDGER_CURRENT.md").read_text(encoding="utf-8")
    parts = re.split(r"(?m)^## (AC-\d+)\n", led)
    for n in range(1, len(parts), 2):
        body = parts[n + 1]
        disp = re.search(r"Current verified disposition:\*\* \*\*([A-Z ]+)\*\*", body)
        out = re.search(r"Outstanding qualification:\*\* (.*)", body)
        orig = re.search(r"Original requirement:\*\* (.*)", body)
        state = disp.group(1).strip() if disp else "UNKNOWN"
        add("Acceptance ledger (current)", parts[n], (orig.group(1) if orig else "")[:120], state, (out.group(1) if out else "") + " " + body[:600], "pass" if state == "PASS" else "open")
    rel = (ROOT / "docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md").read_text(encoding="utf-8")
    for m in re.finditer(r"(?m)^\| (R-\d+[A-Za-z]?) \|(.*)\|\s*$", rel):
        cells = [c.strip() for c in m.group(2).split("|")]
        res = cells[-2] if len(cells) >= 2 else "?"
        add("Release acceptance matrix (P10B)", m.group(1), cells[0], res, " ".join(cells), "pass" if res == "PASS" else "open")
    risk = (ROOT / "docs/capstone/capstone_risk_register.md").read_text(encoding="utf-8")
    for m in re.finditer(r"(?m)^\| (R-\d+) \|(.*)\|\s*$", risk):
        cells = [c.strip() for c in m.group(2).split("|")]
        rows.append(dict(source="Capstone risk register", id=m.group(1), title=cells[0][:120], historical_state="planning risk (no status column)", handling="RETAINED AS HISTORICAL PLANNING RISK; superseded by the issue register; no new issue",
                         mapped_issue_ids=refs(" ".join(cells)), method="reference-or-historical"))
    p9 = (ROOT / "docs/capstone/p9_quality_register.md").read_text(encoding="utf-8")
    sec = p9.split("## Carried open items", 1)[-1].split("\n## ", 1)[0]
    for m in re.finditer(r"(?m)^\| ([^|]+) \| ([^|]+) \|(.*)\|\s*$", sec):
        name = m.group(1).strip()
        if name in ("Item", "---") or set(name) <= set("-"):
            continue
        add("P9 quality register (carried items)", re.sub(r"\W+", "-", name)[:30], name, m.group(2).strip(), " ".join(m.groups()), "open")
    return rows, new


def build() -> dict:
    raw, register = load_register()
    # duplicate groups by meaning (lexical, same category, high overlap); IDs are never removed
    toks = [(i["original_id"], _tok(i["title"] + " " + i["description"]), i["category"]) for i in register]
    parent: dict[str, str] = {}
    for a in range(len(toks)):
        for b in range(a + 1, len(toks)):
            if toks[a][2] != toks[b][2]:
                continue
            ta, tb = toks[a][1], toks[b][1]
            if len(ta) >= 5 and len(tb) >= 5 and len(ta & tb) / len(ta | tb) >= 0.8:
                parent.setdefault(toks[b][0], toks[a][0])
    items = []
    for i in register:
        d = decide(i)
        wp = work_package(i)
        lang = wp == "WP-08"
        rec = dict(
            id=i["original_id"], origin="REGISTER", aliases=i.get("aliases") or [], title=i["title"], category=i["category"], wp=wp, priority=i["priority"],
            owner_role=WORK_PACKAGES[wp][1], dependencies=i.get("dependencies") or "none recorded", current_status=i["status"], historical_blocks_production=i.get("blocks_production"),
            acceptance_criteria=(i.get("closure_evidence") or i.get("remaining") or "not recorded"), required_tests=WP_TESTS[wp] + ("; " + i["closure_evidence"] if i.get("closure_evidence") and i["status"] != "CLOSED - VERIFIED" else ""),
            security_privacy_impact=i.get("security_privacy") or "not recorded", evidence_of_closure=(i.get("closure_evidence") if i["status"] == "CLOSED - VERIFIED" else "none yet"),
            duplicate_of=parent.get(i["original_id"], ""), language_programme=lang, language_gates=(language_gates_for(_blob(i)) if lang else ""),
            description=i["description"], provenance="HISTORICAL", origin_class="REGISTER-HISTORICAL", scope_class="ACADEMIC_ONLY" if i["original_id"] in ACADEMIC_ONLY else "PRODUCTION",
            test_evidence=(i.get("closure_evidence") if i["status"] == "CLOSED - VERIFIED" else "none recorded as passing; required tests are listed in required_tests"), proposed_implementation="",
            historical=i, **d,
        )
        items.append(rec)
    byid = {r["id"]: r for r in items}
    for r in items:  # a duplicate shares its canonical issue's disposition (same meaning, same decision)
        if (r["duplicate_of"] and r["disposition"] not in ("CLOSE WITH EVIDENCE", "OWNER DECISION")
                and byid[r["duplicate_of"]]["disposition"] not in ("CLOSE WITH EVIDENCE", "OWNER DECISION")):
            c = byid[r["duplicate_of"]]
            r.update(disposition=c["disposition"], release=c["release"], rule_id=c["rule_id"] + "+dup", feature_gate=c["feature_gate"], reason=f"duplicate of {c['id']}: {c['reason']}")
    xrows, xnew = cross_check(register)
    newreq = new_requirements() + xnew
    for e in newreq:
        e.setdefault("owner_role", WORK_PACKAGES[e["wp"]][1])
        e.setdefault("aliases", [])
        e.setdefault("category", "NEW")
        e.setdefault("duplicate_of", "")
        e.setdefault("evidence_of_closure", "none yet")
        e.setdefault("language_programme", e["wp"] == "WP-08")
        e.setdefault("language_gates", "")
        e.setdefault("reason", "owner-supplied or discovered requirement; rule set bypassed by explicit assignment")
        e.setdefault("rule_id", "NEW")
        e.setdefault("historical", None)
        e.setdefault("historical_blocks_production", "NEW")
        e.setdefault("provenance", "DISCOVERED_BY_CROSS_CHECK")
        e.setdefault("origin_class", "CROSS-CHECK")
        e.setdefault("scope_class", "PRODUCTION")
        e.setdefault("test_evidence", "none yet")
        e.setdefault("proposed_implementation", "")
        e.setdefault("description", e.get("title", ""))
    for r in items + newreq:
        r["release_basis"] = ("AGREED_RELEASE_TRAIN" if r["rule_id"].split("+")[0] in ("D-COM", "D-FL", "D-SPEECH", "D-INTL", "B1", "B2", "B3", "S1", "M1", "NEW", "C0", "O0", "U-RU", "A0") or r["origin"] == "NEW"
                              else "PROPOSED_PLACEMENT (no agreed theme; owner to confirm: OD-DEFER-PLACEMENT)")
    allitems = items + newreq
    summary = summarise(register, items, newreq, xrows)
    return dict(
        generated="2026-10-21", baseline_register=dict(file="docs/capstone/post_submission_deferred_issues.json", generated=raw["generated"], base_main_sha=raw["base_main_sha"], count=raw["count"]),
        disclaimer="All dispositions, releases, owners and work packages are PROPOSED by documented rules for owner review. No historical status, gate or closure evidence was changed.",
        dispositions=list(DISPOSITIONS), releases=list(RELEASES), release_themes=RELEASE_THEMES, work_packages={k: dict(name=v[0], owner_role=v[1]) for k, v in WORK_PACKAGES.items()},
        gate_constants=GATE_NAMES, summary=summary, cross_check=xrows, items=allitems,
        scope_proposals=dict(applied=False, evidence=EVIDENCE, reclassification={k: dict(proposed_release=v[0], capability=v[1], evidence=v[2]) for k, v in RECLASSIFICATION_PROPOSAL.items()},
                             withdrawn=RECLASSIFICATION_WITHDRAWN),
    )


def summarise(register, items, newreq, xrows) -> dict:
    active = [r for r in items if r["disposition"] != "CLOSE WITH EVIDENCE"]
    allitems = items + newreq
    def cnt(key, seq):
        return dict(Counter(r[key] for r in seq))
    by_rel_disp = defaultdict(lambda: defaultdict(int))
    for r in allitems:
        by_rel_disp[r["release"]][r["disposition"]] += 1
    dup = sum(1 for r in items if r["duplicate_of"])
    return dict(
        historical_issues=len(register), historical_closed=sum(1 for i in register if i["status"] == "CLOSED - VERIFIED"), historical_active=len(active),
        historical_production_blockers=sum(1 for i in register if i.get("blocks_production") == "YES"), historical_owner_decisions=sum(1 for i in register if i["status"] == "PENDING OWNER DECISION"),
        new_items=len(newreq), new_language_requirements=sum(1 for e in newreq if e["id"].startswith("REQ-LANG")), new_owner_requested_areas=sum(1 for e in newreq if e["id"].startswith("REQ-OWN")),
        new_demo_findings=sum(1 for e in newreq if e["id"].startswith("DEMO-")), new_cross_check_issues=sum(1 for e in newreq if e["id"].startswith("XC-")),
        prior_alias_merges=sum(len(i.get("aliases") or []) for i in register), duplicates_reconciled_this_pass=dup,
        disposition_counts=cnt("disposition", allitems), historical_disposition_counts=cnt("disposition", items),
        release_by_disposition={k: dict(v) for k, v in by_rel_disp.items()},
        r1_0_must_fix=sum(1 for r in allitems if r["disposition"] == "FIX BEFORE R1.0"), r1_0_must_verify=sum(1 for r in allitems if r["disposition"] == "VERIFY BEFORE R1.0"),
        owner_decisions=sum(1 for r in allitems if r["disposition"] == "OWNER DECISION"),
        deferred_by_release={rel: sum(1 for r in allitems if r["disposition"] == "DEFER TO NAMED RELEASE" and r["release"] == rel) for rel in DEFER_RELEASES},
        priority_of_r1_0_work=dict(Counter(r["priority"] for r in allitems if r["disposition"] in ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0"))),
        cross_check_rows=len(xrows), cross_check_sources=dict(Counter(x["source"] for x in xrows)),
        unmapped_issues=0,
        new_reviewer_findings=sum(1 for e in newreq if e["id"].startswith("REVIEW-")), new_release_scope_rows=sum(1 for e in newreq if e["id"].startswith("REL-R")), new_other_requirements=sum(1 for e in newreq if e["id"].startswith(("REQ-BETA", "REQ-CAND", "REQ-COV", "REQ-DEFER", "REQ-SCOPE"))),
        academic_only_items=sum(1 for r in allitems if r["scope_class"] == "ACADEMIC_ONLY"), unscheduled_owner_decisions=sum(1 for r in allitems if r["release"] == UNSCHEDULED),
        genuine_new_owner_decisions=sum(1 for r in newreq if r["disposition"] == "OWNER DECISION"), decision_register_entries=len(NEW_DECISIONS),
        r1_0_total_work=sum(1 for r in allitems if r["disposition"] in ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0")),
        by_release_total={rel: sum(1 for r in allitems if r["release"] == rel) for rel in list(RELEASES) + [UNSCHEDULED, "n/a"]},
        provenance_counts=dict(Counter(r["provenance"] for r in allitems)), origin_class_counts=dict(Counter(r["origin_class"] for r in allitems)),
        proposed_reclassification=dict(items=len(RECLASSIFICATION_PROPOSAL), withdrawn=len(RECLASSIFICATION_WITHDRAWN), applied=False,
                                       r1_0_fix_if_applied=sum(1 for r in allitems if r["disposition"] == "FIX BEFORE R1.0") - len(RECLASSIFICATION_PROPOSAL),
                                       r1_0_total_if_applied=sum(1 for r in allitems if r["disposition"] in ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0")) - len(RECLASSIFICATION_PROPOSAL)),
        previous_baseline=PREV_BASELINE,
        delta_vs_previous=dict(items=len(allitems) - PREV_BASELINE["items"],
                               r1_0_must_fix=sum(1 for r in allitems if r["disposition"] == "FIX BEFORE R1.0") - PREV_BASELINE["r1_0_must_fix"],
                               r1_0_must_verify=sum(1 for r in allitems if r["disposition"] == "VERIFY BEFORE R1.0") - PREV_BASELINE["r1_0_must_verify"],
                               owner_decisions=sum(1 for r in allitems if r["disposition"] == "OWNER DECISION") - PREV_BASELINE["owner_decisions"],
                               deferred=sum(1 for r in allitems if r["disposition"] == "DEFER TO NAMED RELEASE") - PREV_BASELINE["deferred"], new_items=len(newreq) - PREV_BASELINE["new_items"]),
    )


def validate(doc: dict) -> list[str]:
    """Machine check. Returns a list of problems (empty = valid)."""
    errs: list[str] = []
    raw, register = load_register()
    items = doc["items"]
    ids = [r["id"] for r in items]
    if len(ids) != len(set(ids)):
        errs.append("duplicate ids in reconciliation")
    byid = {r["id"]: r for r in items}
    if len(register) != raw["count"]:
        errs.append("register count field disagrees with its rows")
    for i in register:  # history preserved verbatim, every register id present
        r = byid.get(i["original_id"])
        if r is None:
            errs.append(f"{i['original_id']}: missing from reconciliation")
            continue
        if r["historical"] != i:
            errs.append(f"{i['original_id']}: historical record was altered")
        if r["current_status"] != i["status"]:
            errs.append(f"{i['original_id']}: status silently changed")
        closed = i["status"] == "CLOSED - VERIFIED"
        if closed and (r["disposition"] != "CLOSE WITH EVIDENCE" or not str(i.get("closure_evidence") or "").strip() or r["evidence_of_closure"] != i.get("closure_evidence")):
            errs.append(f"{i['original_id']}: closed issue lost its disposition or closure evidence")
        if i["status"] == "PENDING OWNER DECISION" and r["disposition"] != "OWNER DECISION":
            errs.append(f"{i['original_id']}: pending owner decision lost its OWNER DECISION disposition")
        if not closed and r["disposition"] == "CLOSE WITH EVIDENCE":
            errs.append(f"{i['original_id']}: active issue marked closed")
    need = ("id", "title", "description", "wp", "priority", "owner_role", "dependencies", "current_status", "acceptance_criteria", "required_tests", "test_evidence", "security_privacy_impact", "disposition", "release", "rule_id", "provenance", "origin_class", "scope_class")
    for r in items:
        for k in need:
            if not str(r.get(k) or "").strip():
                errs.append(f"{r['id']}: empty field {k}")
        d, rel = r["disposition"], r["release"]
        if d not in DISPOSITIONS:
            errs.append(f"{r['id']}: invalid disposition {d!r}")
            continue
        if r["wp"] not in WORK_PACKAGES:
            errs.append(f"{r['id']}: invalid work package")
        if d in ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0") and rel != "R1.0":
            errs.append(f"{r['id']}: {d} must be release R1.0")
        if d == "DEFER TO NAMED RELEASE":
            if rel not in DEFER_RELEASES:
                errs.append(f"{r['id']}: deferral needs a named later release")
            if not str(r.get("feature_gate") or "").strip():
                errs.append(f"{r['id']}: deferral without a feature gate or reason (a safety/privacy dependency may not be deferred while its feature stays enabled)")
        if d == "OWNER DECISION" and rel not in RELEASES and rel != UNSCHEDULED:
            errs.append(f"{r['id']}: owner decision lacks a proposed release")
        if rel == UNSCHEDULED and d != "OWNER DECISION":
            errs.append(f"{r['id']}: only an owner decision may be unscheduled")
        if r["scope_class"] == "ACADEMIC_ONLY" and d in ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0"):
            errs.append(f"{r['id']}: an academic-only item cannot be an R1.0 production requirement")
        if d == "CLOSE WITH EVIDENCE" and not str(r.get("evidence_of_closure") or "").strip():
            errs.append(f"{r['id']}: closure without evidence")
    # recovered owner requirements and reviewer findings
    for n in range(1, 6):
        rv = byid.get(f"REVIEW-0{n}")
        if rv is None or rv["origin_class"] != "TURING-REVIEW" or rv["provenance"] != "REVIEWER_FINDING" or rv["disposition"] != "FIX BEFORE R1.0" or not rv.get("requirements_list"):
            errs.append(f"REVIEW-0{n}: missing or not a complete reviewer-finding requirement")
    if any(r["id"].startswith("RF-") for r in items):
        errs.append("demo findings must be DEMO-nn, never RF-nn (reviewer findings are REVIEW-nn)")
    for n in range(1, 6):
        if f"DEMO-0{n}" not in byid or byid[f"DEMO-0{n}"]["origin_class"] != "DEMO-OBSERVED":
            errs.append(f"DEMO-0{n} missing or mislabelled")
    for n in range(1, 9):
        o = byid.get(f"REQ-OWN-0{n}")
        if o is None or o["disposition"] != "FIX BEFORE R1.0" or o["release"] != "R1.0" or not o.get("requirements_list") or "not in repository" in o["current_status"].lower():
            errs.append(f"REQ-OWN-0{n}: not a specified, testable R1.0 requirement")
    if list(doc.get("releases", [])) != list(RELEASES) or set(doc.get("release_themes", {})) != set(RELEASES):
        errs.append("the agreed release train R1.0 to R2.0 is not fully present")
    sp = doc.get("scope_proposals") or {}
    if sp.get("applied") is not False:
        errs.append("the scope reclassification is a proposal and must be marked not applied")
    for k, v in (sp.get("reclassification") or {}).items():
        r = byid.get(k)
        if r is None or r["origin"] != "REGISTER":
            errs.append(f"proposed reclassification of unknown register item {k}")
            continue
        if r["disposition"] != "FIX BEFORE R1.0" or r["release"] != "R1.0":
            errs.append(f"{k}: the proposal must not be applied (disposition changed)")
        if v["proposed_release"] not in RELEASES[1:] or not v["evidence"] or any(e not in EVIDENCE for e in v["evidence"]):
            errs.append(f"{k}: proposal lacks a later release or valid evidence")
    for k in (sp.get("withdrawn") or {}):
        if byid.get(k) is None or byid[k]["release"] != "R1.0" or k in (sp.get("reclassification") or {}):
            errs.append(f"{k}: withdrawn item must stay in R1.0 and out of the proposal")
    for rel in RELEASES[1:]:
        if not any(r["release"] == rel for r in items):
            errs.append(f"release {rel} has no traced requirement")
    if "REQ-LANG-14" not in byid or byid["REQ-LANG-14"]["provenance"] != "EXPLICIT_OWNER_DECISION":
        errs.append("Russian removal must be recorded as an explicit owner decision")
    active = [r for r in items if r["origin"] == "REGISTER" and r["current_status"] != "CLOSED - VERIFIED"]
    s = doc["summary"]
    if (s["historical_issues"], s["historical_closed"], s["historical_active"]) != (len(register), sum(1 for i in register if i["status"] == "CLOSED - VERIFIED"), len(active)):
        errs.append("summary counts disagree with the register")
    if s["unmapped_issues"] != 0 or any(not r.get("disposition") for r in items):
        errs.append("unmapped issues")
    for x in doc["cross_check"]:
        if x["handling"].startswith("TRACKED") and not x["mapped_issue_ids"]:
            errs.append(f"cross-check {x['id']}: tracked without an issue")
        for m in x["mapped_issue_ids"]:
            if m not in byid:
                errs.append(f"cross-check {x['id']}: mapped to unknown {m}")
    # R1.0 claims: gates behind every deferral must really be disabled
    for mod, name in GATE_CONSTANTS:
        try:
            if getattr(importlib.import_module(mod), name) is not False:
                errs.append(f"gate {mod}.{name} is not False; deferrals that rely on it are invalid")
        except Exception as exc:  # noqa: BLE001
            errs.append(f"gate {mod}.{name} unreadable: {exc}")
    return errs


def render_traceability(doc: dict) -> str:
    s = doc["summary"]
    L = ["# Master Requirements Traceability (Production Roadmap V2.2)", "",
         "**Status:** PROPOSED baseline for owner review, generated 2026-10-21 by `scripts/production/reconcile_issues.py`. Nothing here upgrades a historical status or gate. The full per-item record (acceptance criteria, required tests, security/privacy impact, dependencies, evidence of closure, the verbatim historical row) is in [`PRODUCTION_ISSUE_RECONCILIATION.json`](PRODUCTION_ISSUE_RECONCILIATION.json); the tables below are the readable index.", "",
         f"Baseline: {s['historical_issues']} register issues ({s['historical_closed']} closed, {s['historical_active']} active) + {s['new_items']} new items = {s['historical_issues'] + s['new_items']} traced rows. Unmapped: **{s['unmapped_issues']}**.", "",
         "Dispositions: FIX BEFORE R1.0, VERIFY BEFORE R1.0, OWNER DECISION, DEFER TO NAMED RELEASE (only while the feature stays disabled), CLOSE WITH EVIDENCE.", "", "## Work packages", "", "| WP | Name | Owner role (person not yet named) | Items |", "|---|---|---|---|"]
    cnt = Counter(r["wp"] for r in doc["items"])
    for k, v in doc["work_packages"].items():
        L.append(f"| {k} | {v['name']} | {v['owner_role']} | {cnt.get(k, 0)} |")
    L += ["", "## Rules (proposed)", "", "| Rule | Meaning |", "|---|---|", "| C0 | Historically CLOSED - VERIFIED: closure evidence preserved |", "| O0 | Historically PENDING OWNER DECISION: owner decides; release shown is proposed if approved |",
          "| B1 | Blocks any production release and is not in an R1.0-excluded feature family: FIX (or VERIFY when never run/verified/human-reviewed) before R1.0 |", "| B2 | Safety/privacy/public-claim relevance for an enabled R1.0 feature: VERIFY before R1.0 |",
          "| B3 | Production impact unknown at P0/P1: VERIFY before R1.0 |", "| S1 | AI-safety (D), privacy (F) or legal (K) item at P0-P2 or with a security/privacy impact: VERIFY before R1.0, never deferred while its feature is enabled |", "| M1 | Source qualification for one of the seven R1.0 markets: VERIFY before R1.0 |", "| D-GEN | No production impact, no enabled-feature dependency, no agreed release theme: R1.1 (placement proposed, OD-DEFER-PLACEMENT) |", "| D-ADM | As D-GEN but Admin-related: R1.2 (placement proposed) |", "| D-COM | Commercial activation and plan expansion: R1.1 while billing gates stay False |",
          "| D-INT | Later integrations: R1.2 (alerts), R1.5 (market data) or R1.7 (enterprise) while not configured |", "| D-INTL | Additional-country evidence R1.5, compensation R1.6, while Compensation V2 and international sources stay disabled |", "| D-SPEECH | Server speech and voice practice: R1.4 while governed speech gates stay False |",
          "| U-RU | Russian: excluded from R1.0; any activation is a separate future owner decision (UNSCHEDULED) |", "| A0 | Academic-only capstone-submission task: not a production dependency; owner confirms retirement (UNSCHEDULED) |", "| D-FL | Mandarin, Hindi, Arabic: R1.3 |", "| +dup | Same meaning as an earlier issue: shares its disposition |", ""]
    order = {d: n for n, d in enumerate(DISPOSITIONS)}
    for rel in list(RELEASES) + [UNSCHEDULED, "n/a"]:
        rows = [r for r in doc["items"] if r["release"] == rel]
        if not rows:
            continue
        L += [f"## {rel}" + (f": {RELEASE_THEMES[rel]}" if rel in RELEASE_THEMES else (": unscheduled owner decisions (academic-only retirement, future Russian decision)" if rel == UNSCHEDULED else ": closed items (evidence preserved)")), "", f"{len(rows)} items.", "", "| ID | Title | Origin | Disposition | WP | Prio | Status | Rule |", "|---|---|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda x: (order[x["disposition"]], x["priority"], x["id"])):
            t = r["title"].replace("|", "/")[:90]
            L.append(f"| {r['id']} | {t} | {r['origin_class']} | {r['disposition']} | {r['wp']} | {r['priority']} | {r['current_status'][:60]} | {r['rule_id']} |")
        L.append("")
    L += ["## Recovered owner requirements and reviewer findings (detail)", "", "These rows are specified from `OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md`. Each is a separate, testable requirement; the numbered criteria are the acceptance criteria.", ""]
    for r in doc["items"]:
        if r.get("requirements_list"):
            L += [f"### {r['id']} {r['title']}", "", f"Provenance: {r['provenance']}; WP {r['wp']}; priority {r['priority']}; release {r['release']}; status: {r['current_status']}.", ""] + [f"- {c}" for c in r["requirements_list"]] + ["", f"Required tests: {r['required_tests']}.", f"Dependencies: {r['dependencies']}.", ""]
    L += ["## Cross-check against the other matrices", "", f"{len(doc['cross_check'])} rows from: " + ", ".join(f"{k} ({v})" for k, v in s["cross_check_sources"].items()) + ".", "", "| Source | ID | Historical state | Handling | Mapped issue(s) |", "|---|---|---|---|---|"]
    for x in doc["cross_check"]:
        if x["handling"].startswith("CLOSE"):
            continue
        L.append(f"| {x['source']} | {x['id']} | {x['historical_state']} | {x['handling']} | {', '.join(x['mapped_issue_ids'][:4])} |")
    L += ["", f"Historical PASS rows ({sum(1 for x in doc['cross_check'] if x['handling'].startswith('CLOSE'))}) are kept as CLOSE WITH EVIDENCE and not re-opened; their evidence stays in the source documents.", ""]
    return "\n".join(L)


def render_dashboard(doc: dict) -> str:
    s = doc["summary"]
    pb, dl = s["previous_baseline"], s["delta_vs_previous"]
    items = doc["items"]
    r10 = [r for r in items if r["disposition"] in ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0")]
    def sg(n):
        return f"{n:+d}"
    L = ["# Release Blocker Dashboard (R1.0, 30 November 2026, free private beta)", "", "**Status:** corrected 2026-10-21 against the owner's authoritative requirements. Counts come from `PRODUCTION_ISSUE_RECONCILIATION.json` and are checked by `scripts/production/reconcile_issues.py check`. Dispositions remain PROPOSED for owner review.", "",
         "## Totals", "", "| Measure | Count |", "|---|---|", f"| Historical issues (all preserved with original IDs) | {s['historical_issues']} |", f"| Historically closed (evidence preserved) | {s['historical_closed']} |", f"| Historically active | {s['historical_active']} |",
         f"| Historical production blockers | {s['historical_production_blockers']} |", f"| Historical pending owner decisions | {s['historical_owner_decisions']} |",
         f"| New items | {s['new_items']}: reviewer findings {s['new_reviewer_findings']}, owner capabilities {s['new_owner_requested_areas']}, language requirements {s['new_language_requirements']}, other owner requirements {s['new_other_requirements']}, demo-observed findings {s['new_demo_findings']}, later-release scope rows {s['new_release_scope_rows']}, cross-check {s['new_cross_check_issues']} |",
         f"| Traced rows in total | {len(items)} |", f"| Earlier alias merges recorded in the register | {s['prior_alias_merges']} |", f"| Duplicates reconciled this pass (by meaning, IDs kept) | {s['duplicates_reconciled_this_pass']} |",
         f"| **R1.0 must-fix** | **{s['r1_0_must_fix']}** |", f"| **R1.0 must-verify** | **{s['r1_0_must_verify']}** |", f"| Items with an OWNER DECISION disposition | {s['owner_decisions']} (of which unscheduled {s['unscheduled_owner_decisions']}, academic-only {s['academic_only_items']}) |",
         f"| Genuinely open owner decisions in the register | {s['decision_register_entries']} new, plus the {s['historical_owner_decisions']} historical |", "| Deferred | " + ", ".join(f"{k}: {v}" for k, v in s["deferred_by_release"].items() if v) + " |", f"| Unmapped issues | **{s['unmapped_issues']}** |", ""]
    L += ["## Change since the previous reconciliation (PR #211 at `" + pb["commit"] + "`)", "", "| Measure | Previous | Now | Change |", "|---|---|---|---|",
          f"| Traced rows | {pb['items']} | {len(items)} | {sg(dl['items'])} |", f"| New items | {pb['new_items']} | {s['new_items']} | {sg(dl['new_items'])} |", f"| R1.0 must-fix | {pb['r1_0_must_fix']} | {s['r1_0_must_fix']} | {sg(dl['r1_0_must_fix'])} |",
          f"| R1.0 must-verify | {pb['r1_0_must_verify']} | {s['r1_0_must_verify']} | {sg(dl['r1_0_must_verify'])} |", f"| OWNER DECISION disposition | {pb['owner_decisions']} | {s['owner_decisions']} | {sg(dl['owner_decisions'])} |", f"| Deferred | {pb['deferred']} | {sum(s['deferred_by_release'].values())} | {sg(dl['deferred'])} |", "",
          "Why the numbers moved, not forced to match the old totals:", "", "- The five reviewer findings, eight owner capabilities, the beta, candidate, coverage and deferral-verification requirements and the five demo findings were added as specified R1.0 requirements; REQ-OWN-01 to 08 left OWNER DECISION and became FIX BEFORE R1.0 (this raises must-fix and lowers owner decisions).",
          "- The 19 earlier open decisions shrank to the genuinely open ones: decisions the owner already made (languages, Russian, R1.3, release train, requirement text, reviewer findings) became requirements.",
          "- Russian items moved from a deferral to OWNER DECISION (UNSCHEDULED), because the owner made later activation a separate future decision, not an automatic R2.0 commitment.",
          "- Six historical capstone-submission tasks were reclassified ACADEMIC_ONLY and moved to OWNER DECISION (UNSCHEDULED) pending confirmation of retirement; they no longer count as production work.",
          "- Deferrals were re-routed from the earlier invented R1.1 to R2.0 themes onto the agreed train: commercial to R1.1, speech to R1.4, additional-country evidence to R1.5, compensation to R1.6, with items that fit no agreed theme placed in R1.1 (R1.2 for Admin) as a proposal.", ""]
    pr = s["proposed_reclassification"]
    L += ["## Proposed R1.0 scope reclassification (PROPOSED, NOT APPLIED)", "", f"{pr['items']} of 12 candidates pass the proof that their capability is inaccessible in the R1.0 Candidate API and UI; {pr['withdrawn']} fail it and stay in R1.0. If the owner confirms, R1.0 must-fix would be {pr['r1_0_fix_if_applied']} and fix plus verify {pr['r1_0_total_if_applied']}. Evidence and per-item detail: `execution/R1_SCOPE_RECLASSIFICATION_PROPOSAL.md`. Nothing is applied until the owner confirms (OD-US-CONTENT).", ""]
    L += ["## Totals by release (all dispositions)", "", "| Release | Items | Theme |", "|---|---|---|"] + [f"| {rel} | {s['by_release_total'].get(rel, 0)} | {RELEASE_THEMES[rel][:110]} |" for rel in RELEASES] + [f"| {UNSCHEDULED} | {s['by_release_total'].get(UNSCHEDULED, 0)} | owner decisions with no release yet |", f"| n/a (closed) | {s['by_release_total'].get('n/a', 0)} | closure evidence preserved |", ""]
    L += ["## R1.0 work by priority", "", "| Priority | Items |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(s["priority_of_r1_0_work"].items())] + [""]
    L += ["## R1.0 work by work package", "", "| WP | Fix | Verify | Owner decisions |", "|---|---|---|---|"]
    for k, v in doc["work_packages"].items():
        f = sum(1 for r in items if r["wp"] == k and r["disposition"] == "FIX BEFORE R1.0")
        ve = sum(1 for r in items if r["wp"] == k and r["disposition"] == "VERIFY BEFORE R1.0")
        o = sum(1 for r in items if r["wp"] == k and r["disposition"] == "OWNER DECISION")
        L.append(f"| {k} {v['name']} | {f} | {ve} | {o} |")
    L += ["", "## Capacity warning", "", f"{len(r10)} items must be fixed or verified before R1.0 on 30 November 2026. The date is the owner's target; safety, privacy, licensing and operational gates are not waived to meet it. Many items need people not yet named (reviewers, native reviewers, legal qualifiers) or an authorised hosted environment. OD-SCOPE-01 asks the owner what happens if a mandatory gate is not met: delay, remove the feature from scope, or keep it disabled.", "",
          "## R1.0 P0 items", "", "| ID | Title | Origin | Disposition | WP |", "|---|---|---|---|---|"]
    for r in sorted((r for r in r10 if r["priority"] == "P0"), key=lambda x: x["id"]):
        L.append(f"| {r['id']} | {r['title'].replace('|', '/')[:90]} | {r['origin_class']} | {r['disposition']} | {r['wp']} |")
    L += ["", "## Gates that keep deferred features disabled", ""] + [f"- `{g}` must be False" for g in doc["gate_constants"]] + [""]
    return "\n".join(L)


NEW_DECISIONS = [  # (id, decision, detail, proposed release, type)
    ("OD-SCOPE-01", "What happens if a mandatory R1.0 gate is not met by 30 November 2026", "The date is the owner's target and safety, privacy, licensing and operational gates are not waived. If a gate is not met: delay R1.0, remove the affected feature from scope, or keep it disabled. Phase 00 PROPOSES (not approved) a restricted free private beta of scope tiers T0 to T2 (small capped invitation-only cohort, languages and markets activated only where gates pass, Admin dashboards, plan editor and report builder moved to R1.2) and a capacity-based minimum safe beta (T0, T1 and journey reliability) as an alternative; the computed effort needs roughly 9 to 15 and 6 to 10 parallel streams respectively. See execution/DELIVERY_SCHEDULE.md and execution/PHASE_00_EXIT_REPORT.md. The owner supplies the real capacity.", "R1.0", "AWAITING"),
    ("OD-LANG-02", "Approve each proposed primary market individually", "Ireland, Germany, Spain, Italy, Portugal, France, Netherlands are proposals only; none is an approved country qualification. Each needs owner approval and source qualification (licence, authority, coverage).", "R1.0", "AWAITING"),
    ("OD-LANG-03", "Name the native-language reviewer for each of the seven languages", "No reviewer is named; needed before LG-11.", "R1.0", "AWAITING"),
    ("OD-LANG-04", "Name the legal and privacy translation qualifier(s)", "Needed before real-user access in each language (LG-10).", "R1.0", "AWAITING"),
    ("OD-RU-FUTURE", "Whether and when Russian is ever activated", "Russian is excluded from R1.0; any later activation is a separate decision, not an automatic R2.0 commitment.", "UNSCHEDULED", "AWAITING (future)"),
    ("OD-HOSTED", "Authorise and choose the hosted environment", "Secure hosting is R1.0 scope; the provider, region and approval to create a hosted staging and production environment are not decided (EX-12).", "R1.0", "AWAITING"),
    ("OD-BUDGET", "Approve a bounded live-evaluation and live-provider budget for qualification", "Native-review samples, live multilingual Mo checks, semantic embedding builds and a larger RAGAS run need an explicit budget; the EUR 10 capstone demonstration budget is not reusable.", "R1.0", "AWAITING"),
    ("OD-GATE-THRESHOLDS", "Approve numeric thresholds for the quality and safety gates", "Injection detection and false-positive rates (REVIEW-01), retrieval quality (REVIEW-04), latency and availability targets and human-rating thresholds need owner-approved numbers before the corpora are frozen. Proposals will be made, not assumed.", "R1.0", "AWAITING"),
    ("OD-PLAN-ENFORCE", "Which entitlements are enforced during the free beta", "Basic and Premium are both free beta tiers. Decide whether the history window and model-profile gating (currently disabled by code constants) stay disabled or are enforced for the beta; enabling either changes a gate constant that the reconciliation checks.", "R1.0", "AWAITING"),
    ("OD-ADMIN-NAV", "Confirm the Admin navigation groups", "The owner suggested Command Center; Customers and Workspaces; Products and Commercial; AI and Knowledge; Insights and Operations; Governance and Settings.", "R1.0", "AWAITING"),
    ("OD-BULK-ACTIONS", "Which restricted bulk user actions are permitted", "The owner asked for carefully restricted bulk actions; the permitted set is not defined.", "R1.0", "AWAITING"),
    ("OD-REPORT-EXPORT", "Which export formats the reports support", "The owner asked for export in supported formats; the set is not defined.", "R1.0", "AWAITING"),
    ("OD-WS-TRANSFER", "Workspace ownership transfer rules", "Safe transfer is required; the acceptance procedure and constraints are not defined.", "R1.0", "AWAITING"),
    ("OD-INVITE", "Invitation mechanism for the private beta", "Invitation-only registration is decided; whether it uses invitation codes, an email allow-list or another mechanism is not.", "R1.0", "AWAITING"),
    ("OD-MALWARE", "Select the real malware-scanning provider for user uploads", "Genuine fail-closed scanning is required (the fake scanner is development-only); the product choice and hosting are not decided.", "R1.0", "AWAITING"),
    ("OD-COVERAGE", "Approve the separate frozen R1.0 beta-scope coverage measure", "The historical 95% gate (386 of 412 against 392, FAIL) is preserved unchanged; a separate measure for the enabled beta scope and licensed markets needs approval.", "R1.0", "AWAITING"),
    ("OD-ACADEMIC-01", "Confirm retirement of the academic-only capstone-submission tasks", "Six historical items concern the capstone submission only (see traceability); they are not production dependencies. They are retired only on the owner's confirmation; none is silently closed.", "UNSCHEDULED", "AWAITING"),
    ("OD-EMBED", "Choose the production embedding provider and model", "Phase 00 options: OpenAI embeddings directly, an EU-hosted OpenAI-compatible endpoint, or a self-hosted multilingual model; the choice needs a frozen seven-language retrieval comparison, a data-processing review and a budget. Production must refuse the lexical hash embedder (REVIEW-04).", "R1.0", "AWAITING"),
    ("OD-US-CONTENT", "Whether US-sourced content (O*NET, BLS) is enabled in the EU beta", "The curated corpus is US-centred while the R1.0 markets are EU. Decide whether US content stays enabled for candidates, is limited to labelled general guidance, or is disabled; and whether the US occupational measurement and alias reviews (BL-5, BL-6 series, BL-7, BL-9) and Compensation V2 authorisation (BL-12) move out of R1.0 (proposed in Phase 00 package 00B).", "R1.0", "AWAITING"),
    ("OD-DEFER-PLACEMENT", "Confirm placement of items that fit no agreed release theme", "Items that are neither blockers nor part of an agreed release theme are placed in R1.1 (or R1.2 for Admin) as a proposal.", "R1.1", "AWAITING"),
]

LANG_NAMES = [("en", "English", "Ireland"), ("de", "German", "Germany"), ("es", "Spanish", "Spain"), ("it", "Italian", "Italy"), ("pt", "Portuguese", "Portugal"), ("fr", "French", "France"), ("nl", "Dutch", "Netherlands")]
GATES = [
    ("LG-01", "Locale audit complete", "Catalogue, Mo, interview, report, legal and email text inventoried; missing/unreviewed counts recorded"),
    ("LG-02", "Interface text complete", "No missing keys, no English leak in chrome, protected slogan unchanged"),
    ("LG-03", "Candidate journeys pass", "All candidate surfaces work end to end in the language"),
    ("LG-04", "Prompts and policies verified", "Grounding, safety, coaching-style and language directives behave; no policy bypass by language"),
    ("LG-05", "Interview quality validated", "Questions, scoring invariance, feedback and explanations reviewed"),
    ("LG-06", "Multilingual RAG and attribution", "Retrieval, citation and abstention evaluated; no invented source translation"),
    ("LG-07", "Language never sets the country", "Geography unchanged by language; each market individually approved and source-qualified"),
    ("LG-08", "Injection, security and privacy suites", "Language-specific and mixed-language suites pass"),
    ("LG-09", "Story Bank and Workspaces", "Flows verified with owner isolation intact"),
    ("LG-10", "Legal and privacy translation qualified", "Qualified review signed before real-user access"),
    ("LG-11", "Native-language human review", "Named reviewer sign-off on UI, Mo samples, interview text"),
    ("LG-12", "Mo language ownership", "Mo-voiced and deterministic text in the conversation language; interface language owns only chrome"),
    ("LG-13", "Readiness tracked, no aggregate claim", "Per-language status maintained; no production-qualified claim before all gates"),
    ("LG-14", "Boundaries", "Admin English-only; Russian not in active selection; zh/hi/ar not registered"),
]

PRODUCTION_GATES = [  # (id, name, measurable requirement, evidence, state)
    ("PG-01", "Secure hosted deployment", "Hosted staging and production exist on an owner-authorised provider: TLS and HSTS verified, secrets only in the managed store, CORS fail-closed, no development bypass headers accepted, hosted rehearsal repeated from a clean checkout", "Rehearsal record at the release SHA; scripts/eval_hosting_readiness.py", "NOT RUN (OD-HOSTED)"),
    ("PG-02", "Identity and account lifecycle", "Invitation-only registration enforced server-side; live verification email and password recovery round trip; sessions revoked on deactivation; account closure and deletion complete; Google sign-in validated or disabled", "Live round trip under owner authorisation; auth, invitation and deletion suites", "NOT RUN (REQ-BETA-01 not started)"),
    ("PG-03", "Injection defence and tool safety", "REVIEW-01 R1 to R6 complete: labelled corpus including direct, indirect, multilingual, encoded and retrieved-document attacks; detection and benign false-positive rates reported per language and above the owner-approved thresholds on a frozen held-out set (OD-GATE-THRESHOLDS); injection-risk score on every RetrievalResult; high-risk chunks excluded before context; tool calls re-authorised before side effects; no cross-user disclosure", "Held-out corpus run in CI; tool-authorization and cross-user negative tests", "NOT MET (heuristics only)"),
    ("PG-04", "Privacy, legal and data rights", "Privacy requests, export, deletion and retention verified; legal documents qualified in each offered language before real-user access; third-party provider data handling reviewed (K-PROVIDER); no GDPR or legal-compliance claim without qualified review", "Counsel sign-off per language; privacy suites", "NOT MET (engineering drafts)"),
    ("PG-05", "Persistent Knowledge Sources and embedding/index integrity", "REQ-OWN-05 K1 to K9 and REVIEW-04 R1 to R7 complete: sources survive restart, redeployment and separate-environment restore; manifest records embedding identity and checksums; mismatch detected and refused; no silent hash-embedding fallback in production; genuine malware scanning; alerts", "Restart, redeploy and restore drills; manifest and mismatch tests; retrieval and citation provenance tests", "NOT MET"),
    ("PG-06", "Candidate end-to-end reliability", "REQ-CAND-01: a real browser journey per language passes against a staging stack, including Start interview; provider outage yields an accurate recoverable message; REVIEW-05 streaming with cancellation works and the synchronous fallback is tested; availability and latency targets (OD-GATE-THRESHOLDS) met over a rehearsal", "Playwright journeys; outage simulation; SSE contract tests", "NOT RUN"),
    ("PG-07", "Independent human AI evaluation", "Named independent reviewers rate a frozen sample of interview questions, feedback and Mo answers per language against a written rubric; results reported with sample size; RAGAS is secondary and never presented as human-verified", "Signed rating records; blinded protocol results", "NOT MET (no reviewer named; AC-24 PARTIAL; human-qualified coverage 0 of 412)"),
    ("PG-08", "Admin 2.0 functionality", "REQ-OWN-01, 02, 03, 04, 08 complete: navigation, Command Center, plans, users, reports; permission matrix and route invariant unchanged; Admin still has no path to private candidate content", "Admin Playwright specs; permission matrix; sentinel tests", "PARTIAL foundations; Admin 2.0 NOT MET"),
    ("PG-09", "Observability, resilience, backup, restore and rollback", "Monitoring and alerting live for API, worker, indexing and provider health; backup and restore drilled for database, files and indexes; rollback of a release and of a prompt or plan version rehearsed; incident process documented and tested", "Drill records; alert tests; runbook rehearsal", "NOT RUN"),
    ("PG-10", "Deferred and paid features disabled", "Every gate constant in `gate_constants` is False; for each gated family a test proves the UI entry and the API route are unreachable (REQ-DEFER-01); no payment route is reachable; Russian is absent from active selection", "reconcile_issues.py check; consolidated UI plus API inaccessibility suite", "PARTIAL: constants checked False; UI/API suite not written; Russian still exposed"),
    ("PG-11", "Complete issue reconciliation", "Every historical and new item has a valid disposition and release; zero unmapped; history, closure evidence and failed historical gates preserved verbatim", "reconcile_issues.py check and tests", "MET (machine-checked)"),
    ("PG-12", "Prompt versioning, provenance and registry parity", "REVIEW-02 R1 to R7 and REVIEW-03 R1 to R6 complete: versioned prompt assets with declared versions and hashes; effective versions recorded on runs and evaluations; rollback without code change; one authoritative tool catalogue with parity tests and an unchanged tool set", "Loader, rollback, parity and attribution tests", "NOT MET"),
    ("PG-13", "Story Bank and Workspaces", "REQ-OWN-06 and REQ-OWN-07 acceptance journeys pass in the browser, including restart persistence and immediate revocation; authorization verified at the API boundary; verified in all seven languages (LG-09)", "Playwright journeys; API authorization tests", "PARTIAL foundations; journeys NOT RUN"),
    ("PG-14", "Reports and safe analytics", "REQ-OWN-04 complete: every metric traceable to a query and denominator; small-cohort suppression; missing data never shown as zero; custom builder accepts only registered metrics and dimensions; no arbitrary SQL; exports permissioned", "Metric tests; suppression tests; builder guard test", "PARTIAL foundations; NOT MET"),
    ("PG-15", "Free beta operational acceptance", "Invited beta users can register, practise and recover from errors; support process, abuse handling, data-rights handling and on-call ownership defined; no payment taken; owner signs a go/no-go with the evidence at one SHA", "Owner go/no-go record; beta runbook rehearsal", "NOT RUN"),
]


def render_owner_decisions(doc: dict) -> str:
    items = doc["items"]
    L = ["# Owner Decision Register (Production Roadmap V2.2, corrected)", "", "**Status:** corrected 2026-10-21 against the owner's authoritative requirements (`OWNER_REQUIREMENTS_SOURCE_OF_TRUTH_V2_2.md`). Only decisions that are genuinely still awaiting the owner are listed as open. Decisions the owner has already made (languages, Russian exclusion, R1.3 languages, release train, free invitation-only beta, English-only Admin, Basic/Premium as free beta tiers, the owner-requested capabilities and the five reviewer findings) are **requirements**, not open decisions, and are no longer listed here. Earlier open items that were resolved by the recovered text: OD-LANG-01, OD-LANG-05, OD-LANG-06, OD-REQ-TEXT, OD-REVIEW-FINDINGS, OD-RELEASE-TRAIN.", "",
         "## Genuinely open decisions", "", "| ID | Decision | Detail | Release | Type |", "|---|---|---|---|---|"]
    for id_, t, d, rel, typ in NEW_DECISIONS:
        L.append(f"| {id_} | {t} | {d.replace('|', '/')} | {rel} | {typ} |")
    hist = [r for r in items if r["origin"] == "REGISTER" and r["current_status"] == "PENDING OWNER DECISION"]
    L += ["", f"## Historical pending owner decisions ({len(hist)}, preserved with their register IDs)", "", "| ID | Decision | Owner action recorded | Priority | If approved: release | WP |", "|---|---|---|---|---|---|"]
    for r in sorted(hist, key=lambda x: (x["priority"], x["id"])):
        oa = str(r["historical"].get("owner_decisions") or "").replace("|", "/")[:140]
        L.append(f"| {r['id']} | {r['title'].replace('|', '/')[:80]} | {oa} | {r['priority']} | {r['release']} | {r['wp']} |")
    ac = [r for r in items if r["scope_class"] == "ACADEMIC_ONLY"]
    L += ["", f"## Academic-only capstone tasks awaiting confirmation of retirement ({len(ac)}; OD-ACADEMIC-01)", "", "| ID | Title | Historical status | Why academic only |", "|---|---|---|---|"]
    for r in sorted(ac, key=lambda x: x["id"]):
        L.append(f"| {r['id']} | {r['title'].replace('|', '/')[:80]} | {r['current_status']} | {ACADEMIC_ONLY[r['id']]} |")
    new = [r for r in items if r["origin"] == "NEW" and r["disposition"] == "OWNER DECISION"]
    L += ["", f"## New items needing an owner decision ({len(new)})", "", "| ID | Title | Proposed release | Provenance |", "|---|---|---|---|"]
    for r in sorted(new, key=lambda x: x["id"]):
        L.append(f"| {r['id']} | {r['title'].replace('|', '/')[:100]} | {r['release']} | {r['provenance']} |")
    L.append("")
    return "\n".join(L)


def render_acceptance_matrix(doc: dict) -> str:
    cc = [x for x in doc["cross_check"] if x["source"].startswith("Acceptance ledger")]
    L = ["# Production Acceptance Matrix (V2.2, corrected)", "", "**Status:** corrected 2026-10-21. No production gate has passed. This matrix does not upgrade any capstone result: the capstone acceptance ledger (17 PASS, 8 PARTIAL), the historical 95% coverage gate (386 of 412 against 392, FAIL), AC-24 PARTIAL and human-qualified coverage 0 of 412 stay as recorded. A mandatory safety, privacy, licensing or operational gate cannot be bypassed by recording an accepted limitation; the owner may remove a feature from scope or delay its activation. Numeric thresholds are not yet approved (OD-GATE-THRESHOLDS); states below are honest current states, not passes.", "",
         "## 1. Production gates for R1.0 (free private beta)", "", "| Gate | Name | Measurable requirement | Evidence | State |", "|---|---|---|---|---|"]
    for g in PRODUCTION_GATES:
        L.append("| " + " | ".join(c.replace("|", "/") for c in g) + " |")
    L += ["", "## 2. Per-language gates (LG-01 to LG-14, each of seven languages)", "", "A language is activated for real users only when ALL fourteen gates pass for it; a failed mandatory gate prevents activation in that locale. Today none passes. Per-language reporting is kept; there is no aggregate claim.", "",
          "| Gate | Meaning | " + " | ".join(n for _, n, _ in LANG_NAMES) + " |", "|---|---|" + "---|" * len(LANG_NAMES)]
    state = {"LG-01": "NOT RUN", "LG-02": "ENGINEERING DRAFT (key parity enforced; unreviewed)", "LG-03": "NOT RUN per language", "LG-04": "PARTIAL (offline fixtures)", "LG-05": "NOT RUN", "LG-06": "NOT RUN (English-keyword routing known)",
             "LG-07": "OFFLINE separation tests; markets unapproved", "LG-08": "PARTIAL (offline fixtures)", "LG-09": "NOT RUN per language", "LG-10": "NOT MET (engineering drafts)", "LG-11": "NOT MET (no reviewer)", "LG-12": "PARTIAL (offline)", "LG-13": "NOT STARTED", "LG-14": "NOT MET (Russian still selectable)"}
    for gid, name, _ in GATES:
        L.append(f"| {gid} | {name} | " + " | ".join(state[gid] for _ in LANG_NAMES) + " |")
    L += ["", "German has some governed knowledge-base content; the other languages have none beyond the curated corpus. Rows diverge as per-language evidence is gathered.", "",
          "## 3. Capstone acceptance criteria that are not PASS (carried, not upgraded)", "", "| AC | Historical state | Handling | Tracked by |", "|---|---|---|---|"]
    for x in cc:
        if not x["handling"].startswith("CLOSE"):
            L.append(f"| {x['id']} | {x['historical_state']} | {x['handling']} | {', '.join(x['mapped_issue_ids'][:5])} |")
    L += ["", "## 4. Historical gates preserved", "", "The original 95% product-coverage gate keeps its failed result. A separate frozen, qualified R1.0 beta-scope coverage measure is required (REQ-COV-01, OD-COVERAGE) and is always reported beside, never instead of, the historical result.", ""]
    return "\n".join(L)


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "check"
    if cmd == "generate":
        doc = build()
        errs = validate(doc)
        if errs:
            print("\n".join(errs[:30]))
            return 1
        OUT.mkdir(parents=True, exist_ok=True)
        RECON.write_text(json.dumps(doc, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        (OUT / "MASTER_REQUIREMENTS_TRACEABILITY.md").write_text(render_traceability(doc), encoding="utf-8")
        (OUT / "RELEASE_BLOCKER_DASHBOARD.md").write_text(render_dashboard(doc), encoding="utf-8")
        (OUT / "OWNER_DECISION_REGISTER.md").write_text(render_owner_decisions(doc), encoding="utf-8")
        (OUT / "PRODUCTION_ACCEPTANCE_MATRIX.md").write_text(render_acceptance_matrix(doc), encoding="utf-8")
        print(json.dumps(doc["summary"], indent=1))
        return 0
    if cmd == "check":
        doc = json.loads(RECON.read_text(encoding="utf-8"))
        errs = validate(doc)
        fresh = build()
        for key in ("summary",):
            if doc[key] != fresh[key]:
                errs.append(f"committed {key} is stale: regenerate with `generate`")
        if {r["id"]: r["disposition"] for r in doc["items"]} != {r["id"]: r["disposition"] for r in fresh["items"]}:
            errs.append("committed dispositions differ from the rules: regenerate with `generate` (or the register changed)")
        if errs:
            print("\n".join(errs[:40]))
            return 1
        print(f"OK: {len(doc['items'])} items, 0 unmapped, history preserved")
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
