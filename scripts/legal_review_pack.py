#!/usr/bin/env python
"""05E legal review pack generator (PRIV-LEGAL, K-PRIV, K-AIGUID). Offline, deterministic, no provider call, no network.

Generates, from the product's own catalogues, the REVIEW-READY material counsel needs: the exact current Privacy, Terms and AI-transparency texts per language
(in the order the page shows them), the in-product AI-guidance and source wording, the fact map (each statement mapped to the code that makes it true) and a diff-able
change list of PROPOSED edits. It never edits a product text, never records a sign-off and never claims legal compliance: legal review stays open (LG-10, PG-04).

Output directory: ``docs/production/legal_review/`` with ``--write``; otherwise a temp directory. ``--check`` fails when the committed files are stale (the generated files
are byte-stable: no timestamps). Imports ``tests.conftest`` first (test isolation) because it reads the backend's deterministic Mo wording tables.

Usage:
    python scripts/legal_review_pack.py --check
    python scripts/legal_review_pack.py --write
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tests.conftest  # noqa: E402,F401  (test isolation: temp DB, no .env)

ROOT = Path(__file__).resolve().parent.parent
FE = ROOT / "frontend"
PACK = ROOT / "docs/production/legal_review"
SOURCE = PACK / "source"

OFFERED = ("en", "de", "fr", "es", "it", "pt", "nl")
PRESERVED_EXCLUDED = ("ru",)
UPDATED_RE = re.compile(r'updated="([^"]+)"')

DOCUMENTS = {
    "privacy": ("Privacy", "/privacy", "frontend/components/marketing/PrivacyContent.tsx"),
    "terms": ("Terms of use", "/terms", "frontend/components/marketing/TermsContent.tsx"),
    "ai_transparency": ("AI transparency and responsible use", "/ai-transparency", "frontend/components/marketing/AiTransparencyContent.tsx"),
}

# In-product AI-guidance and source wording (K-AIGUID): frontend keys by prefix or exact key.
AI_GUIDANCE_PREFIXES = ("provenance.", "trustUx.", "researchEvidence.", "sources.", "packUx.lim_")
AI_GUIDANCE_KEYS = ("practice.evalDisclaimer", "packUx.disclaimer", "states.aiUsageLimit", "workflow.feedbackAsk4mo", "help.priv4a", "help.prac2a")
# Other legal-relevant pages and in-app copy, listed in catalogue order.
EXTRA_NAMESPACES = (("trust", "Trust page (public claims about data handling)"), ("dataPrivacy", "In-app Data & Privacy copy (export, deletion, sharing statements)"))

STATUS_ORDER = ("CONTRADICTED_BY_CODE", "PARTIAL", "NOT_VERIFIED", "UNSTATED_FACT", "NOT_A_CODE_FACT", "VERIFIED_IN_CODE")


# ---------------------------------------------------------------------------------------------------------------------------------- inputs
def load_catalogs() -> dict[str, dict[str, str]]:
    node = shutil.which("node")
    if node is None:
        raise RuntimeError("node is required to read the catalogues")
    proc = subprocess.run([node, "scripts/dump-legal-texts.mjs"], cwd=str(FE), capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"catalogue helper failed: {proc.stderr.strip()[:300]}")
    return json.loads(proc.stdout)


def parse_page(tsx_rel: str) -> dict:
    """The ordered blocks of a legal page component: {'title_key', 'updated', 'blocks': [(kind, [keys])]}. Any line that renders a catalogue key but is not understood
    is an ERROR, so the generator can never silently skip text."""
    src = (ROOT / tsx_rel).read_text(encoding="utf-8")
    title = re.search(r'title=\{t\("([\w.]+)"\)\}', src)
    updated = UPDATED_RE.search(src)
    body = src.split("<LegalPage", 1)[1].split("</LegalPage>", 1)[0]
    blocks: list[tuple[str, list[str]]] = []
    for raw in body.splitlines()[1:]:
        line = raw.strip()
        if not line or line in ("<ul>", "</ul>", ">") or line.startswith("title=") or "t(" not in line:
            continue
        keys = re.findall(r't\("([\w.]+)"\)', line)
        if line.startswith("<h2>"):
            blocks.append(("h2", keys))
        elif line.startswith("<p>"):
            blocks.append(("p", keys))
        elif line.startswith("<li><strong>"):
            blocks.append(("li_pair", keys))
        elif line.startswith("<li>"):
            blocks.append(("li", keys))
        else:
            raise RuntimeError(f"unparsed legal page line in {tsx_rel}: {line}")
    if not title or not updated:
        raise RuntimeError(f"cannot read the title or date of {tsx_rel}")
    return {"title_key": title.group(1), "updated": updated.group(1), "blocks": blocks}


def backend_wording(code: str) -> list[tuple[str, str]]:
    """Deterministic Mo-voiced text (the model-unavailable and insufficient-evidence wording), one row per fixed string for ``code``."""
    from src.copilot.rag import localized as L

    rows: list[tuple[str, str]] = []
    h = L.SECTION_HEADINGS.get(code)
    if h:
        rows += [("SECTION_HEADINGS[evidence]", h[0]), ("SECTION_HEADINGS[tools]", h[1]), ("SECTION_HEADINGS[recommendation]", h[2])]
    for name in ("INSUFFICIENT", "COMPENSATION_GUIDANCE", "UNVERIFIED_GENERAL", "UNRETRIEVED_LIMITATION"):
        v = getattr(L, name).get(code)
        if v:
            rows.append((name, v))
    for k, v in sorted((L.FALLBACK.get(code) or {}).items()):
        rows.append((f"FALLBACK[{k}]", v))
    return rows


# ---------------------------------------------------------------------------------------------------------------------------------- rendering
def _fmt(blocks_text: list[str]) -> str:
    return "\n".join(blocks_text)


def render_blocks(page: dict, cat: dict[str, str], *, overrides: dict[str, str] | None = None, inserts: dict[str, list[tuple[str, str, str]]] | None = None) -> list[str]:
    """Markdown lines for one page. ``overrides`` replaces the text of a key (proposals); ``inserts`` adds (new_key, kind, text) after a key."""
    overrides = overrides or {}
    inserts = inserts or {}
    out: list[str] = []

    def text(k: str) -> str:
        return overrides.get(k, cat[k])

    def after(keys: list[str]) -> None:
        for k in keys:
            for new_key, kind, body in inserts.get(k, []):
                out.append(f"- {body}  `{new_key}` **[PROPOSED INSERT]**" if kind == "li" else f"{body}  `{new_key}` **[PROPOSED INSERT]**")
                out.append("")
    for kind, keys in page["blocks"]:
        if kind == "h2":
            out.append("")
            out.append(f"#### {text(keys[0])}  `{keys[0]}`")
            out.append("")
        elif kind == "p":
            out.append(f"{text(keys[0])}  `{keys[0]}`")
            out.append("")
        elif kind == "li":
            out.append(f"- {text(keys[0])}  `{keys[0]}`")
        elif kind == "li_pair":
            out.append(f"- **{text(keys[0])}**: {text(keys[1])}  `{keys[0]}` + `{keys[1]}`")
        after(keys)
    return out


def render_locale(code: str, name: str, cats: dict[str, dict[str, str]], pages: dict[str, dict]) -> str:
    cat = cats[code]
    excluded = code in PRESERVED_EXCLUDED
    out = [f"# Legal review pack: exact current texts, `{code}` ({name})", "",
           "GENERATED by `scripts/legal_review_pack.py` from the product catalogues. Do not edit by hand; run `python scripts/legal_review_pack.py --write`.", ""]
    if excluded:
        out += ["**Status: PRESERVED BUT EXCLUDED from the offered languages (REQ-LANG-14).** This text is kept in the product code and is not shown to users. It is listed so that a later "
                "activation starts from the exact current text.", ""]
    else:
        out += ["**Status: " + ("SOURCE-LANGUAGE ENGINEERING DRAFT" if code == "en" else "ENGINEERING TRANSLATION") + ". NOT reviewed by counsel or a native legal reviewer. Counsel sign-off for this language: NOT DONE.**", ""]
    out += ["## 0. Shared page elements", "",
            f"- Draft banner shown on every legal page: {cat['marketing.draftBanner']}  `marketing.draftBanner`",
            f"- Last-updated line (date shown: {pages['privacy']['updated']}): {cat['marketing.lastUpdated']}  `marketing.lastUpdated`", ""]
    for i, (doc, (title, path, tsx)) in enumerate(DOCUMENTS.items(), start=1):
        page = pages[doc]
        out += [f"## {i}. {title} (`{path}`)", "", f"Source component: `{tsx}`. Page title: {cat[page['title_key']]}  `{page['title_key']}`. Date shown: {page['updated']}.", ""]
        out += render_blocks(page, cat)
        out.append("")
    n = len(DOCUMENTS) + 1
    for ns, label in EXTRA_NAMESPACES:
        keys = [k for k in cat if k.split(".")[0] == ns]
        out += [f"## {n}. {label}", "", f"Namespace `{ns}`, {len(keys)} strings, in catalogue order (not page order).", ""]
        out += [f"- `{k}`: {cat[k]}" for k in keys]
        out.append("")
        n += 1
    guid = [k for k in cat if k.startswith(AI_GUIDANCE_PREFIXES) or k in AI_GUIDANCE_KEYS]
    out += [f"## {n}. In-product AI-guidance and source wording (K-AIGUID)", "",
            f"{len(guid)} interface strings that describe AI output, sources, limits and practice-feedback status, in catalogue order. Wording that Mo itself produces in a "
            "conversation is model output and is not listed; the fixed wording below is produced WITHOUT a model.", ""]
    out += [f"- `{k}`: {cat[k]}" for k in guid]
    out += ["", f"### {n}.1 Deterministic Mo wording (backend, no model call)", "", "Source: `src/copilot/rag/localized.py`. Used for section headings, the insufficient-evidence sentence, the compensation and unverified-general notices and the model-unavailable fallback.", ""]
    out += [f"- `{k}`: {v}" for k, v in backend_wording(code)]
    out.append("")
    return "\n".join(out)


def document_hashes(code: str, cats: dict[str, dict[str, str]], pages: dict[str, dict]) -> dict[str, dict]:
    cat = cats[code]
    res = {}
    for doc in DOCUMENTS:
        keys = [cat_key for _kind, ks in pages[doc]["blocks"] for cat_key in ks] + [pages[doc]["title_key"]]
        joined = "\n".join(f"{k}\t{cat[k]}" for k in keys)
        res[doc] = {"strings": len(keys), "sha256": hashlib.sha256(joined.encode("utf-8")).hexdigest()}
    return res


def render_manifest(cats: dict, pages: dict) -> str:
    data = {"about": "Per-language, per-document digest of the exact current text (key and value, in page order). A change to any legal string changes its digest; regenerate with scripts/legal_review_pack.py --write.",
            "offered": list(OFFERED), "preserved_excluded": list(PRESERVED_EXCLUDED),
            "date_shown": {d: pages[d]["updated"] for d in DOCUMENTS},
            "locales": {code: document_hashes(code, cats, pages) for code in OFFERED + PRESERVED_EXCLUDED}}
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


# ---------------------------------------------------------------------------------------------------------------------------------- facts
def load_json(name: str) -> dict:
    return json.loads((SOURCE / name).read_text(encoding="utf-8"))


def render_facts(cat_en: dict[str, str]) -> str:
    data = load_json("facts.json")
    facts = data["facts"]
    counts = {s: sum(1 for f in facts if f["status"] == s) for s in STATUS_ORDER}
    out = ["# Data-flow and retention facts the legal texts rely on", "",
           "GENERATED by `scripts/legal_review_pack.py` from `source/facts.json` and the English catalogue. Do not edit by hand.", "",
           "Every statement in the current Privacy, Terms and AI-transparency texts is mapped below to the code that makes it true, with an ENGINEERING status. A status is a reading of "
           "the code at the commit this pack was generated against; it is not a legal conclusion, and `VERIFIED_IN_CODE` means only that the code does this and a test or evaluator "
           "exercises it offline. Code references are `file :: symbol` and are checked by `tests/test_legal_review_pack_05e.py`. Hosted behaviour, live providers and human review are "
           "NOT covered.", "", "## Summary", "", "| Status | Entries |", "|---|---|"]
    out += [f"| {s} | {counts[s]} |" for s in STATUS_ORDER]
    out += ["", "## Findings that need attention first", ""]
    for status in ("CONTRADICTED_BY_CODE", "PARTIAL", "NOT_VERIFIED"):
        for f in facts:
            if f["status"] == status:
                out.append(f"- **{f['id']} ({status})**: {f['fact']}")
    out += [""]
    for doc, title in (("privacy", "Privacy text"), ("terms", "Terms text"), ("ai_transparency", "AI-transparency text"), ("data_flow", "Facts the texts do not state (data flows, retention, access)")):
        out += [f"## {title}", ""]
        for f in (x for x in facts if x["document"] == doc):
            out.append(f"### {f['id']}: {f['status']}")
            out.append("")
            if f["keys"]:
                out.append("Statement (exact current English):")
                out.append("")
                for k in f["keys"]:
                    out.append(f"> {cat_en[k]}  `{k}`")
                out.append("")
            out.append(f"Fact: {f['fact']}")
            out.append("")
            if f["refs"]:
                out.append("Code:")
                for ref in f["refs"]:
                    pending = " (lands with the 05E engineering PR)" if len(ref) > 2 else ""
                    out.append(f"- `{ref[0]}` :: `{ref[1]}`{pending}")
                out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------------------------------------------- change list
def word_diff(old: str, new: str) -> str:
    a, b = old.split(), new.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(" ".join(a[i1:i2]))
        else:
            if i2 > i1:
                out.append("~~" + " ".join(a[i1:i2]) + "~~")
            if j2 > j1:
                out.append("**" + " ".join(b[j1:j2]) + "**")
    return " ".join(out)


def render_change_list(cat_en: dict[str, str]) -> str:
    props = load_json("proposals.json")["proposals"]
    out = ["# Proposed copy changes (NOT APPLIED)", "",
           "GENERATED by `scripts/legal_review_pack.py` from `source/proposals.json` and the English catalogue. Do not edit by hand.", "",
           "**These are proposals for counsel and the owner. None is applied to the product, none is legal advice and none is approved.** The legal page copy is unchanged by this "
           "package. Square brackets mark content that only the owner or counsel can supply. Every approved proposal would need translation into the seven offered languages and a "
           "native legal review (LG-10) before it ships. To see the whole English text with the proposals applied, diff `texts/en.md` against `proposed/en_with_proposals.md`.", "",
           "| Id | Action | Key | Facts | Open questions |", "|---|---|---|---|---|"]
    for p in props:
        key = p["key"] if p["action"] == "replace" else f"{p['new_key']} (after {p['after_key']})"
        out.append(f"| {p['id']} | {p['action']} | `{key}` | {', '.join(p['facts'])} | {', '.join(p['questions']) or '-'} |")
    out.append("")
    for p in props:
        out += [f"## {p['id']}: {p['action']} `{p['key'] if p['action'] == 'replace' else p['new_key']}`", ""]
        out.append(f"Why: {p['reason']}")
        out.append("")
        if p["action"] == "replace":
            out += ["Current:", "", f"> {cat_en[p['key']]}", "", "Proposed:", "", f"> {p['proposed']}", "", "Word diff (struck = removed, bold = added):", "", f"> {word_diff(cat_en[p['key']], p['proposed'])}", ""]
        else:
            out += [f"Insert after `{p['after_key']}` (current text: {cat_en[p['after_key']]}):", "", f"> {p['proposed']}", ""]
        out.append(f"Facts: {', '.join(p['facts'])}. Open questions: {', '.join(p['questions']) or 'none'}. Status: PROPOSED, not approved.")
        out.append("")
    return "\n".join(out)


def render_proposed_en(cats: dict, pages: dict) -> str:
    props = load_json("proposals.json")["proposals"]
    overrides = {p["key"]: p["proposed"] for p in props if p["action"] == "replace"}
    inserts: dict[str, list[tuple[str, str, str]]] = {}
    for p in props:
        if p["action"] == "insert_after":
            inserts.setdefault(p["after_key"], []).append((p["new_key"], p["kind"], p["proposed"]))
    cat = cats["en"]
    out = ["# English texts with the PROPOSED changes applied (NOT APPLIED to the product)", "",
           "GENERATED by `scripts/legal_review_pack.py`. Diff against `texts/en.md` to see every proposed change in context. Proposals are listed in `CHANGE_LIST.md`. Not approved, not legal advice.", ""]
    for i, (doc, (title, path, tsx)) in enumerate(DOCUMENTS.items(), start=1):
        page = pages[doc]
        out += [f"## {i}. {title} (`{path}`)", "", f"Source component: `{tsx}`. Page title: {cat[page['title_key']]}  `{page['title_key']}`. Date shown: {page['updated']}.", ""]
        out += render_blocks(page, cat, overrides=overrides, inserts=inserts)
        out.append("")
    return "\n".join(out)


# ---------------------------------------------------------------------------------------------------------------------------------- build
def build() -> dict[str, str]:
    from src.locales import LANGUAGE_NAMES

    cats = load_catalogs()
    pages = {doc: parse_page(tsx) for doc, (_t, _p, tsx) in DOCUMENTS.items()}
    files: dict[str, str] = {}
    for code in OFFERED:
        files[f"texts/{code}.md"] = render_locale(code, LANGUAGE_NAMES.get(code, code), cats, pages) + "\n"
    for code in PRESERVED_EXCLUDED:
        files[f"texts/{code}_PRESERVED_EXCLUDED.md"] = render_locale(code, LANGUAGE_NAMES.get(code, code), cats, pages) + "\n"
    files["texts/MANIFEST.json"] = render_manifest(cats, pages)
    files["FACTS.md"] = render_facts(cats["en"]) + "\n"
    files["CHANGE_LIST.md"] = render_change_list(cats["en"]) + "\n"
    files["proposed/en_with_proposals.md"] = render_proposed_en(cats, pages) + "\n"
    return files


def write(files: dict[str, str], base: Path) -> None:
    for rel, text in files.items():
        p = base / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def stale(files: dict[str, str], base: Path) -> list[str]:
    return [rel for rel, text in files.items() if not (base / rel).is_file() or (base / rel).read_text(encoding="utf-8") != text]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Generate the 05E legal review pack (texts, facts, change list).")
    ap.add_argument("--write", action="store_true", help="Write into docs/production/legal_review/ (otherwise a temp directory).")
    ap.add_argument("--check", action="store_true", help="Fail when the committed generated files are stale.")
    args = ap.parse_args(argv)
    files = build()
    if args.check:
        bad = stale(files, PACK)
        if bad:
            print("STALE: " + ", ".join(bad) + "\nRun: python scripts/legal_review_pack.py --write")
            return 1
        print(f"OK: {len(files)} generated files match the catalogues.")
        return 0
    target = PACK if args.write else Path(tempfile.mkdtemp(prefix="a4m-legal-pack-"))
    write(files, target)
    print(f"wrote {len(files)} files to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
