"""05E PR 2 (PRIV-LEGAL, K-PRIV, K-AIGUID): the legal review pack is current, complete, truthful about its own status and leaves the legal page copy unchanged.

Offline. The pack is GENERATED from the product catalogues; these tests keep it from going stale, check that every code reference in the fact map resolves, that every proposal
is well-formed, and that nothing in the pack records counsel sign-off or makes a compliance claim."""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
from pathlib import Path

import pytest

import tests.conftest  # noqa: F401  (isolation first)

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "docs/production/legal_review"
spec = importlib.util.spec_from_file_location("legal_review_pack", ROOT / "scripts/legal_review_pack.py")
GEN = importlib.util.module_from_spec(spec)
spec.loader.exec_module(GEN)

HAND_WRITTEN = ("README.md", "OPEN_LEGAL_QUESTIONS.md", "COUNSEL_CHECKLIST.md")
GENERATED_PROSE = ("FACTS.md", "CHANGE_LIST.md", "proposed/en_with_proposals.md")
STATUSES = set(GEN.STATUS_ORDER)


@pytest.fixture(scope="module")
def built():
    return GEN.build()


@pytest.fixture(scope="module")
def catalogs():
    return GEN.load_catalogs()


def facts():
    return json.loads((PACK / "source/facts.json").read_text(encoding="utf-8"))["facts"]


def proposals():
    return json.loads((PACK / "source/proposals.json").read_text(encoding="utf-8"))["proposals"]


# ------------------------------------------------------------------------------------------------------------------ currency and stability
def test_the_committed_pack_matches_the_catalogues(built):
    assert GEN.stale(built, PACK) == [], "stale legal review pack: run `python scripts/legal_review_pack.py --write`"


def test_generation_is_byte_stable(built):
    again = GEN.build()
    assert again == built


def test_every_offered_language_and_the_preserved_one_have_a_file_and_a_digest_per_document(built):
    for code in GEN.OFFERED:
        assert f"texts/{code}.md" in built
    assert "texts/ru_PRESERVED_EXCLUDED.md" in built and "texts/ru.md" not in built
    manifest = json.loads(built["texts/MANIFEST.json"])
    assert manifest["offered"] == list(GEN.OFFERED) and manifest["preserved_excluded"] == ["ru"]
    for code in GEN.OFFERED + GEN.PRESERVED_EXCLUDED:
        for doc in GEN.DOCUMENTS:
            d = manifest["locales"][code][doc]
            assert re.fullmatch(r"[0-9a-f]{64}", d["sha256"]) and d["strings"] > 5
    assert len({manifest["locales"][c]["privacy"]["sha256"] for c in GEN.OFFERED}) == len(GEN.OFFERED)       # the languages really differ


def test_the_texts_contain_every_string_of_the_three_pages_in_every_language(built, catalogs):
    pages = {doc: GEN.parse_page(tsx) for doc, (_t, _p, tsx) in GEN.DOCUMENTS.items()}
    for code in GEN.OFFERED + GEN.PRESERVED_EXCLUDED:
        name = f"texts/{code}.md" if code in GEN.OFFERED else f"texts/{code}_PRESERVED_EXCLUDED.md"
        text = built[name]
        for doc, page in pages.items():
            for _kind, keys in page["blocks"]:
                for k in keys:
                    assert catalogs[code][k] in text, (code, k)
            assert catalogs[code][page["title_key"]] in text


def test_the_status_line_never_claims_review(built):
    for code in GEN.OFFERED:
        text = built[f"texts/{code}.md"]
        assert "NOT reviewed by counsel or a native legal reviewer" in text and "Counsel sign-off for this language: NOT DONE" in text
    assert "PRESERVED BUT EXCLUDED" in built["texts/ru_PRESERVED_EXCLUDED.md"]


def test_the_ai_guidance_and_deterministic_mo_wording_are_included(built):
    for code in GEN.OFFERED:
        text = built[f"texts/{code}.md"]
        assert "In-product AI-guidance and source wording (K-AIGUID)" in text and "Deterministic Mo wording" in text
        assert "`INSUFFICIENT`" in text and "`provenance.aiLabel`" in text


# ------------------------------------------------------------------------------------------------------------------ the parser fails loudly
def test_the_page_parser_rejects_a_line_it_does_not_understand(tmp_path, monkeypatch):
    (tmp_path / "Bad.tsx").write_text('export function X() {\n  return (\n    <LegalPage title={t("a.b")} updated="2026-01-01">\n      <blockquote>{t("a.c")}</blockquote>\n    </LegalPage>\n  );\n}\n', encoding="utf-8")
    monkeypatch.setattr(GEN, "ROOT", tmp_path)
    with pytest.raises(RuntimeError, match="unparsed legal page line"):
        GEN.parse_page("Bad.tsx")


def test_the_page_parser_reads_the_real_pages_in_render_order():
    page = GEN.parse_page("frontend/components/marketing/TermsContent.tsx")
    assert page["title_key"] == "terms.pageTitle" and page["updated"] == "2026-09-26"
    assert page["blocks"][0] == ("p", ["terms.intro"]) and ("h2", ["terms.changesHeading"]) in page["blocks"] and page["blocks"][-1] == ("p", ["terms.changesBody"])
    privacy = GEN.parse_page("frontend/components/marketing/PrivacyContent.tsx")
    assert ("li_pair", ["privacy.storeAccountTerm", "privacy.storeAccountDesc"]) in privacy["blocks"]


# ------------------------------------------------------------------------------------------------------------------ the fact map
def test_every_code_reference_in_the_fact_map_resolves():
    unresolved = []
    for f in facts():
        for ref in f["refs"]:
            path, symbol = ref[0], ref[1]
            pending = len(ref) > 2 and ref[2] == "pending-05E-PR1"
            p = ROOT / path
            if not p.is_file():
                if not pending:
                    unresolved.append((f["id"], path, "missing file"))
                continue
            if symbol not in p.read_text(encoding="utf-8", errors="replace") and not pending:         # a pending reference lands with the 05E engineering PR
                unresolved.append((f["id"], path, f"symbol not found: {symbol}"))
    assert unresolved == [], unresolved


def test_the_fact_map_is_well_formed_and_every_statement_key_exists(catalogs):
    ids = [f["id"] for f in facts()]
    assert len(ids) == len(set(ids))
    for f in facts():
        assert f["status"] in STATUSES, f["id"]
        assert f["document"] in ("privacy", "terms", "ai_transparency", "data_flow")
        for k in f["keys"]:
            assert k in catalogs["en"], (f["id"], k)
        if f["status"] != "NOT_A_CODE_FACT" and f["status"] != "NOT_VERIFIED":
            assert f["refs"], f["id"]                       # a verified or partial or contradicted or unstated fact names its code


def test_every_statement_of_the_three_legal_texts_is_covered_by_the_fact_map(catalogs):
    """Headings and page titles are structure; every other string of Privacy, Terms and AI transparency must be mapped to a fact."""
    covered = {k for f in facts() for k in f["keys"]}
    uncovered = []
    for doc, (_t, _p, tsx) in GEN.DOCUMENTS.items():
        for kind, keys in GEN.parse_page(tsx)["blocks"]:
            if kind == "h2":
                continue
            uncovered += [k for k in keys if k not in covered]
    assert uncovered == [], f"statements with no mapped fact: {uncovered}"


def test_the_findings_in_the_readme_are_backed_by_the_fact_map():
    by_id = {f["id"]: f for f in facts()}
    readme = (PACK / "README.md").read_text(encoding="utf-8")
    for fid in re.findall(r"\b((?:PF|TF|AF|DF)-\d\d)\b", readme):
        assert fid in by_id, fid
    # TF-05 (the EUR 19.99 sentence) was CONTRADICTED_BY_CODE until 04D replaced it with the beta statement (true today, still not reviewed by counsel); PF-21 is still contradicted
    assert by_id["TF-05"]["status"] == "VERIFIED_IN_CODE" and by_id["PF-21"]["status"] == "CONTRADICTED_BY_CODE"
    assert by_id["AF-05"]["status"] == "PARTIAL" and by_id["PF-19"]["status"] == "NOT_VERIFIED"


def test_the_facts_file_summary_matches_the_data(built):
    text = built["FACTS.md"]
    for status in GEN.STATUS_ORDER:
        n = sum(1 for f in facts() if f["status"] == status)
        assert f"| {status} | {n} |" in text


def test_the_claims_the_fact_map_makes_about_the_code_still_hold():
    """Spot-check the facts a reader would act on, directly against the code, so the map cannot rot silently."""
    pricing = (ROOT / "frontend/lib/pricing.ts").read_text(encoding="utf-8")
    assert "purchasable: false" in pricing or "purchasable: boolean" in pricing
    assert "LIVE_BILLING_ENABLED = False" in (ROOT / "src/billing/policy.py").read_text(encoding="utf-8")
    assert "EXTERNAL_CHECKOUT_AUTHORIZED = False" in (ROOT / "src/billing/policy.py").read_text(encoding="utf-8")
    cfg = " ".join((ROOT / n).read_text(encoding="utf-8") for n in ("src/config.py", "src/api/config.py", ".env.example"))
    assert not re.search(r"SUPPORT_EMAIL|PRIVACY_EMAIL|CONTACT_EMAIL|support_email", cfg)                    # PF-21: no contact address exists
    assert "MAX_AGENT_STEPS = 6" in (ROOT / "src/agent/policies.py").read_text(encoding="utf-8")                 # AF-01


def test_no_third_party_analytics_script_is_loaded_by_the_frontend():
    """DF-07 states that none is. Scan the frontend sources (not node_modules) for well-known analytics hosts and loaders."""
    banned = re.compile(r"googletagmanager|google-analytics|gtag\(|plausible\.io|segment\.(com|io)|mixpanel|hotjar|fullstory|posthog|amplitude\.com|clarity\.ms", re.I)
    hits = []
    for base in ("app", "components", "lib"):
        for p in (ROOT / "frontend" / base).rglob("*"):
            if p.suffix in (".ts", ".tsx", ".js", ".mjs") and "node_modules" not in p.parts:
                if banned.search(p.read_text(encoding="utf-8", errors="replace")):
                    hits.append(str(p.relative_to(ROOT)))
    assert hits == [], hits


# ------------------------------------------------------------------------------------------------------------------ the change list
def test_every_proposal_is_well_formed_and_cites_real_facts_and_questions(catalogs):
    fact_ids = {f["id"] for f in facts()}
    questions = set(re.findall(r"\|\s*(OL-[A-Z]\d+)\s*\|", (PACK / "OPEN_LEGAL_QUESTIONS.md").read_text(encoding="utf-8")))
    ids = [p["id"] for p in proposals()]
    assert len(ids) == len(set(ids))
    for p in proposals():
        assert p["action"] in ("replace", "insert_after") and p["kind"] in ("li", "p") and p["proposed"].strip() and p["reason"].strip()
        assert set(p["facts"]) <= fact_ids and set(p["questions"]) <= questions, p["id"]
        if p["action"] == "replace":
            assert p["key"] in catalogs["en"] and p["proposed"] != catalogs["en"][p["key"]]
        else:
            assert p["after_key"] in catalogs["en"] and p["new_key"] not in catalogs["en"]


def test_a_proposal_changes_only_what_it_says_in_the_applied_view(built, catalogs):
    applied = built["proposed/en_with_proposals.md"]
    current = built["texts/en.md"]
    for p in proposals():
        assert p["proposed"] in applied
        if p["action"] == "replace":
            assert catalogs["en"][p["key"]] not in applied or catalogs["en"][p["key"]] in p["proposed"]       # an extension of the current text contains it
        else:
            assert f"`{p['new_key']}` **[PROPOSED INSERT]**" in applied
        assert p["proposed"] not in current
    assert "NOT APPLIED" in applied.splitlines()[0]
    unchanged_keys = [k for k in ("privacy.storeAccountDesc", "privacy.voiceNoInference", "terms.respLawful", "aiTransparency.neverInference") if k not in {p.get("key") for p in proposals()}]
    assert all(catalogs["en"][k] in applied for k in unchanged_keys)


def test_the_word_diff_marks_removals_and_additions():
    assert GEN.word_diff("one two three", "one 2 three four") == "one ~~two~~ **2** three **four**"
    assert GEN.word_diff("same", "same") == "same"


def test_no_proposal_makes_a_compliance_claim_or_uses_a_banned_character():
    banned = re.compile(r"\bGDPR\b|compliant|certified|guarantee|bias-free|100%|approved by counsel|legally reviewed", re.I)
    for p in proposals():
        assert not banned.search(p["proposed"]), p["id"]
        assert "—" not in p["proposed"] and "–" not in p["proposed"], p["id"]           # no em or en dash in customer-facing copy
        assert "Ask More" not in p["proposed"]                                                  # the protected slogan is never re-stated or translated here


# ------------------------------------------------------------------------------------------------------------------ status discipline: nothing records a sign-off
def test_the_pack_never_records_counsel_signoff_or_a_compliance_claim(built):
    forbidden = re.compile(r"signed off|sign-off (is |was )?(done|complete|obtained|recorded)|counsel (has )?(approved|signed|reviewed|confirmed)|reviewed and approved|"
                           r"\bGDPR[- ](compliant|certified)|is compliant with|are compliant with|legally compliant|certified compliant|compliance (is )?(achieved|confirmed)", re.I)
    for name in HAND_WRITTEN:
        assert not forbidden.search((PACK / name).read_text(encoding="utf-8")), name
    for name in GENERATED_PROSE:
        assert not forbidden.search(built[name]), name


def test_the_signoff_table_is_not_done_for_every_language_and_the_readme_says_so():
    checklist = (PACK / "COUNSEL_CHECKLIST.md").read_text(encoding="utf-8")
    rows = [r for r in checklist.splitlines() if re.match(r"\|\s*(en|de|fr|es|it|pt|nl|ru)\b", r)]
    assert len(rows) == 8
    for r in rows:
        cells = [c.strip() for c in r.strip("|").split("|")]
        assert cells[-1] in ("NOT DONE", "EXCLUDED"), r
        assert cells[-3] in ("none appointed", "none") and cells[-2] == "none", r
    assert "- [x]" not in checklist.lower() and "[x]" not in checklist.lower()
    readme = (PACK / "README.md").read_text(encoding="utf-8")
    assert "No counsel sign-off exists" in readme and "REVIEW-READY, NOT REVIEWED" in readme and "Hosted verification: NOT RUN" in readme


def test_the_language_readiness_record_still_shows_no_legal_qualification():
    data = json.loads((ROOT / "docs/production/execution/language_readiness.json").read_text(encoding="utf-8"))
    for code, lang in data["languages"].items():
        assert lang["production_qualified"] is False and lang["offered_to_real_users"] is False, code
        assert lang["gates"]["LG-10"]["state"] != "PASS", code


# ------------------------------------------------------------------------------------------------------------------ the legal page copy is unchanged
def test_the_legal_page_copy_and_components_are_untouched_by_this_package():
    paths = ["frontend/lib/i18n/messages/w96/legal.ts", "frontend/lib/i18n/messages/w96/ru/legal.ts", "frontend/components/marketing/PrivacyContent.tsx",
             "frontend/components/marketing/TermsContent.tsx", "frontend/components/marketing/AiTransparencyContent.tsx", "frontend/components/marketing/LegalPage.tsx",
             "frontend/app/privacy/page.tsx", "frontend/app/terms/page.tsx", "frontend/app/ai-transparency/page.tsx"]
    out = subprocess.run(["git", "diff", "--name-only", "origin/main", "--", *paths], cwd=ROOT, capture_output=True, text=True)
    if out.returncode == 0:                                    # a detached or shallow checkout cannot compare
        # 04D (owner direction: no price on any candidate surface) is the ONE sanctioned change since this pack: it removed the false "Premium is EUR 19.99 per month" sentence
        # (terms.accountsPlans) and renders the beta statement in its place. Any other change to legal copy, and any other changed line in these files, still fails here.
        sanctioned = {"frontend/components/marketing/TermsContent.tsx", "frontend/lib/i18n/messages/w96/legal.ts", "frontend/lib/i18n/messages/w96/ru/legal.ts"}
        changed = set(out.stdout.split())
        assert changed <= sanctioned, sorted(changed - sanctioned)
        if changed:
            diff = subprocess.run(["git", "diff", "-U0", "origin/main", "--", *sorted(changed)], cwd=ROOT, capture_output=True, text=True).stdout
            lines = [ln for ln in diff.splitlines() if ln[:1] in "+-" and not ln.startswith(("+++", "---"))]
            allowed = ("accountsPlans:", "Basic ", "Basic is", "O Basic", "Basic бесплатен", '<li>{t("terms.accountsPlans")}</li>', '<li><BetaPricingStatement testId="terms-beta-pricing" /></li>',
                       'import { BetaPricingStatement } from "@/components/plan/BetaPricingStatement";')
            stray = [ln for ln in lines if not ln[1:].strip().lstrip('"').startswith(allowed) and not ln[1:].strip().startswith(allowed)]
            assert stray == [], f"legal copy changed beyond the sanctioned 04D Terms sentence: {stray}"
    for rel in paths:
        assert (ROOT / rel).is_file(), rel
