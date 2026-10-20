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
RELEASES = ("R1.0", "R1.1", "R1.2", "R1.3", "R2.0")
DEFER_RELEASES = ("R1.1", "R1.2", "R1.3", "R2.0")

# Proposed release themes (the owner fixed only R1.0 = 30 Nov 2026 and R1.3 = Mandarin/Hindi/Arabic; the rest are PROPOSED).
RELEASE_THEMES = {
    "R1.0": "First production release, 30 November 2026: seven candidate languages (all gates), safety/privacy/operations blockers, English-only Admin",
    "R1.1": "Post-launch stabilisation: operational depth, accessibility and performance polish, non-safety technical debt",
    "R1.2": "Commercial activation and external integrations (billing, Stripe, paid plans, Adzuna, external paging) behind owner approval",
    "R1.3": "New languages: Mandarin, Hindi, Arabic (language-specific engineering and human qualification each)",
    "R2.0": "International expansion and deep modalities: knowledge/compensation beyond the seven markets, server speech and realtime voice, Russian, enterprise",
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
}

MARKETS = ["Ireland", "Germany", "Spain", "Italy", "Portugal", "France", "Netherlands"]
SEVEN_MARKET_RE = re.compile(r"\b(ireland|irish|germany|german|deutschland|spain|spanish|italy|italian|portugal|portuguese|france|french|netherlands|dutch|eu\b|europe|esco|eurostat)", re.I)
OTHER_MARKET_RE = re.compile(r"\b(united kingdom|\buk\b|canada|australia|india|china|japan|brazil|mexico|singapore|uae|gulf|saudi|africa|latin america)\b", re.I)
LANG_RE = re.compile(r"(locale|language|translat|multilingual|native-|native review|i18n|l10n|cross-language|xlang|dutch|german|french|spanish|italian|portuguese|russian|\bru\b|conversation language)", re.I)
RUSSIAN_RE = re.compile(r"(russian|\bru\b|cyrillic)", re.I)
FUTURE_LANG_RE = re.compile(r"(mandarin|chinese|hindi|arabic)", re.I)
COMMERCIAL_RE = re.compile(r"(stripe|billing|checkout|invoice|\btax\b|refund|premium|revenue|merchant|seller|payment|subscription|pricing|entitlement|plan price|mrr)", re.I)
CLAIM_RE = re.compile(r"(claim|label|preview|banner|disclos|public page|marketing|honest)", re.I)
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
    if grp == "russian":
        return deferred("R2.0", "D-RU", "Russian is excluded from R1.0 (owner 2026-10); code preserved, locale must not be exposed as an active beta locale", ["Russian locale hidden from candidate language choices (see REQ-LANG-14)"])
    if grp == "future_language":
        return deferred("R1.3", "D-FL", "Mandarin, Hindi, Arabic are the R1.3 languages (owner decision)", ["no zh/hi/ar locale is registered in src/locales.py"])
    if grp == "commercial":
        return deferred("R1.2", "D-COM", "commercial activation is outside R1.0; billing stays mock-only and disabled", FEATURE_GATES["commercial"])
    if grp == "intl_knowledge":
        return deferred("R2.0", "D-INTL", "knowledge/compensation outside the seven R1.0 markets; Compensation V2 and international sources stay disabled", ["Compensation V2 and international sources not operational (src/knowledge_foundation/readiness.py: operational_today False)"])
    if grp == "speech_server":
        return deferred("R2.0", "D-SPEECH", "server speech and realtime voice are outside R1.0; governed speech stays disabled", FEATURE_GATES["speech"])
    if grp == "integration_later":
        return deferred("R1.2", "D-INT", "integration is outside R1.0 and not enabled", ["integration not configured; no live provider call is possible without owner credentials"])
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
    return deferred("R1.1", "D-R11", "does not block production and has no safety, privacy or claim impact on an enabled feature", ["no enabled feature depends on it"])


def language_gates_for(text: str) -> str:
    out = []
    for pat, gates in LANGUAGE_GATES.items():
        if re.search(pat, text, re.I):
            out.extend(gates.split(","))
    return ",".join(sorted(set(out))) or "LG-01"


def new_requirements() -> list[dict]:
    """Requirements that are NOT in the 394-row register: the owner's language decision, owner-named Admin/product areas and five demonstration findings."""
    def r(id_, title, desc, wp, prio, disp, release, accept, tests, sec, deps, status, source, gate_reason=""):
        return dict(id=id_, title=title, description=desc, wp=wp, priority=prio, disposition=disp, release=release, acceptance_criteria=accept, required_tests=tests,
                    security_privacy_impact=sec, dependencies=deps, current_status=status, source=source, feature_gate=gate_reason, origin="NEW")
    L = "owner language decision 2026-10-21 (Roadmap V2.2)"
    langs = []
    spec = [
        ("REQ-LANG-01", "Audit every existing locale", "Inventory the interface catalogues, Mo conversation, interview and report text, legal/privacy pages and email templates for en, de, es, it, pt, fr, nl; record gaps per language.", "Audit report per language with counts of missing, machine-translated and unreviewed strings", "scripts/eval_i18n_l10n.py plus a new per-language audit table", "LG-01,LG-02"),
        ("REQ-LANG-02", "Verify all Candidate journeys in all seven languages", "Onboarding, Opportunity, Company research, Prepare/Mo, Practice, History, Progress, Documents, Settings and privacy controls work end to end in each language.", "One recorded run per language per journey with no English fallback leaking into chrome or Mo text", "Playwright per-language journey matrix; screenshots", "LG-03"),
        ("REQ-LANG-03", "Prompts and system policies work correctly in each language", "Grounding policy, safety policy, coaching-style directive and language directive behave in each language (no policy bypass by switching language).", "Per-language policy regression suite passes; directive text allow-listed", "tests/test_candidate_grounding_policy.py extended per language; scripts/eval_agent.py", "LG-04"),
        ("REQ-LANG-04", "Validate localized interview questions, scoring, feedback and explanations", "Question generation, rubric scoring, feedback and Deep Dive explanations in each language; scoring is not recomputed or biased by language.", "Blinded native-reader rating plus deterministic checks that scores are language-independent", "Human rating protocol; scoring invariance tests", "LG-05,LG-11"),
        ("REQ-LANG-05", "Verify Story Bank and Workspaces in all seven languages", "Story capture, verification, sharing grants, invitations and report export render and behave correctly in each language.", "Per-language Story Bank and Workspace flow passes with owner isolation intact", "eval_workspace_security plus per-language Playwright", "LG-09"),
        ("REQ-LANG-06", "Evaluate multilingual RAG and cross-language source attribution", "Retrieval and citation across languages: question in language X over sources in language Y, with correct attribution, abstention and no invented translation of source claims.", "Per-language retrieval/citation evaluation with sample sizes and a stated limitation; no unsourced claims", "Multilingual retrieval evaluator (new) plus citation validity tests", "LG-06"),
        ("REQ-LANG-07", "Language must never change labour-market country silently", "Selecting a language never changes career geography; the proposed market mapping (en to Ireland, de to Germany, es to Spain, it to Italy, pt to Portugal, fr to France, nl to Netherlands) is a PROPOSAL used only as an explicit, user-visible suggestion after owner approval and source qualification.", "Tests prove geography is unchanged by any language switch; mapping is not applied without an explicit user choice", "tests for language/geography separation; Playwright", "LG-07"),
        ("REQ-LANG-08", "Language-specific injection, security and privacy regression suites", "Prompt-injection, PII/redaction, privacy-request and abuse suites run in each language including mixed-script inputs.", "All suites pass in each language; failures block that language", "eval suites per language (injection fixtures in 7 languages exist for multi-agent; extend to security/privacy)", "LG-08"),
        ("REQ-LANG-09", "Native-language human review", "A named native reviewer per language signs off interface text, Mo output samples, interview questions/feedback and legal text.", "Signed review record per language (reviewer, date, scope, findings, resolution)", "Human review protocol and sign-off records", "LG-11,LG-12"),
        ("REQ-LANG-10", "Qualify legal and privacy translations before real-user access", "Terms, Privacy, AI-transparency and consent text are reviewed by qualified counsel/translator in each language before any real-user access in that language.", "Signed legal translation qualification per language", "Legal review record; version registry entries", "LG-10"),
        ("REQ-LANG-11", "Track readiness and quality separately per language", "A per-language readiness record (gate state, evidence date, SHA, sample size) is maintained; no aggregate 'multilingual ready' claim.", "One status row per language per gate in PRODUCTION_ACCEPTANCE_MATRIX.md, generated from evidence", "Consistency check that fails if an aggregate claim exists without all gates", "LG-13"),
        ("REQ-LANG-12", "Keep Platform Admin English-only for R1.0", "Admin interface stays English; no Admin translation work in R1.0 and Admin never gains a candidate-content path through localisation.", "Admin catalogue remains English; scanner exempts Admin as documented", "Existing Admin invariants", "LG-14"),
        ("REQ-LANG-13", "No language is called production-qualified before its gates pass", "Public pages, documents and Admin must not claim a language is production-qualified until LG-01..LG-14 pass for it; unqualified languages are not offered for real-user access.", "Marketing/claims gate (eval_marketing_product_trust) extended; per-language switch off until qualified", "Claim discipline test; owner review", "LG-13"),
        ("REQ-LANG-14", "Russian: exclude from R1.0 and do not expose it as an active beta locale", "Russian code is preserved, but the Russian option must not appear in candidate language choices for R1.0. (Today Russian is an exposed eighth locale: this is a code change that has NOT been made.)", "Language selector, onboarding and settings offer exactly seven languages; Russian catalogue retained and tested", "frontend tests for selectable locales; scripts/eval_i18n_l10n.py updated", "LG-14"),
        ("REQ-LANG-15", "R1.3 languages: Mandarin, Hindi, Arabic", "Each needs new language-specific engineering (scripts, RTL for Arabic, tokenisation, speech boundaries) and human qualification before exposure.", "A separate language-qualification plan per language approved by the owner", "Plan documents; not started", "LG-01..LG-14 (future)"),
        ("REQ-LANG-16", "Approve and qualify the proposed primary market per language", "Owner approves the seven-market mapping and sources for those markets are qualified (licence, authority, coverage) before it is used anywhere.", "Signed owner decision and a source approval register entry per market", "Source approval register; coverage evidence", "LG-07"),
    ]
    for id_, title, desc, accept, tests, gates in spec:
        e = r(id_, title, desc, "WP-08", "P1" if id_ != "REQ-LANG-15" else "P2", "FIX BEFORE R1.0", "R1.0", accept, tests,
              "Privacy and safety: language-specific injection and PII handling; legal text accuracy", "REQ-LANG-01 precedes REQ-LANG-02..13; owner approval for REQ-LANG-16", "NEW - NOT STARTED", L)
        e["language_gates"] = gates
        langs.append(e)
    # adjust special cases
    for e in langs:
        if e["id"] == "REQ-LANG-15":
            e.update(disposition="DEFER TO NAMED RELEASE", release="R1.3", feature_gate="no zh/hi/ar locale is registered in src/locales.py")
        if e["id"] == "REQ-LANG-16":
            e.update(disposition="OWNER DECISION")
    o = "owner-requested area named in the V2.2 reconciliation prompt; the detailed requirement text is NOT in this repository"
    areas = [("Admin 2.0", "WP-10"), ("Plans", "WP-10"), ("Users", "WP-10"), ("Reports", "WP-10"), ("Knowledge (Admin sources)", "WP-10"), ("Story Bank", "WP-09"), ("Workspaces", "WP-09"), ("Navigation", "WP-10")]
    own = []
    for n, (name, wp) in enumerate(areas, 1):
        e = r(f"REQ-OWN-{n:02d}", f"Owner-requested requirement: {name}", f"The owner named '{name}' as a requirement area. The detailed text of the earlier approved requirement is not recorded in the repository, so no scope is invented here.",
              wp, "P1", "OWNER DECISION", "R1.0", "Owner supplies or points to the approved requirement text; then acceptance criteria are written and traced",
              "To be defined once the requirement text is supplied", "Requirement-specific; Admin never gains candidate-content access", "Owner supplies requirement text (OD-REQ-TEXT)", "NEW - REQUIREMENT TEXT NOT IN REPOSITORY", o)
        own.append(e)
    findings = [
        ("RF-01", "Admin Knowledge Sources looked empty although the curated corpus was intact", "Curated sources (31) and governed sources (4 synthetic) are different layers; the Sources page listed only governed records. A read-only curated panel was added (PR #210). Operators still need a clear 'what is searched' explanation.", "WP-10", "P1", "VERIFY BEFORE R1.0", "Page explains curated vs governed; reviewer walkthrough passes without the empty-state confusion", "Admin Knowledge Playwright; walkthrough", "CLOSED IN CODE (PR #210); verification pending"),
        ("RF-02", "Wrong stack mode silently broke 'Start interview' (keyless stack without a key returned a generic unavailable message)", "A keyless review stack and the live stack look identical in the UI; interview creation failed with a generic message. Operators and the UI need a visible environment/mode indicator and a clearer provider-unavailable message.", "WP-02", "P1", "FIX BEFORE R1.0", "Candidate and Admin show the active provider mode; the unavailable message distinguishes 'AI not configured' from transient failure; documented startup per mode", "Mode-indicator tests; startup runbook rehearsal", "NEW - NOT STARTED"),
        ("RF-03", "Live RAGAS result is PARTIAL (7 of 8 valid) with response relevancy 0.0 and context recall 0.0", "The only live RAGAS run covered 2 cases; the scores are valid numbers from a tiny sample but are unexplained and low. They must be investigated before any quality claim.", "WP-16", "P1", "VERIFY BEFORE R1.0", "Root-cause analysis of the zero scores (reference quality, retrieval, embedding path); a larger approved run reaches COMPLETE status", "Bounded live evaluation under an approved budget", "NEW - NOT STARTED"),
        ("RF-04", "Blocking calls inside async request paths can deadlock the event loop", "The live-demo spend guard blocked the event loop (fixed, regression test added). Other synchronous waits in async paths (locks, SQLite) should be audited.", "WP-15", "P2", "VERIFY BEFORE R1.0", "Audit result recorded; async-safety tests for provider chokepoints", "Async regression tests", "FIXED IN GUARD; audit not started"),
        ("RF-05", "Optional-dependency tests failed in the base CI install", "A test imported the optional RAGAS package (fixed in PR #209 with a dedicated evaluation-extras CI job). Other optional-dependency tests should be audited for the same pattern.", "WP-15", "P2", "VERIFY BEFORE R1.0", "Audit result recorded; every optional-extra test either runs in a provisioned job or skips by importorskip", "CI matrix", "FIXED FOR RAGAS; audit not started"),
    ]
    fr = []
    for id_, title, desc, wp, prio, disp, accept, tests, status in findings:
        e = r(id_, title, desc, wp, prio, disp, "R1.0", accept, tests, "Reliability and honest representation of AI quality", "none beyond the item", status,
              "ENGINEERING-OBSERVED during the live-demo preparation (the text of the five CAPSTONE REVIEWER findings was not supplied; owner to confirm or replace these five)")
        fr.append(e)
    return langs + own + fr


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
    allitems = items + newreq
    summary = summarise(register, items, newreq, xrows)
    return dict(
        generated="2026-10-21", baseline_register=dict(file="docs/capstone/post_submission_deferred_issues.json", generated=raw["generated"], base_main_sha=raw["base_main_sha"], count=raw["count"]),
        disclaimer="All dispositions, releases, owners and work packages are PROPOSED by documented rules for owner review. No historical status, gate or closure evidence was changed.",
        dispositions=list(DISPOSITIONS), releases=list(RELEASES), release_themes=RELEASE_THEMES, work_packages={k: dict(name=v[0], owner_role=v[1]) for k, v in WORK_PACKAGES.items()},
        gate_constants=GATE_NAMES, summary=summary, cross_check=xrows, items=allitems,
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
        new_demo_findings=sum(1 for e in newreq if e["id"].startswith("RF-")), new_cross_check_issues=sum(1 for e in newreq if e["id"].startswith("XC-")),
        prior_alias_merges=sum(len(i.get("aliases") or []) for i in register), duplicates_reconciled_this_pass=dup,
        disposition_counts=cnt("disposition", allitems), historical_disposition_counts=cnt("disposition", items),
        release_by_disposition={k: dict(v) for k, v in by_rel_disp.items()},
        r1_0_must_fix=sum(1 for r in allitems if r["disposition"] == "FIX BEFORE R1.0"), r1_0_must_verify=sum(1 for r in allitems if r["disposition"] == "VERIFY BEFORE R1.0"),
        owner_decisions=sum(1 for r in allitems if r["disposition"] == "OWNER DECISION"),
        deferred_by_release={rel: sum(1 for r in allitems if r["disposition"] == "DEFER TO NAMED RELEASE" and r["release"] == rel) for rel in DEFER_RELEASES},
        priority_of_r1_0_work=dict(Counter(r["priority"] for r in allitems if r["disposition"] in ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0"))),
        cross_check_rows=len(xrows), cross_check_sources=dict(Counter(x["source"] for x in xrows)),
        unmapped_issues=0,
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
    need = ("id", "title", "wp", "priority", "owner_role", "dependencies", "current_status", "acceptance_criteria", "required_tests", "security_privacy_impact", "disposition", "release", "rule_id")
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
        if d == "OWNER DECISION" and rel not in RELEASES:
            errs.append(f"{r['id']}: owner decision lacks a proposed release")
        if d == "CLOSE WITH EVIDENCE" and not str(r.get("evidence_of_closure") or "").strip():
            errs.append(f"{r['id']}: closure without evidence")
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
          "| B3 | Production impact unknown at P0/P1: VERIFY before R1.0 |", "| S1 | AI-safety (D), privacy (F) or legal (K) item at P0-P2 or with a security/privacy impact: VERIFY before R1.0, never deferred while its feature is enabled |", "| M1 | Source qualification for one of the seven R1.0 markets: VERIFY before R1.0 |", "| D-R11 | No production impact and no enabled-feature dependency: defer to R1.1 |", "| D-COM | Commercial activation: R1.2 while billing gates stay False |",
          "| D-INT | Later integrations: R1.2 while not configured |", "| D-INTL | Knowledge/compensation outside the seven markets: R2.0 while Compensation V2 and international sources stay disabled |", "| D-SPEECH | Server speech and realtime: R2.0 while governed speech gates stay False |",
          "| D-RU | Russian: excluded from R1.0 |", "| D-FL | Mandarin, Hindi, Arabic: R1.3 |", "| +dup | Same meaning as an earlier issue: shares its disposition |", ""]
    order = {d: n for n, d in enumerate(DISPOSITIONS)}
    for rel in list(RELEASES) + ["n/a"]:
        rows = [r for r in doc["items"] if r["release"] == rel]
        if not rows:
            continue
        L += [f"## {rel}" + (f": {RELEASE_THEMES[rel]}" if rel in RELEASE_THEMES else ": closed items (evidence preserved)"), "", f"{len(rows)} items.", "", "| ID | Title | Disposition | WP | Prio | Historical status | Rule |", "|---|---|---|---|---|---|---|"]
        for r in sorted(rows, key=lambda x: (order[x["disposition"]], x["priority"], x["id"])):
            t = r["title"].replace("|", "/")[:90]
            L.append(f"| {r['id']} | {t} | {r['disposition']} | {r['wp']} | {r['priority']} | {r['current_status']} | {r['rule_id']} |")
        L.append("")
    L += ["## Cross-check against the other matrices", "", f"{len(doc['cross_check'])} rows from: " + ", ".join(f"{k} ({v})" for k, v in s["cross_check_sources"].items()) + ".", "", "| Source | ID | Historical state | Handling | Mapped issue(s) |", "|---|---|---|---|---|"]
    for x in doc["cross_check"]:
        if x["handling"].startswith("CLOSE"):
            continue
        L.append(f"| {x['source']} | {x['id']} | {x['historical_state']} | {x['handling']} | {', '.join(x['mapped_issue_ids'][:4])} |")
    L += ["", f"Historical PASS rows ({sum(1 for x in doc['cross_check'] if x['handling'].startswith('CLOSE'))}) are kept as CLOSE WITH EVIDENCE and not re-opened; their evidence stays in the source documents.", ""]
    return "\n".join(L)


def render_dashboard(doc: dict) -> str:
    s = doc["summary"]
    items = doc["items"]
    r10 = [r for r in items if r["disposition"] in ("FIX BEFORE R1.0", "VERIFY BEFORE R1.0")]
    L = ["# Release Blocker Dashboard (R1.0, 30 November 2026)", "", "**Status:** PROPOSED, generated 2026-10-21. Counts come from `PRODUCTION_ISSUE_RECONCILIATION.json` and are checked by `scripts/production/reconcile_issues.py check`.", "",
         "## Totals", "", "| Measure | Count |", "|---|---|", f"| Historical issues | {s['historical_issues']} |", f"| Historically closed (evidence preserved) | {s['historical_closed']} |", f"| Historically active | {s['historical_active']} |",
         f"| Historical production blockers | {s['historical_production_blockers']} |", f"| Historical pending owner decisions | {s['historical_owner_decisions']} |", f"| Newly recorded items | {s['new_items']} (language {s['new_language_requirements']}, owner-named areas {s['new_owner_requested_areas']}, demonstration findings {s['new_demo_findings']}, cross-check {s['new_cross_check_issues']}) |",
         f"| Earlier alias merges recorded in the register | {s['prior_alias_merges']} |", f"| Duplicates reconciled in this pass (by meaning, IDs kept) | {s['duplicates_reconciled_this_pass']} |",
         f"| **R1.0 must-fix** | **{s['r1_0_must_fix']}** |", f"| **R1.0 must-verify** | **{s['r1_0_must_verify']}** |", f"| Owner decisions | {s['owner_decisions']} |",
         "| Deferred | " + ", ".join(f"{k}: {v}" for k, v in s["deferred_by_release"].items()) + " |", f"| Unmapped issues | **{s['unmapped_issues']}** |", ""]
    L += ["## R1.0 work by priority", "", "| Priority | Items |", "|---|---|"] + [f"| {k} | {v} |" for k, v in sorted(s["priority_of_r1_0_work"].items())] + [""]
    L += ["## R1.0 work by work package", "", "| WP | Fix | Verify | Owner decisions |", "|---|---|---|---|"]
    for k, v in doc["work_packages"].items():
        f = sum(1 for r in items if r["wp"] == k and r["disposition"] == "FIX BEFORE R1.0")
        ve = sum(1 for r in items if r["wp"] == k and r["disposition"] == "VERIFY BEFORE R1.0")
        o = sum(1 for r in items if r["wp"] == k and r["disposition"] == "OWNER DECISION")
        L.append(f"| {k} {v['name']} | {f} | {ve} | {o} |")
    L += ["", "## Capacity warning", "", f"{len(r10)} items must be fixed or verified before R1.0 and the date is 30 November 2026. Many need people who are not yet named (reviewers A, B, C, native reviewers for seven languages, legal counsel) or an authorised hosted environment. The owner should decide the scope trade-off explicitly (OD-SCOPE-01 in OWNER_DECISION_REGISTER.md); this dashboard does not assume it will fit.", "",
          "## R1.0 P0 items", "", "| ID | Title | Disposition | WP |", "|---|---|---|---|"]
    for r in sorted((r for r in r10 if r["priority"] == "P0"), key=lambda x: x["id"]):
        L.append(f"| {r['id']} | {r['title'].replace('|', '/')[:90]} | {r['disposition']} | {r['wp']} |")
    L += ["", "## Gates that keep deferred features disabled", ""] + [f"- `{g}` must be False" for g in doc["gate_constants"]] + [""]
    return "\n".join(L)


NEW_DECISIONS = [
    ("OD-SCOPE-01", "Confirm or re-scope R1.0 (30 November 2026)", "The reconciled R1.0 must-fix and must-verify counts (see RELEASE_BLOCKER_DASHBOARD.md) exceed what a team can plausibly close in about five weeks, and several items depend on people not yet named. Decide: hold the date and re-scope, move the date, or release a subset.", "R1.0"),
    ("OD-LANG-01", "Approve the seven R1.0 languages and the per-language gates LG-01..LG-14", "Languages: English, German, Spanish, Italian, Portuguese, French, Dutch. Decide what happens if a language fails its gates at the cut-off: it is not offered for real-user access (recommended), or the release waits. The owner said R1.0 must not be English-only.", "R1.0"),
    ("OD-LANG-02", "Approve the proposed primary market per language", "English-Ireland, German-Germany, Spanish-Spain, Italian-Italy, Portuguese-Portugal, French-France, Dutch-Netherlands. PROPOSED only: used solely as an explicit, user-visible suggestion after source qualification; never inferred from the interface language.", "R1.0"),
    ("OD-LANG-03", "Name the native-language reviewer for each of the seven languages", "No reviewer is named. Needed before LG-11.", "R1.0"),
    ("OD-LANG-04", "Name the legal and privacy translation qualifier(s) for the seven languages", "Needed before any real-user access (LG-10).", "R1.0"),
    ("OD-LANG-05", "Approve hiding Russian from candidate language choices for R1.0", "Russian is exposed today as an eighth locale; the owner decision excludes it from R1.0 and forbids exposing it as an active beta locale. Code is preserved.", "R1.0"),
    ("OD-LANG-06", "Approve the R1.3 plan for Mandarin, Hindi and Arabic", "Each needs new language-specific engineering and human qualification; plans are not yet written.", "R1.3"),
    ("OD-REQ-TEXT", "Supply the approved requirement text for the owner-named areas", "Admin 2.0, Plans, Users, Reports, Knowledge, Story Bank, Workspaces and navigation (REQ-OWN-01..08): the detailed text is not in the repository, so no scope was invented.", "R1.0"),
    ("OD-REVIEW-FINDINGS", "Confirm or replace the five capstone reviewer findings", "The reviewer findings were not supplied; five engineering-observed findings (RF-01..RF-05) are recorded in their place.", "R1.0"),
    ("OD-HOSTED", "Authorise a hosted staging and production environment", "Hosted deployment (EX-12) cannot be certified locally; needed for the TLS, backup, rollback and scale gates.", "R1.0"),
    ("OD-BUDGET", "Approve a bounded live-evaluation and live-provider budget for qualification", "Native-review samples, live multilingual Mo checks and a larger RAGAS run need an explicit budget; the EUR 10 capstone demonstration budget is not reusable.", "R1.0"),
    ("OD-RELEASE-TRAIN", "Approve or amend the proposed themes for R1.1, R1.2 and R2.0", "Only R1.0 (30 November 2026) and R1.3 (languages) were fixed by the owner; the other themes are proposals.", "R1.1"),
]

LANG_NAMES = [("en", "English", "Ireland"), ("de", "German", "Germany"), ("es", "Spanish", "Spain"), ("it", "Italian", "Italy"), ("pt", "Portuguese", "Portugal"), ("fr", "French", "France"), ("nl", "Dutch", "Netherlands")]
GATES = [
    ("LG-01", "Locale audit complete", "Catalogue, Mo, interview, report, legal and email text inventoried; missing/unreviewed counts recorded"),
    ("LG-02", "Interface text complete", "No missing keys, no English leak in chrome, protected slogan unchanged"),
    ("LG-03", "Candidate journeys pass", "All candidate surfaces work end to end in the language"),
    ("LG-04", "Prompts and policies verified", "Grounding, safety, coaching-style and language directives behave; no policy bypass by language"),
    ("LG-05", "Interview quality validated", "Questions, scoring invariance, feedback and explanations reviewed"),
    ("LG-06", "Multilingual RAG and attribution", "Retrieval, citation and abstention evaluated; no invented source translation"),
    ("LG-07", "Language never sets the country", "Geography unchanged by language; proposed market mapping owner-approved and source-qualified"),
    ("LG-08", "Injection, security and privacy suites", "Language-specific suites pass"),
    ("LG-09", "Story Bank and Workspaces", "Flows verified with owner isolation intact"),
    ("LG-10", "Legal and privacy translation qualified", "Qualified review signed before real-user access"),
    ("LG-11", "Native-language human review", "Named reviewer sign-off on UI, Mo samples, interview text"),
    ("LG-12", "Mo language ownership", "Mo-voiced and deterministic text in the conversation language; interface language owns only chrome"),
    ("LG-13", "Readiness tracked, no aggregate claim", "Per-language status maintained; no production-qualified claim before all gates"),
    ("LG-14", "Boundaries", "Admin English-only; Russian not exposed; zh/hi/ar not registered"),
]


def render_owner_decisions(doc: dict) -> str:
    items = doc["items"]
    L = ["# Owner Decision Register (Production Roadmap V2.2)", "", "**Status:** PROPOSED, generated 2026-10-21. Nothing here is decided on the owner's behalf. Historical decisions keep their register IDs and wording; new decisions are listed first.", "",
         "## New decisions required by V2.2", "", "| ID | Decision | Detail | Proposed release |", "|---|---|---|---|"]
    for id_, t, d, rel in NEW_DECISIONS:
        L.append(f"| {id_} | {t} | {d.replace('|', '/')} | {rel} |")
    hist = [r for r in items if r["origin"] == "REGISTER" and r["current_status"] == "PENDING OWNER DECISION"]
    L += ["", f"## Historical pending owner decisions ({len(hist)})", "", "| ID | Decision | Owner action recorded | Priority | If approved: release | WP |", "|---|---|---|---|---|---|"]
    for r in sorted(hist, key=lambda x: (x["priority"], x["id"])):
        oa = str(r["historical"].get("owner_decisions") or "").replace("|", "/")[:140]
        L.append(f"| {r['id']} | {r['title'].replace('|', '/')[:80]} | {oa} | {r['priority']} | {r['release']} | {r['wp']} |")
    new = [r for r in items if r["origin"] == "NEW" and r["disposition"] == "OWNER DECISION"]
    L += ["", f"## New items needing an owner decision ({len(new)})", "", "| ID | Title | Proposed release |", "|---|---|---|"]
    for r in sorted(new, key=lambda x: x["id"]):
        L.append(f"| {r['id']} | {r['title'].replace('|', '/')[:100]} | {r['release']} |")
    L.append("")
    return "\n".join(L)


def render_acceptance_matrix(doc: dict) -> str:
    cc = [x for x in doc["cross_check"] if x["source"].startswith("Acceptance ledger")]
    L = ["# Production Acceptance Matrix (V2.2)", "", "**Status:** PROPOSED, generated 2026-10-21. No production gate has passed. This matrix does not upgrade any capstone result: the capstone acceptance ledger (17 PASS, 8 PARTIAL, coverage gate 386/412 FAIL, AC-24 PARTIAL, human-qualified coverage 0 of 412) stays as recorded.", "",
         "## 1. General production gates (R1.0)", "", "| Gate | Requirement | Evidence required | State |", "|---|---|---|---|"]
    gen = [
        ("PG-01", "Hosted deployment rehearsed: TLS and HSTS, migration, backup and restore, rollback, pause", "Rehearsal record on an authorised hosted environment", "NOT RUN (EX-12 and related issues)"),
        ("PG-02", "Identity: live verification email and password recovery; Google sign-in either validated or disabled", "Owner-authorised live round trip", "NOT RUN"),
        ("PG-03", "AI security: injection, grounding and abuse suites pass in all seven languages", "Per-language suite results at the release SHA", "PARTIAL (English and some multilingual fixtures offline)"),
        ("PG-04", "Privacy and data rights verified; legal documents qualified in each language before real-user access", "Counsel sign-off per language; privacy suites", "NOT MET (engineering drafts)"),
        ("PG-05", "Knowledge sources for the seven markets qualified (licence, authority, coverage); coverage gate handled honestly", "Source approval register; coverage report (gate currently FAILS)", "NOT MET"),
        ("PG-06", "Candidate journeys pass in each language", "Per-language journey evidence", "NOT RUN per language"),
        ("PG-07", "Human validation: named reviewers; native-language review; AC-24 human items", "Signed reviews", "NOT MET (no reviewer named)"),
        ("PG-08", "Admin: permissions, audit, no candidate-content access, English-only", "Admin matrix and route invariant", "PASS offline at capstone scope; Admin 2.0 requirement text outstanding"),
        ("PG-09", "Operations: monitoring, alerting, incident process, resilience under load", "Runbook rehearsal and load evidence", "NOT RUN"),
        ("PG-10", "Deferred features stay disabled (all gate constants False) and no public claim exceeds evidence", "scripts/production/reconcile_issues.py check; claims gate", "MET at this SHA (checked by the reconciliation)"),
        ("PG-11", "Backlog reconciliation: every active issue has a valid disposition; zero unmapped", "scripts/production/reconcile_issues.py check", "MET (machine-checked)"),
    ]
    for g in gen:
        L.append("| " + " | ".join(g) + " |")
    L += ["", "## 2. Per-language gates", "", "A language is production-qualified only when ALL of LG-01..LG-14 pass for it. Today none do. States below are the honest current evidence class, not a pass.", "",
          "| Gate | Meaning | " + " | ".join(n for _, n, _ in LANG_NAMES) + " |", "|---|---|" + "---|" * len(LANG_NAMES)]
    state = {"LG-01": "NOT RUN", "LG-02": "ENGINEERING DRAFT (key parity enforced; unreviewed)", "LG-03": "NOT RUN per language", "LG-04": "PARTIAL (offline fixtures)", "LG-05": "NOT RUN", "LG-06": "NOT RUN (English-keyword routing known)",
             "LG-07": "OFFLINE separation tests; mapping unapproved", "LG-08": "PARTIAL (offline fixtures)", "LG-09": "NOT RUN per language", "LG-10": "NOT MET (engineering drafts)", "LG-11": "NOT MET (no reviewer)", "LG-12": "PARTIAL (offline)", "LG-13": "NOT STARTED", "LG-14": "NOT MET (Russian still exposed)"}
    for gid, name, _ in GATES:
        L.append(f"| {gid} | {name} | " + " | ".join(state[gid] for _ in LANG_NAMES) + " |")
    L += ["", "German has some governed knowledge-base content; the other languages have none beyond the curated corpus. Per-language rows will diverge as evidence is gathered.", "",
          "## 3. Capstone acceptance criteria that are not PASS (carried, not upgraded)", "", "| AC | Historical state | Handling | Tracked by |", "|---|---|---|---|"]
    for x in cc:
        if not x["handling"].startswith("CLOSE"):
            L.append(f"| {x['id']} | {x['historical_state']} | {x['handling']} | {', '.join(x['mapped_issue_ids'][:5])} |")
    L.append("")
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
