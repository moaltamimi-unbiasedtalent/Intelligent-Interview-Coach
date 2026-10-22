"""Native-review and legal-translation qualification MATERIALS (06F; LG-10 and LG-11; OD-LANG-03, OD-LANG-04).

Purpose. LG-11 (native-language human review) and LG-10 (legal and privacy translation qualified) need named humans. Engineering cannot supply them and must not pretend to.
It can supply a complete, review-ready package so a reviewer's work starts the day the owner appoints them. This module builds that package, deterministically, per language:

* the exact interface catalogue strings grouped by surface, with the English source, the place each string appears and mechanical hints for attention;
* the Mo-voiced sentence tables (06C inventory) and the transactional email templates;
* the interview question and feedback prompts from the SYNTHETIC sample bank;
* pointers to the legal and privacy text (and, conditionally, to the legal review pack of 05E);
* the reviewer instruction sheet and an UNFILLED sign-off form whose fields are the fields ``src/language_activation.py`` requires (named reviewer, qualification statement,
  evidence reference, approval date, release SHA);
* a freeze manifest with per-language digests, and a changes-since-review diff so a frozen catalogue is re-reviewed incrementally.

Boundaries (never blur)
* No model call, no network, no credential, no real reviewer data and no invented name. The package is DATA for humans.
* Nothing here records or implies a qualification: every form is blank, ``validate_form`` only reports what is missing and never writes a record, and the freeze manifest has no
  freeze SHA until the owner supplies one. 06H requires a named human approver, an evidence reference, an approval date and the release SHA per gate.
* The catalogue is read through ``frontend/scripts/dump-catalog-strings.mjs`` (needs ``node`` and the frontend dependencies); the pure functions here take the catalogue as a
  plain ``{locale: {key: text}}`` mapping so they are testable without node.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from src.language_activation import _SHA, _iso_date, _PLACEHOLDER_WORDS, named_human
from src.language_quality import inventory as _inventory
from src.locales import ACTIVE_CANDIDATE_LOCALES, LANGUAGE_NAMES

ROOT = Path(__file__).resolve().parents[2]
FRONTEND = ROOT / "frontend"
PACK_DIR = ROOT / "docs" / "production" / "language_review"
MANIFEST_NAME = "FREEZE_MANIFEST.json"
BANK_FILE = ROOT / "evaluations" / "language_ai" / "synthetic_prompt_bank.json"
BRAND_SLOGAN = "Ask More. Be More."
LANGUAGES: tuple[str, ...] = ACTIVE_CANDIDATE_LOCALES
GENERATOR_VERSION = "06F/1"
FORM_SCHEMA = "ask4mo.language_review.signoff_form/1"
SNAPSHOT_SCHEMA = "ask4mo.language_review.freeze_snapshot/1"
MANIFEST_SCHEMA = "ask4mo.language_review.freeze_manifest/1"
LEGAL_NAMESPACES: tuple[str, ...] = ("aiTransparency", "dataPrivacy", "legal", "privacy", "terms", "trust")
SAMPLE_TASKS: tuple[str, ...] = ("interview_question", "interview_feedback")
FILES: tuple[str, ...] = ("README.md", "INSTRUCTIONS.md", "INTERFACE_STRINGS.md", "MO_SENTENCES.md", "INTERVIEW_SAMPLES.md", "LEGAL_POINTERS.md", "SIGNOFF_FORM.md",
                          "SIGNOFF_FORM.template.json")
GATE_NATIVE, GATE_LEGAL = "LG-11", "LG-10"
FORM_GATES: tuple[str, ...] = (GATE_NATIVE, GATE_LEGAL)

# ------------------------------------------------------------------------------------------------------------------------------------------------ context notes
# Surface groups and one context note per catalogue namespace. A namespace not listed here still renders (group "Other", generic note) and is counted in the README, so a new
# namespace never breaks the build; it just tells the reviewer less. Notes describe where the text appears, not what it should say.
_NAMESPACES: dict[str, tuple[str, str]] = {
    "common": ("Shell and navigation", "Shared words and buttons used on many screens (Save, Cancel, errors, the brand line)."),
    "nav": ("Shell and navigation", "Main navigation menu and header labels."),
    "v4nav": ("Shell and navigation", "Navigation labels of the redesigned shell."),
    "states": ("Shell and navigation", "Loading, empty and error state messages shown across the product."),
    "home": ("Home and public pages", "Candidate home screen: welcome, next-step cards and feature blocks."),
    "homeStory": ("Home and public pages", "Short story block on the home screen."),
    "marketing": ("Home and public pages", "Public marketing site (landing page) copy shown before sign-in."),
    "about": ("Home and public pages", "Public About page."),
    "proofCarousel": ("Home and public pages", "Evidence carousel on the public site."),
    "pricingV4": ("Pricing and plans", "Public pricing page. Prices and plan names are not translated; the preview status is part of the claim and must stay."),
    "plan": ("Pricing and plans", "Plan summary shown inside the product."),
    "planUx": ("Pricing and plans", "Plan and access explanations (what a plan includes, limits, previews)."),
    "quotaUx": ("Pricing and plans", "Usage limit and quota messages."),
    "billing": ("Pricing and plans", "Billing summary and payment state messages. Billing is not live: wording about payment states must stay precise."),
    "checkout": ("Pricing and plans", "Checkout availability and return pages."),
    "auth": ("Account and sign-in", "Sign-in, registration, email verification and password recovery screens."),
    "account": ("Account and sign-in", "Account page: profile, sessions, deletion and export controls."),
    "settings": ("Account and sign-in", "Settings page: language, coaching style, geography, memory and privacy options."),
    "geography": ("Account and sign-in", "Career geography (labour market) selection. Language never sets the country; the wording must not suggest it does."),
    "onboarding": ("Onboarding and help", "First-run onboarding steps."),
    "gettingStarted": ("Onboarding and help", "Getting-started checklist."),
    "tutorial": ("Onboarding and help", "Guided tutorial steps."),
    "help": ("Onboarding and help", "Help centre articles and FAQ."),
    "support": ("Onboarding and help", "Support tickets: forms, statuses and messages."),
    "prepare": ("Prepare (Mo coach)", "Prepare screen with the coach Mo: input, answer presentation, citations, approval cards."),
    "coach": ("Prepare (Mo coach)", "Coach framing labels."),
    "coaching": ("Prepare (Mo coach)", "Coaching style names and descriptions (supportive, balanced, direct, challenging)."),
    "journeyCues": ("Prepare (Mo coach)", "Journey stage cues (understand, prepare, practise)."),
    "prepctx": ("Prepare (Mo coach)", "Preparation context handoff messages."),
    "provenance": ("Prepare (Mo coach)", "Provenance labels (AI-generated, sourced, verified). The distinctions must survive translation exactly."),
    "researchEvidence": ("Prepare (Mo coach)", "Evidence and research labels on answers."),
    "sources": ("Prepare (Mo coach)", "Knowledge source label."),
    "feedback": ("Prepare (Mo coach)", "Feedback (helpful or not helpful) controls on answers and reports."),
    "dictation": ("Prepare (Mo coach)", "Dictation (speech-to-text) controls and messages."),
    "voice": ("Prepare (Mo coach)", "Voice playback (text-to-speech) and speaking controls."),
    "memory": ("Prepare (Mo coach)", "Saved preparation memory: what is stored, edit, pin, delete."),
    "practice": ("Practice (interviews)", "Interview practice: setup, questions, answers, evaluation, deep dive, report."),
    "history": ("Practice (interviews)", "Completed interview history."),
    "progress": ("Practice (interviews)", "Progress view and score interpretation. Scores are practice feedback, not a hiring decision."),
    "analyticsUx": ("Practice (interviews)", "Analytics and score explanations shown to the candidate."),
    "packUx": ("Practice (interviews)", "Preparation pack: sections, status and actions."),
    "workflow": ("Practice (interviews)", "Workflow step labels across preparation and practice."),
    "opportunity": ("Opportunities and company research", "Opportunity (private job-preparation context): list, detail, status."),
    "company": ("Opportunities and company research", "Company research: claim types FACT, REVIEW and MODEL_INFERENCE must stay distinguishable."),
    "documents": ("Documents and Story Bank", "Document upload, processing states, review and extraction."),
    "storyBank": ("Documents and Story Bank", "Story Bank: capture, verification, sources, revocation."),
    "workspaces": ("Collaboration", "Workspaces: members, invitations, sharing."),
    "wsMgmt": ("Collaboration", "Workspace management and share grants."),
    "trust": ("Legal, privacy and trust (qualified legal review, LG-10)", "Trust centre statements about data, AI and limits. Legal accuracy matters."),
    "privacy": ("Legal, privacy and trust (qualified legal review, LG-10)", "Privacy notice text."),
    "terms": ("Legal, privacy and trust (qualified legal review, LG-10)", "Terms of use text."),
    "aiTransparency": ("Legal, privacy and trust (qualified legal review, LG-10)", "AI transparency statement."),
    "dataPrivacy": ("Legal, privacy and trust (qualified legal review, LG-10)", "Data and privacy controls: export, deletion, retention explanations."),
    "trustUx": ("Legal, privacy and trust (qualified legal review, LG-10)", "Short trust cues next to features. Not legal text but must not contradict it."),
}
_OTHER_GROUP = "Other (context note not curated)"
_OTHER_NOTE = "No curated context note yet; use the 'where' column and the surface file list to see where the text appears."

_MO_CONTEXT: dict[str, str] = {
    "heading_evidence": "Section heading of a Mo answer: the evidence used (shown on the Prepare screen).",
    "heading_tool_results": "Section heading of a Mo answer: results from tools.",
    "heading_recommendation": "Section heading of a Mo answer: the recommendation.",
    "insufficient_evidence": "Notice shown when the knowledge base does not hold enough evidence to answer. POLICY: Mo says it cannot answer from evidence and does not guess.",
    "compensation_guidance": "Notice shown instead of a salary figure when no verified compensation evidence exists. POLICY: no unsourced salary figure or estimate is ever given.",
    "unretrieved_limitation": "Notice shown when a statistic was asked for but nothing was retrieved. POLICY: no statistic without a retrieved source.",
    "unverified_general_notice": "Note shown under a general answer that was not checked against the knowledge base. POLICY: the answer is labelled as not source-backed.",
    "fallback_model_unavailable": "Notice shown when the assistant model is unavailable.",
    "fallback_retrieved_passages": "Lead-in shown above retrieved passages when the model cannot write the answer.",
    "agent_unavailable": "Agent message when the assistant is temporarily unavailable.",
    "agent_not_configured": "Agent message when the assistant is not configured in this environment.",
    "agent_step_limit": "Message shown when the assistant reached its step limit for a request.",
    "hitl_approve_memory": "Approval card question: may Mo remember something for future preparation. POLICY: nothing is saved without an explicit yes.",
    "hitl_approve_handoff": "Approval card question: start practising the identified areas.",
    "warn_uncited_retrieval": "Run warning: retrieved evidence was used but the answer carried no inline citation.",
    "warn_statistic_removed": "Run warning: an unsupported statistic was removed and an evidence limit given. POLICY: no invented figures.",
    "warn_unverified_general": "Run warning: an external factual question was answered without retrieval and is labelled not source-backed.",
}

_JUDGE_KEYS: tuple[tuple[str, str], ...] = (
    ("correctness", "Correctness: grammar, spelling and meaning are right; nothing is added, lost or reversed compared with the English source."),
    ("naturalness", "Naturalness: reads like text written by a fluent professional, not like a translation."),
    ("register", "Register: the form of address (formal or informal) and the level of formality are appropriate for a careers-coaching product and consistent across the product. State which form is used."),
    ("terminology", "Terminology: product and career terms are consistent (the same English term always maps to the same word) and use the term that people in the field actually use."),
    ("policy_equivalence", "Policy-sentence equivalence: each sentence that states a rule (no unsourced salary, no statistic without a source, not source-backed, nothing saved without a yes) says exactly the same rule as the English, no stronger and no weaker."),
    ("english_leaks", "Absence of English leaks: no English word or phrase remains where the language has a normal word (names of the product, a protected slogan and widely used loanwords are acceptable; say which ones you accept)."),
    ("slogan", f"Protected slogan: the phrase \"{BRAND_SLOGAN}\" appears exactly as written, never translated, transliterated or re-punctuated, wherever it appears."),
)


# ------------------------------------------------------------------------------------------------------------------------------------------------ source loading
def load_catalogue(frontend: Path | None = None) -> dict[str, dict[str, str]]:
    """The merged interface catalogue as ``{locale: {"namespace.key": text}}`` through the esbuild helper (offline, read-only)."""
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("node is required to read the interface catalogue (frontend/scripts/dump-catalog-strings.mjs)")
    fe = frontend or FRONTEND
    proc = subprocess.run([node, "scripts/dump-catalog-strings.mjs"], cwd=str(fe), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"catalogue helper failed: {proc.stderr.strip()[:300]}")
    data = json.loads(proc.stdout)
    return {loc: dict(sorted(v.items())) for loc, v in sorted(data.items())}


_REF = re.compile(r"[\"'`]([A-Za-z][A-Za-z0-9]*\.[A-Za-z][A-Za-z0-9_]*)[\"'`]")
_NS_REF = re.compile(r"[\"'`]([A-Za-z][A-Za-z0-9]*)\.")


def scan_usage(keys: set[str], frontend: Path | None = None) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """Where the catalogue keys are referenced in the frontend source: (static references per key, files per namespace). Composed keys (``t(`ns.${x}`)``) are found only at namespace level."""
    fe = frontend or FRONTEND
    namespaces = {k.split(".", 1)[0] for k in keys}
    per_key: dict[str, set[str]] = {}
    per_ns: dict[str, set[str]] = {}
    for sub in ("app", "components", "lib"):
        base = fe / sub
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix not in (".ts", ".tsx") or "i18n/messages" in path.as_posix() or not path.is_file():
                continue
            rel = path.relative_to(fe).as_posix()
            try:
                text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for m in _REF.finditer(text):
                if m.group(1) in keys:
                    per_key.setdefault(m.group(1), set()).add(rel)
            for m in _NS_REF.finditer(text):
                if m.group(1) in namespaces:
                    per_ns.setdefault(m.group(1), set()).add(rel)
    return ({k: sorted(v) for k, v in per_key.items()}, {k: sorted(v) for k, v in per_ns.items()})


def _digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _d16(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------------------------------------------------------------------------------------ content model
def _hints(en: str, text: str, lang: str) -> list[str]:
    """Mechanical signals for a human (never a verdict): ``=EN`` identical to English, ``PH`` placeholders differ, ``EN?`` English-only words, ``SLOGAN`` protected slogan altered."""
    if lang == "en":
        return []
    out: list[str] = []
    if text.strip() == en.strip() and re.search(r"[A-Za-z]{4,}", text):
        out.append("=EN")
    if _inventory.placeholders(text) != _inventory.placeholders(en):
        out.append("PH")
    if _inventory.english_markers(text, lang):
        out.append("EN?")
    if BRAND_SLOGAN in en and BRAND_SLOGAN not in text:
        out.append("SLOGAN")
    return out


def _mail_table(lang: str) -> dict[str, dict[str, str]]:
    from src.mail import templates as mail

    return {kind: dict(parts) for kind, parts in sorted(mail._T.get(lang, {}).items())}


def _samples(bank: Mapping, lang: str) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for task in SAMPLE_TASKS:
        spec = bank["tasks"][task]
        for rkey, role in bank["roles"].items():
            out.append({"id": f"{task}:{rkey}", "kind": spec["kind"], "expected": spec["expected_behaviour"],
                        "en": spec["template"]["en"].replace("{role}", role["en"]), "text": spec["template"][lang].replace("{role}", role[lang])})
    return out


def build_content(catalogue: Mapping[str, Mapping[str, str]], lang: str, *, bank: Mapping | None = None, frontend: Path | None = None, usage: tuple | None = None) -> dict[str, Any]:
    """Everything a reviewer of ``lang`` reads, as one plain structure. Deterministic: no clock, no environment, no randomness."""
    if lang not in LANGUAGES:
        raise ValueError(f"{lang!r} is not an active candidate language")
    bank = bank if bank is not None else json.loads(BANK_FILE.read_text(encoding="utf-8"))
    en_cat, cat = catalogue["en"], catalogue[lang]
    per_key, per_ns = usage if usage is not None else scan_usage(set(en_cat), frontend)
    interface = []
    for key in sorted(en_cat):
        ns = key.split(".", 1)[0]
        group, note = _NAMESPACES.get(ns, (_OTHER_GROUP, _OTHER_NOTE))
        text = cat.get(key, "")
        interface.append({"key": key, "ns": ns, "group": group, "note": note, "en": en_cat[key], "text": text, "files": per_key.get(key, []), "hints": _hints(en_cat[key], text, lang)
                          + (["MISSING"] if key not in cat else [])})
    mo = []
    for s in _inventory.inventory():
        mo.append({"key": s.key, "category": s.category, "context": _MO_CONTEXT.get(s.key, f"Candidate-facing {s.category} sentence."), "wired": s.wired, "source": s.source,
                   "en": s.texts["en"], "text": s.texts[lang], "hints": _hints(s.texts["en"], s.texts[lang], lang)})
    mail_en, mail_l = _mail_table("en"), _mail_table(lang)
    email = []
    for kind in sorted(mail_en):
        for part in sorted(mail_en[kind]):
            text = mail_l.get(kind, {}).get(part, "")
            email.append({"id": f"{kind}.{part}", "en": mail_en[kind][part], "text": text, "hints": _hints(mail_en[kind][part], text, lang) + ([] if text else ["MISSING"])})
    samples = _samples(bank, lang)
    legal = [i for i in interface if i["ns"] in LEGAL_NAMESPACES]
    return {"language": lang, "language_name": LANGUAGE_NAMES[lang], "interface": interface, "namespace_files": per_ns, "mo": mo, "email": email, "samples": samples, "legal": legal,
            "open_english_only": [{"key": o.key, "english": o.english, "file": o.file} for o in _inventory.OPEN_ENGLISH_ONLY]}


def content_items(content: Mapping[str, Any]) -> dict[str, tuple[str, str]]:
    """Every reviewable item as ``{id: (english source, text in the language)}``; the unit of the freeze snapshot and of the diff."""
    items: dict[str, tuple[str, str]] = {}
    for i in content["interface"]:
        items[f"interface:{i['key']}"] = (i["en"], i["text"])
    for m in content["mo"]:
        items[f"mo:{m['key']}"] = (m["en"], m["text"])
    for e in content["email"]:
        items[f"email:{e['id']}"] = (e["en"], e["text"])
    for s in content["samples"]:
        items[f"sample:{s['id']}"] = (s["en"], s["text"])
    return items


def content_digest(content: Mapping[str, Any]) -> str:
    """Digest of the reviewable CONTENT only (items), independent of how it is rendered, so a layout change never invalidates a review."""
    return _digest({k: list(v) for k, v in sorted(content_items(content).items())})


# ------------------------------------------------------------------------------------------------------------------------------------------------ rendering
def _cell(text: str) -> str:
    return text.replace("\\", "\\\\").replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def _status_banner(lang: str) -> list[str]:
    return [f"> **STATUS: NOT REVIEWED. No reviewer is appointed (OD-LANG-03, OD-LANG-04) and no sign-off exists.** This pack is review material for {LANGUAGE_NAMES[lang]} (`{lang}`)."
            + (" The text is the English SOURCE." if lang == "en" else " Every non-English text in it is an ENGINEERING translation."),
            "> Generated by `scripts/language_review_pack.py --write`; do not edit by hand (a test fails if it drifts).", ""]


def render_interface(content: Mapping[str, Any]) -> str:
    lang, name = content["language"], content["language_name"]
    out = [f"# Interface strings for review: {name} (`{lang}`)", ""] + _status_banner(lang)
    out += ["Strings are grouped by surface (where a candidate meets them), then by catalogue namespace. `where` is the first frontend file that references the exact key; `composed` means the "
            "key is built in code (for example a status name), so see the namespace file list. Hints are mechanical signals for attention, never a verdict: `=EN` identical to English, "
            "`PH` placeholders differ from English, `EN?` English-only words present, `SLOGAN` protected slogan altered, `MISSING` no translation.", ""]
    groups: dict[str, dict[str, list[Mapping[str, Any]]]] = {}
    for i in content["interface"]:
        groups.setdefault(i["group"], {}).setdefault(i["ns"], []).append(i)
    ns_files: Mapping[str, list[str]] = content["namespace_files"]
    for group in sorted(groups, key=lambda g: (g == _OTHER_GROUP, g)):
        out += [f"## Surface: {group}", ""]
        for ns in sorted(groups[group]):
            rows = groups[group][ns]
            out += [f"### `{ns}` ({len(rows)} strings)", "", f"Context: {rows[0]['note']}", ""]
            files = ns_files.get(ns, [])
            out += [("Appears in: " + ", ".join(f"`{f}`" for f in files[:6]) + (f" and {len(files) - 6} more" if len(files) > 6 else "")) if files else "Appears in: no static reference found (composed or dynamic use).", ""]
            if lang == "en":
                out += ["| key | English source | where |", "|---|---|---|"]
                for r in rows:
                    out.append(f"| `{r['key']}` | {_cell(r['en'])} | {_where(r)} |")
            else:
                out += ["| key | English source | translation | where | hints |", "|---|---|---|---|---|"]
                for r in rows:
                    out.append(f"| `{r['key']}` | {_cell(r['en'])} | {_cell(r['text'])} | {_where(r)} | {' '.join(r['hints'])} |")
            out.append("")
    return "\n".join(out).rstrip() + "\n"


def _where(row: Mapping[str, Any]) -> str:
    files = row["files"]
    if not files:
        return "composed"
    short = files[0].rsplit("/", 1)[-1]
    return f"`{short}`" + (f" +{len(files) - 1}" if len(files) > 1 else "")


def render_mo(content: Mapping[str, Any]) -> str:
    lang, name = content["language"], content["language_name"]
    out = [f"# Mo-voiced sentences for review: {name} (`{lang}`)", ""] + _status_banner(lang)
    out += ["The Mo conversation language owns every sentence Mo says, including the deterministic text that stands in for the model. The sentences marked POLICY state a rule; judge that the rule "
            "is stated with exactly the English meaning (policy-sentence equivalence). Source: the 06C inventory (`docs/production/execution/evidence/06C_POLICY_SENTENCE_INVENTORY.md`).", "",
            "## Candidate-facing sentences", ""]
    hdr = ["| key | category | where it appears | English source | translation | hints |", "|---|---|---|---|---|---|"] if lang != "en" else \
          ["| key | category | where it appears | English source |", "|---|---|---|---|"]
    out += hdr
    for m in content["mo"]:
        base = f"| `{m['key']}` | {m['category']} | {_cell(m['context'])} | {_cell(m['en'])} |"
        out.append(base if lang == "en" else base + f" {_cell(m['text'])} | {' '.join(m['hints'])} |")
    out += ["", "## Transactional email (plain text; `{link}` and `{expiry}` are the only placeholders)", "",
            "Sent by `src/mail/templates.py` for identity flows (verification, password reset, account notice, administrator test)."]
    out += ["", "| id | English source |" + (" translation | hints |" if lang != "en" else ""), "|---|---|" + ("---|---|" if lang != "en" else "")]
    for e in content["email"]:
        row = f"| `{e['id']}` | {_cell(e['en'])} |"
        out.append(row if lang == "en" else row + f" {_cell(e['text'])} | {' '.join(e['hints'])} |")
    out += ["", "## Known gaps: still English-only in code", "", "These candidate-visible sentences are emitted in English by code that this package does not own. They cannot be reviewed in "
            f"{name} until the code is wired (see the 06C inventory); list them in your report if they matter to your sign-off.", "", "| key | file | English text |", "|---|---|---|"]
    for o in content["open_english_only"]:
        out.append(f"| `{o['key']}` | `{o['file']}` | {_cell(o['english'])} |")
    return "\n".join(out).rstrip() + "\n"


def render_samples(content: Mapping[str, Any]) -> str:
    lang, name = content["language"], content["language_name"]
    out = [f"# Interview question and feedback samples: {name} (`{lang}`)", ""] + _status_banner(lang)
    out += ["These are the SYNTHETIC prompts from `evaluations/language_ai/synthetic_prompt_bank.json` that ask the interviewer for a first question and for feedback. They contain no real "
            "person, company or conversation. They are the request side only: judge that each prompt reads naturally and means the same as the English. The replies a model produces "
            "to these prompts are reviewed through the blinded rating packet (06C / 06G), not here. The policy sentences are in `MO_SENTENCES.md`.", ""]
    out += ["| id | what a good reply does | English source |" + (" prompt in the language |" if lang != "en" else ""), "|---|---|---|" + ("---|" if lang != "en" else "")]
    for s in content["samples"]:
        row = f"| `{s['id']}` | {_cell(s['expected'])} | {_cell(s['en'])} |"
        out.append(row if lang == "en" else row + f" {_cell(s['text'])} |")
    return "\n".join(out).rstrip() + "\n"


def render_legal(content: Mapping[str, Any]) -> str:
    lang, name = content["language"], content["language_name"]
    out = [f"# Legal and privacy text for qualified review: {name} (`{lang}`)", ""] + _status_banner(lang)
    out += ["LG-10 needs a qualified person (counsel or a qualified legal translator) to review that the legal and privacy text is a faithful, legally accurate translation before any real "
            "user sees it in this language. This is a legal-translation review, not a legal-advice review: the English text is the source of record.", "",
            "## Where the legal text lives", "",
            "- Interface catalogue namespaces " + ", ".join(f"`{n}`" for n in LEGAL_NAMESPACES) + " (the full text is reproduced in the table below).",
            "- Legal document versions (terms, privacy, AI transparency) are versioned records served by the backend (`src/privacy`); their acceptance records are not part of this pack.",
            "- Transactional email (account notice and verification) is in `MO_SENTENCES.md`.",
            "- If `docs/production/legal_review/` exists in the release tree (the 05E legal review pack), the qualifier also reviews the documents listed there; this pack does not copy them "
            "and does not depend on them. If the directory is absent, say so in the evidence reference.", "",
            f"## Legal and trust strings ({len(content['legal'])})", ""]
    out += ["| key | English source |" + (" translation | hints |" if lang != "en" else ""), "|---|---|" + ("---|---|" if lang != "en" else "")]
    for r in content["legal"]:
        row = f"| `{r['key']}` | {_cell(r['en'])} |"
        out.append(row if lang == "en" else row + f" {_cell(r['text'])} | {' '.join(r['hints'])} |")
    return "\n".join(out).rstrip() + "\n"


def render_instructions(content: Mapping[str, Any]) -> str:
    lang, name = content["language"], content["language_name"]
    out = [f"# Reviewer instruction sheet: {name} (`{lang}`)", ""] + _status_banner(lang)
    out += ["## Who you are and what you are asked", "",
            f"You are a native speaker of {name} appointed by the owner (OD-LANG-03) to judge the text Ask4Mo shows to candidates, or (for the legal part) a qualified person appointed under "
            "OD-LANG-04. You are asked to judge text, not the product. Do not use a translation tool, search engine or AI assistant on the text; your judgement is the evidence.", "",
            "## What to judge", ""]
    out += [f"{n}. {text}" for n, (_, text) in enumerate(_JUDGE_KEYS, 1)]
    out += ["", "## How to mark a string", "",
            "Use one verdict per string: `OK`, `MINOR` (wording could be better, not wrong), `MAJOR` (wrong, unnatural or inconsistent; must be fixed), `BLOCKER` (changes a rule, legal meaning or the protected "
            "slogan; the language must not be offered until fixed). For anything other than `OK`, write the corrected text. Keep placeholders such as `{name}` untouched and in a position that "
            "reads naturally. A hint in the table is only a signal: decide for yourself.", "",
            "## Your files", "",
            "- `INTERFACE_STRINGS.md`: every interface string, grouped by surface, with the English source and where it appears.",
            "- `MO_SENTENCES.md`: the sentences Mo says (policy sentences, fallbacks, headings) and the transactional emails.",
            "- `INTERVIEW_SAMPLES.md`: synthetic interview question and feedback prompts.",
            "- `LEGAL_POINTERS.md`: the legal and privacy text (the legal qualifier's file).",
            "- `SIGNOFF_FORM.md` and `SIGNOFF_FORM.template.json`: the form you complete and sign at the end. It is blank on purpose.", "",
            "## Independence and conflicts", "",
            "You must not be the person who wrote or machine-translated the text you review, and you must not be paid in a way that depends on the outcome of your review. State any relationship "
            "with the owner or the product in the form. If you cannot say so truthfully, tell the owner before you start.", "",
            "## What your sign-off means and does not mean", "",
            "It covers THIS pack at the content digest printed in `README.md` and the release SHA the owner names, for the gate on the form (LG-11 native review, LG-10 legal translation). "
            "If the text changes later, you are sent only the changes (`CHANGES_SINCE_REVIEW`) and sign again at the new release SHA. The platform activates a language only from a complete record with your "
            "name, qualification, evidence reference, date and the release SHA; an engineering check never replaces your decision.", ""]
    return "\n".join(out).rstrip() + "\n"


# ------------------------------------------------------------------------------------------------------------------------------------------------ sign-off form
def form_template(lang: str, digest: str) -> dict[str, Any]:
    """The UNFILLED sign-off form. Every human field is an empty string; the only filled value is the generated pack digest (a reference, not a claim)."""
    def one(gate: str) -> dict[str, Any]:
        return {"gate": gate, "scope": "Native-language human review (interface text, Mo output samples, interview questions and feedback)" if gate == GATE_NATIVE
                else "Legal and privacy translation qualified (terms, privacy, AI transparency, consent text)",
                "reviewer_name": "", "qualification_statement": "", "independence_statement": "", "conflicts_declared": "", "evidence_reference": "",
                "approval_date": "", "release_sha": "", "approved_until": "", "pack_content_digest_reviewed": "", "verdict_summary": "", "state": "NOT SIGNED"}
    return {"schema": FORM_SCHEMA, "language": lang, "pack_content_digest_expected": digest, "forms": {g: one(g) for g in FORM_GATES},
            "note": "BLANK TEMPLATE. Nothing here is a sign-off. A form counts only when a named human completes it and the owner records it in docs/production/execution/language_readiness.json."}


FIELD_MAP: tuple[tuple[str, str, str], ...] = (
    ("reviewer_name", "gates.<LG>.approver", "named human; not empty, not a placeholder, not an automation or engineering label (language_activation.named_human)"),
    ("qualification_statement", "(kept in the signed form; cited by evidence)", "who the person is and why qualified (native speaker; legal translator or counsel); required by this protocol"),
    ("evidence_reference", "gates.<LG>.evidence", "at least 8 characters, not a placeholder: the path or identifier of the signed form and review report"),
    ("approval_date", "gates.<LG>.approved_on", "ISO date YYYY-MM-DD, not in the future"),
    ("release_sha", "gates.<LG>.release_sha AND languages.<code>.release_sha", "7-40 lowercase hex characters; identical for the locale and every one of its fourteen gates"),
    ("approved_until", "gates.<LG>.approved_until (optional)", "ISO date; when it has passed the gate is stale"),
)


def validate_form(form: Mapping[str, Any], gate: str, *, expected_digest: str | None = None, today: date | None = None) -> list[str]:
    """Report what is missing or invalid in a COMPLETED form for ``gate``. Empty list means the form is complete enough to be recorded by the owner; it records nothing and approves nothing."""
    problems: list[str] = []
    now = today or datetime.now(timezone.utc).date()
    if form.get("schema") != FORM_SCHEMA:
        problems.append("schema is not the sign-off form schema")
    lang = form.get("language")
    if lang not in LANGUAGES:
        problems.append("language is not an active candidate language")
    f = (form.get("forms") or {}).get(gate) if isinstance(form.get("forms"), dict) else None
    if gate not in FORM_GATES or not isinstance(f, dict):
        return problems + [f"no form for gate {gate!r}"]
    if not named_human(f.get("reviewer_name")):
        problems.append("reviewer_name is not a named human")
    stmt = f.get("qualification_statement")
    if not (isinstance(stmt, str) and len(stmt.strip()) >= 20 and stmt.strip().lower() not in _PLACEHOLDER_WORDS):
        problems.append("qualification_statement is missing or too short")
    ind = f.get("independence_statement")
    if not (isinstance(ind, str) and len(ind.strip()) >= 10):
        problems.append("independence_statement is missing")
    if not isinstance(f.get("conflicts_declared"), str) or not f.get("conflicts_declared", "").strip():
        problems.append("conflicts_declared is empty (write NONE explicitly if there are none)")
    ev = f.get("evidence_reference")
    if not (isinstance(ev, str) and len(ev.strip()) >= 8 and ev.strip().lower() not in _PLACEHOLDER_WORDS):
        problems.append("evidence_reference is missing")
    d = _iso_date(f.get("approval_date"))
    if d is None:
        problems.append("approval_date is not a valid ISO date")
    elif d > now:
        problems.append("approval_date is in the future")
    sha = f.get("release_sha")
    if not (isinstance(sha, str) and _SHA.fullmatch(sha)):
        problems.append("release_sha is missing or malformed")
    until = f.get("approved_until")
    if until not in ("", None):
        u = _iso_date(until)
        if u is None:
            problems.append("approved_until is not a valid ISO date")
        elif u < now:
            problems.append("approved_until has passed")
    reviewed = f.get("pack_content_digest_reviewed")
    if not (isinstance(reviewed, str) and re.fullmatch(r"[0-9a-f]{64}", reviewed)):
        problems.append("pack_content_digest_reviewed is missing")
    elif expected_digest and reviewed != expected_digest:
        problems.append("pack_content_digest_reviewed differs from the current pack (the text changed since the review)")
    if not (isinstance(f.get("verdict_summary"), str) and f["verdict_summary"].strip()):
        problems.append("verdict_summary is missing")
    return problems


def gate_fragment(form: Mapping[str, Any], gate: str) -> dict[str, str]:
    """The ``language_readiness.json`` gate fields that a COMPLETED, valid form maps to. Call only after ``validate_form`` returned no problems; the owner records it by hand."""
    f = form["forms"][gate]
    out = {"evidence": f["evidence_reference"].strip(), "approver": f["reviewer_name"].strip(), "approved_on": f["approval_date"], "release_sha": f["release_sha"]}
    if f.get("approved_until"):
        out["approved_until"] = f["approved_until"]
    return out


def render_form_md(lang: str, digest: str) -> str:
    name = LANGUAGE_NAMES[lang]
    out = [f"# Sign-off form: {name} (`{lang}`)", ""] + _status_banner(lang)
    out += ["**This form is BLANK and must stay blank in the repository.** Only the named human fills it, and only the owner records the result. One form per gate; the same person may sign both "
            "only if qualified for both (a native reviewer is not automatically a legal qualifier).", "",
            f"Pack content digest (SHA-256 of the reviewed content): `{digest}`", ""]
    for gate in FORM_GATES:
        label = "LG-11 Native-language human review" if gate == GATE_NATIVE else "LG-10 Legal and privacy translation qualified"
        out += [f"## {label}", "",
                "| Field | Value | Maps to in `language_readiness.json` |", "|---|---|---|",
                "| Named reviewer (full name) | ____________________ | `gates." + gate + ".approver` |",
                "| Qualification statement (who you are; why qualified) | ____________________ | kept in this form; cited by the evidence reference |",
                "| Independence statement (not the author; not paid by the author's incentives) | ____________________ | kept in this form |",
                "| Conflicts declared (write NONE if none) | ____________________ | kept in this form |",
                "| Evidence reference (path or id of the signed form and your review report) | ____________________ | `gates." + gate + ".evidence` |",
                "| Approval date (YYYY-MM-DD) | ____________________ | `gates." + gate + ".approved_on` |",
                "| Release SHA reviewed (given by the owner) | ____________________ | `gates." + gate + ".release_sha` and `languages." + lang + ".release_sha` |",
                "| Approved until (optional, YYYY-MM-DD) | ____________________ | `gates." + gate + ".approved_until` |",
                "| Pack content digest you reviewed | ____________________ | kept in this form; must equal the digest above |",
                "| Verdict summary (counts of OK / MINOR / MAJOR / BLOCKER, open items) | ____________________ | kept in this form |", "",
                "Signature of the named reviewer: ____________________   (a typed name is not a signature of record; the owner decides what counts)", ""]
    out += ["The machine-readable twin is `SIGNOFF_FORM.template.json`. `python scripts/language_review_pack.py --validate-form FILE --gate LG-11` reports what is missing; it writes nothing.", ""]
    return "\n".join(out).rstrip() + "\n"


def render_readme(lang: str, content: Mapping[str, Any], digest: str, file_digests: Mapping[str, str]) -> str:
    name = LANGUAGE_NAMES[lang]
    hint_counts: dict[str, int] = {}
    for part in ("interface", "mo", "email"):
        for r in content[part]:
            for h in r["hints"]:
                hint_counts[h] = hint_counts.get(h, 0) + 1
    other = sorted({i["ns"] for i in content["interface"] if i["group"] == _OTHER_GROUP})
    out = [f"# Review pack: {name} (`{lang}`)", ""] + _status_banner(lang)
    out += ["| Item | Value |", "|---|---|",
            f"| Interface strings | {len(content['interface'])} |", f"| Mo-voiced sentences | {len(content['mo'])} |", f"| Email parts | {len(content['email'])} |",
            f"| Interview samples (synthetic prompts) | {len(content['samples'])} |", f"| Legal and trust strings | {len(content['legal'])} |",
            f"| Pack content digest (SHA-256) | `{digest}` |", "| Mechanical hints (for attention only) | " + (", ".join(f"{k}: {v}" for k, v in sorted(hint_counts.items())) or "none") + " |",
            f"| Namespaces without a curated context note | {', '.join(f'`{n}`' for n in other) or 'none'} |", f"| Generator | {GENERATOR_VERSION} |", ""]
    out += ["## Files", "", "| File | SHA-256 |", "|---|---|"]
    out += [f"| `{f}` | `{file_digests[f]}` |" for f in FILES if f in file_digests]
    out += ["", "## Start here", "", "1. Read `INSTRUCTIONS.md`.", "2. Review `INTERFACE_STRINGS.md`, `MO_SENTENCES.md`, `INTERVIEW_SAMPLES.md` (native reviewer) or `LEGAL_POINTERS.md` (legal qualifier).",
            "3. Complete `SIGNOFF_FORM.md` (or the JSON twin) and return it with your review report to the owner.", "",
            "## If the text changes after your review", "",
            "The owner freezes a release SHA (`python scripts/language_review_pack.py --freeze --release-sha SHA --out DIR`), which stores a snapshot of every item's digest. After later changes, "
            f"`python scripts/language_review_pack.py --diff --baseline DIR/FREEZE_SNAPSHOT.json --language {lang} --out DIR2` lists exactly which items were added, removed, re-sourced or re-translated, so only those are re-reviewed.", ""]
    return "\n".join(out).rstrip() + "\n"


# ------------------------------------------------------------------------------------------------------------------------------------------------ build / check
def build_pack(catalogue: Mapping[str, Mapping[str, str]], lang: str, *, bank: Mapping | None = None, frontend: Path | None = None, usage: tuple | None = None) -> dict[str, str]:
    """All files of one language's pack as ``{file name: text}`` (deterministic)."""
    content = build_content(catalogue, lang, bank=bank, frontend=frontend, usage=usage)
    digest = content_digest(content)
    files = {"INSTRUCTIONS.md": render_instructions(content), "INTERFACE_STRINGS.md": render_interface(content), "MO_SENTENCES.md": render_mo(content),
             "INTERVIEW_SAMPLES.md": render_samples(content), "LEGAL_POINTERS.md": render_legal(content), "SIGNOFF_FORM.md": render_form_md(lang, digest),
             "SIGNOFF_FORM.template.json": json.dumps(form_template(lang, digest), ensure_ascii=False, indent=2, sort_keys=True) + "\n"}
    file_digests = {n: hashlib.sha256(t.encode("utf-8")).hexdigest() for n, t in files.items()}
    files["README.md"] = render_readme(lang, content, digest, file_digests)
    return {n: files[n] for n in FILES}


def build_manifest(catalogue: Mapping[str, Mapping[str, str]], packs: Mapping[str, Mapping[str, str]], contents: Mapping[str, Mapping[str, Any]], *, freeze_sha: str | None = None) -> dict[str, Any]:
    langs: dict[str, Any] = {}
    for lang in LANGUAGES:
        langs[lang] = {"content_digest": content_digest(contents[lang]), "interface_keys": len(contents[lang]["interface"]), "items": len(content_items(contents[lang])),
                       "files": {n: hashlib.sha256(t.encode("utf-8")).hexdigest() for n, t in sorted(packs[lang].items())}}
    return {"schema": MANIFEST_SCHEMA, "package": "06F", "generator": GENERATOR_VERSION,
            "status": "NOT FROZEN: the owner has not named a freeze SHA" if freeze_sha is None else "FROZEN at the named release SHA (a freeze is not a review: no language is reviewed)",
            "freeze_sha": freeze_sha, "reviewed": False, "signoffs_recorded": 0, "english_source_digest": langs["en"]["content_digest"],
            "note": "Digests identify exactly what a reviewer was shown. This file records no review, no reviewer and no approval; those live only in signed forms and docs/production/execution/language_readiness.json.",
            "languages": langs}


def build_all(catalogue: Mapping[str, Mapping[str, str]] | None = None, *, bank: Mapping | None = None, frontend: Path | None = None) -> tuple[dict[str, dict[str, str]], dict[str, Any], dict[str, dict]]:
    """(packs per language, freeze manifest, contents per language). The usage scan is done once and shared."""
    cat = catalogue if catalogue is not None else load_catalogue(frontend)
    usage = scan_usage(set(cat["en"]), frontend)
    contents = {lang: build_content(cat, lang, bank=bank, frontend=frontend, usage=usage) for lang in LANGUAGES}
    packs = {lang: build_pack(cat, lang, bank=bank, frontend=frontend, usage=usage) for lang in LANGUAGES}
    return packs, build_manifest(cat, packs, contents), contents


def manifest_text(manifest: Mapping[str, Any]) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def write_all(packs: Mapping[str, Mapping[str, str]], manifest: Mapping[str, Any], out: Path | None = None) -> list[Path]:
    base = Path(out) if out else PACK_DIR
    written: list[Path] = []
    for lang, files in packs.items():
        for name, text in files.items():
            p = base / lang / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
            written.append(p)
    mp = base / MANIFEST_NAME
    mp.write_text(manifest_text(manifest), encoding="utf-8")
    return written + [mp]


def check_all(packs: Mapping[str, Mapping[str, str]], manifest: Mapping[str, Any], base: Path | None = None) -> list[str]:
    """Differences between the generated packs and the committed ones (empty when current)."""
    root = Path(base) if base else PACK_DIR
    stale: list[str] = []
    for lang, files in packs.items():
        for name, text in files.items():
            p = root / lang / name
            if not p.exists() or p.read_text(encoding="utf-8") != text:
                stale.append(f"{lang}/{name}")
    mp = root / MANIFEST_NAME
    if not mp.exists() or mp.read_text(encoding="utf-8") != manifest_text(manifest):
        stale.append(MANIFEST_NAME)
    return stale


# ------------------------------------------------------------------------------------------------------------------------------------------------ freeze and diff
def build_snapshot(contents: Mapping[str, Mapping[str, Any]], manifest: Mapping[str, Any], release_sha: str) -> dict[str, Any]:
    """Per-item digests of every language at a named release SHA. Short digests (16 hex) identify an item; the old text is recoverable from git at the release SHA."""
    if not _SHA.fullmatch(release_sha or ""):
        raise ValueError("release SHA must be 7 to 40 lowercase hex characters")
    langs = {}
    for lang in LANGUAGES:
        langs[lang] = {"content_digest": content_digest(contents[lang]),
                       "items": {iid: {"en": _d16(en), "tr": _d16(tr)} for iid, (en, tr) in sorted(content_items(contents[lang]).items())}}
    frozen = dict(manifest)
    frozen["freeze_sha"] = release_sha
    frozen["status"] = "FROZEN at the named release SHA (a freeze is not a review: no language is reviewed)"
    return {"schema": SNAPSHOT_SCHEMA, "release_sha": release_sha, "manifest": frozen, "languages": langs}


def diff_against(snapshot: Mapping[str, Any], content: Mapping[str, Any]) -> dict[str, Any]:
    """Which items of ``content`` changed since ``snapshot``: added, removed, ``source_changed`` (English changed, translation must be re-checked), ``text_changed`` (translation changed)."""
    lang = content["language"]
    base = snapshot["languages"][lang]["items"]
    now = content_items(content)
    added = sorted(set(now) - set(base))
    removed = sorted(set(base) - set(now))
    source, text, same = [], [], 0
    for iid in sorted(set(now) & set(base)):
        en, tr = now[iid]
        b = base[iid]
        en_changed, tr_changed = _d16(en) != b["en"], _d16(tr) != b["tr"]
        if en_changed:
            source.append(iid)
        elif tr_changed:
            text.append(iid)
        else:
            same += 1
    return {"language": lang, "baseline_release_sha": snapshot["release_sha"], "added": added, "removed": removed, "source_changed": source, "text_changed": text,
            "unchanged": same, "needs_rereview": len(added) + len(source) + len(text), "baseline_digest": snapshot["languages"][lang]["content_digest"], "current_digest": content_digest(content)}


def render_changes_md(diff: Mapping[str, Any], content: Mapping[str, Any]) -> str:
    lang, name = diff["language"], content["language_name"]
    items = content_items(content)
    out = [f"# Changes since review: {name} (`{lang}`)", "", f"> Baseline: release SHA `{diff['baseline_release_sha']}`, content digest `{diff['baseline_digest']}`. Current content digest `{diff['current_digest']}`.",
           "> STATUS: NOT REVIEWED. This list narrows the re-review; it does not replace the reviewer's judgement and a new sign-off at a new release SHA is still required.", "",
           f"- Items needing re-review: **{diff['needs_rereview']}** (added {len(diff['added'])}, English source changed {len(diff['source_changed'])}, translation changed {len(diff['text_changed'])})",
           f"- Removed since the baseline: {len(diff['removed'])} (nothing to review)", f"- Unchanged: {diff['unchanged']}", ""]
    for label, ids in (("Added", diff["added"]), ("English source changed (re-check the translation)", diff["source_changed"]), ("Translation changed (re-review)", diff["text_changed"])):
        out += [f"## {label}", ""]
        if not ids:
            out += ["None.", ""]
            continue
        out += ["| item | English source |" + (" translation |" if lang != "en" else ""), "|---|---|" + ("---|" if lang != "en" else "")]
        for iid in ids:
            en, tr = items[iid]
            out.append(f"| `{iid}` | {_cell(en)} |" + (f" {_cell(tr)} |" if lang != "en" else ""))
        out.append("")
    if diff["removed"]:
        out += ["## Removed items", ""] + [f"- `{iid}`" for iid in diff["removed"]] + [""]
    return "\n".join(out).rstrip() + "\n"
