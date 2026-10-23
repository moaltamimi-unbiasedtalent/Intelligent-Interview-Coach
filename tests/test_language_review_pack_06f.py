"""06F review packs: deterministic generation, blank sign-off forms that map onto the 06H activation record, freeze manifest and the incremental diff.

Offline. The catalogue is read with node and the frontend dependencies (as the 06A locale-audit test does); every other test works on that one in-memory catalogue.
No test records a qualification: the only completed forms here are synthetic fixtures built inside the test, never written to the repository.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

import tests.conftest  # noqa: F401  (test isolation)
from src.language_activation import GATES, validate_locale_record
from src.language_quality import review_pack as P
from src.locales import ACTIVE_CANDIDATE_LOCALES

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "language_review_pack.py"
TODAY = date(2026, 10, 22)
SHA = "a" * 40


@pytest.fixture(scope="module")
def built():
    assert shutil.which("node"), "node is required (CI installs it for the python shards)"
    catalogue = P.load_catalogue()
    packs, manifest, contents = P.build_all(catalogue)
    return catalogue, packs, manifest, contents


def _complete_form(lang: str, gate: str, digest: str, **over) -> dict:
    form = P.form_template(lang, digest)
    f = form["forms"][gate]
    f.update({"reviewer_name": "Test Reviewer One", "qualification_statement": "Synthetic test fixture: a stated qualification of sufficient length.", "independence_statement": "Not the author; fixed fee.",
              "conflicts_declared": "NONE", "evidence_reference": "evidence/signed/test-fixture.md", "approval_date": "2026-10-21", "release_sha": SHA, "approved_until": "",
              "pack_content_digest_reviewed": digest, "verdict_summary": "Fixture: 0 BLOCKER."})
    f.update(over)
    return form


# ------------------------------------------------------------------------------------------------------------------------------------------------ determinism and shape
def test_committed_packs_and_manifest_are_current(built):
    _, packs, manifest, _ = built
    assert P.check_all(packs, manifest) == [], "run: python scripts/language_review_pack.py --write"


def test_generation_is_deterministic(built):
    catalogue, packs, manifest, _ = built
    again, manifest2, _ = P.build_all(catalogue)
    assert again == packs and P.manifest_text(manifest2) == P.manifest_text(manifest)


def test_every_language_has_exactly_the_pack_files(built):
    _, packs, _, _ = built
    assert set(packs) == set(ACTIVE_CANDIDATE_LOCALES) == set(P.LANGUAGES)
    for lang, files in packs.items():
        assert tuple(files) == P.FILES, lang
        for path in P.FILES:
            assert (P.PACK_DIR / lang / path).exists()


def test_interface_strings_complete_and_grouped_by_surface(built):
    catalogue, packs, _, contents = built
    n = len(catalogue["en"])
    for lang in P.LANGUAGES:
        c = contents[lang]
        assert len(c["interface"]) == n
        text = packs[lang]["INTERFACE_STRINGS.md"]
        assert text.count("\n| `") == n, lang
        assert "## Surface:" in text and "Context:" in text and "Appears in:" in text
        for key in list(catalogue["en"])[:50:7] + list(catalogue["en"])[-3:]:
            assert f"| `{key}` |" in text
        if lang != "en":
            assert "translation" in text.splitlines()[next(i for i, l in enumerate(text.splitlines()) if l.startswith("| key"))]


def test_a_non_english_pack_shows_the_english_source_and_the_translation(built):
    catalogue, packs, _, contents = built
    row = next(i for i in contents["de"]["interface"] if i["key"] == "common.save" or len(i["en"]) > 12)
    esc = lambda s: P._cell(s)  # noqa: E731
    assert esc(row["en"]) in packs["de"]["INTERFACE_STRINGS.md"] and esc(row["text"]) in packs["de"]["INTERFACE_STRINGS.md"]
    assert row["text"] == catalogue["de"][row["key"]]


def test_mo_sentence_tables_come_from_the_06c_inventory(built):
    from src.language_quality import inventory

    _, packs, _, contents = built
    keys = [s.key for s in inventory.inventory()]
    assert [m["key"] for m in contents["fr"]["mo"]] == keys
    for lang in P.LANGUAGES:
        text = packs[lang]["MO_SENTENCES.md"]
        assert all(f"`{k}`" in text for k in keys)
        assert "POLICY:" in text and "Transactional email" in text and "Known gaps" in text
    inv = {s.key: s for s in inventory.inventory()}
    assert contents["nl"]["mo"][3]["text"] == inv[contents["nl"]["mo"][3]["key"]].texts["nl"]


def test_interview_samples_are_the_synthetic_bank_prompts(built):
    _, packs, _, contents = built
    bank = json.loads(P.BANK_FILE.read_text(encoding="utf-8"))
    assert bank["synthetic"] is True
    for lang in P.LANGUAGES:
        samples = contents[lang]["samples"]
        assert len(samples) == len(P.SAMPLE_TASKS) * len(bank["roles"])
        text = packs[lang]["INTERVIEW_SAMPLES.md"]
        assert "SYNTHETIC" in text and "no real" in text.lower()
        first = samples[0]
        assert P._cell(first["text"]) in text and P._cell(first["en"]) in text
    assert not re.search(r"https?://|@[a-z]+\.", packs["it"]["INTERVIEW_SAMPLES.md"])


def test_legal_pointers_cover_legal_namespaces_and_reference_05e_conditionally(built):
    catalogue, packs, _, contents = built
    for lang in P.LANGUAGES:
        legal = contents[lang]["legal"]
        assert legal and {i["ns"] for i in legal} <= set(P.LEGAL_NAMESPACES)
        text = packs[lang]["LEGAL_POINTERS.md"]
        assert "If `docs/production/legal_review/` exists" in text and "If the directory is absent" in text
        assert "qualified" in text and "not a legal-advice review" in text
    assert sum(1 for k in catalogue["en"] if k.split(".", 1)[0] in P.LEGAL_NAMESPACES) == len(contents["en"]["legal"])


def test_the_pack_never_claims_a_review(built):
    _, packs, manifest, _ = built
    for lang, files in packs.items():
        for name, text in files.items():
            if name.endswith(".md"):
                assert "NOT REVIEWED" in text, f"{lang}/{name}"
                assert not re.search(r"\b(approved|qualified|signed off) by\b", text, re.I)
    assert manifest["reviewed"] is False and manifest["signoffs_recorded"] == 0 and manifest["freeze_sha"] is None and manifest["status"].startswith("NOT FROZEN")


# ------------------------------------------------------------------------------------------------------------------------------------------------ instructions
def test_instruction_sheet_has_every_judging_criterion_and_the_slogan(built):
    _, packs, _, _ = built
    for lang in P.LANGUAGES:
        text = packs[lang]["INSTRUCTIONS.md"]
        for word in ("Correctness", "Naturalness", "Register", "Terminology", "Policy-sentence equivalence", "English leaks", "Protected slogan"):
            assert word in text, (lang, word)
        assert P.BRAND_SLOGAN in text and "BLOCKER" in text and "Independence" in text and "translation tool" in text


# ------------------------------------------------------------------------------------------------------------------------------------------------ sign-off form
HUMAN_FIELDS = ("reviewer_name", "qualification_statement", "independence_statement", "conflicts_declared", "evidence_reference", "approval_date", "release_sha", "approved_until",
                "pack_content_digest_reviewed", "verdict_summary")


def test_forms_are_never_prefilled(built):
    _, packs, _, contents = built
    for lang in P.LANGUAGES:
        tpl = json.loads(packs[lang]["SIGNOFF_FORM.template.json"])
        assert tpl["pack_content_digest_expected"] == P.content_digest(contents[lang])
        assert set(tpl["forms"]) == {"LG-10", "LG-11"}
        for gate, f in tpl["forms"].items():
            assert all(f[k] == "" for k in HUMAN_FIELDS), (lang, gate)
            assert f["state"] == "NOT SIGNED"
            assert P.validate_form(tpl, gate, today=TODAY), "a blank form must not validate"
        md = packs[lang]["SIGNOFF_FORM.md"]
        assert md.count("____") >= 2 * 9 and "BLANK" in md


def test_form_fields_match_what_language_activation_requires(built):
    _, packs, _, _ = built
    md = packs["de"]["SIGNOFF_FORM.md"]
    for needed in ("approver", "evidence", "approved_on", "release_sha"):
        assert f".{needed}`" in md
    assert [m[0] for m in P.FIELD_MAP][:1] == ["reviewer_name"]
    # every key language_activation reads from a PASS gate is covered by the mapping
    for key in ("approver", "evidence", "approved_on", "release_sha"):
        assert any(key in target for _, target, _ in P.FIELD_MAP)


@pytest.mark.parametrize("gate", P.FORM_GATES)
def test_a_complete_form_maps_to_a_06h_valid_gate_record(built, gate):
    _, _, _, contents = built
    digest = P.content_digest(contents["es"])
    form = _complete_form("es", gate, digest)
    assert P.validate_form(form, gate, expected_digest=digest, today=TODAY) == []
    frag = P.gate_fragment(form, gate)
    assert set(frag) == {"evidence", "approver", "approved_on", "release_sha"}
    rec = {"production_qualified": True, "offered_to_real_users": True, "release_sha": SHA, "gates": {}}
    for g in GATES:
        rec["gates"][g] = {"state": "PASS", "evidence": "evidence/other/test-fixture.md", "approver": "Test Approver", "approved_on": "2026-10-20", "release_sha": SHA}
    rec["gates"][gate] = {"state": "PASS", **frag}
    status = validate_locale_record("es", rec, today=TODAY)
    assert status.qualified, status.problems
    rec["gates"][gate]["release_sha"] = "b" * 40
    assert not validate_locale_record("es", rec, today=TODAY).qualified          # a different SHA makes it stale: one freeze SHA for all gates


def test_form_validation_negatives(built):
    _, _, _, contents = built
    digest = P.content_digest(contents["fr"])
    gate = "LG-11"

    def problems(**over):
        return P.validate_form(_complete_form("fr", gate, digest, **over), gate, expected_digest=digest, today=TODAY)

    assert problems() == []
    assert problems(reviewer_name="Claude")                       # automation is not a human
    assert problems(reviewer_name="TBD")
    assert problems(reviewer_name="Engineering Team")
    assert problems(release_sha="HEAD")
    assert problems(release_sha="ABCDEF1")
    assert problems(approval_date=(TODAY + timedelta(days=1)).isoformat())
    assert problems(approval_date="22/10/2026")
    assert problems(evidence_reference="n/a")
    assert problems(qualification_statement="native")
    assert problems(independence_statement="")
    assert problems(conflicts_declared="")
    assert problems(approved_until="2026-01-01")
    assert problems(pack_content_digest_reviewed="0" * 64)         # reviewed a different text
    assert problems(pack_content_digest_reviewed="")
    assert problems(verdict_summary="")
    bad = _complete_form("fr", gate, digest)
    bad["language"] = "ru"
    assert P.validate_form(bad, gate, today=TODAY)
    assert P.validate_form(_complete_form("fr", gate, digest), "LG-05", today=TODAY)


# ------------------------------------------------------------------------------------------------------------------------------------------------ hints, usage scan
def test_mechanical_hints():
    assert P._hints("Dashboard Export", "Dashboard Export", "de") == ["=EN"]
    assert P._hints("Hello {name}", "Hallo", "de") == ["PH"]
    assert "EN?" in P._hints("A sentence.", "Das ist the answer.", "de")
    assert "SLOGAN" in P._hints(f"{P.BRAND_SLOGAN} Today", "Mehr fragen. Mehr sein. Heute", "de")
    assert P._hints(f"{P.BRAND_SLOGAN} Today", f"{P.BRAND_SLOGAN} Heute", "de") == []
    assert P._hints("anything", "anything", "en") == []


def test_the_protected_slogan_is_untouched_in_every_language(built):
    _, _, _, contents = built
    for lang in P.LANGUAGES:
        for row in contents[lang]["interface"] + contents[lang]["mo"] + contents[lang]["email"]:
            assert "SLOGAN" not in row["hints"], (lang, row.get("key") or row.get("id"))


def test_usage_scan_finds_static_and_namespace_references(tmp_path):
    fe = tmp_path / "frontend"
    (fe / "components").mkdir(parents=True)
    (fe / "lib" / "i18n" / "messages").mkdir(parents=True)
    (fe / "components" / "A.tsx").write_text('t("home.title"); t(`home.${k}Body`);', encoding="utf-8")
    (fe / "lib" / "i18n" / "messages" / "en.ts").write_text('"home.title"', encoding="utf-8")
    per_key, per_ns = P.scan_usage({"home.title", "home.x", "nav.a"}, fe)
    assert per_key == {"home.title": ["components/A.tsx"]} and per_ns == {"home": ["components/A.tsx"]}


# ------------------------------------------------------------------------------------------------------------------------------------------------ freeze and diff
def test_freeze_snapshot_and_incremental_diff(built):
    catalogue, _, manifest, contents = built
    with pytest.raises(ValueError):
        P.build_snapshot(contents, manifest, "not-a-sha")
    snap = P.build_snapshot(contents, manifest, SHA)
    assert snap["release_sha"] == SHA and snap["manifest"]["freeze_sha"] == SHA and set(snap["languages"]) == set(P.LANGUAGES)
    assert all(P.diff_against(snap, contents[lang])["needs_rereview"] == 0 for lang in P.LANGUAGES), "an unchanged tree needs no re-review"

    keys = list(catalogue["en"])
    k_text, k_src, k_drop = keys[3], keys[5], keys[7]
    changed = copy.deepcopy(dict(catalogue))
    changed = {loc: dict(v) for loc, v in changed.items()}
    changed["de"][k_text] = changed["de"][k_text] + " (neu)"
    changed["en"][k_src] = changed["en"][k_src] + " now"
    for loc in changed:
        changed[loc]["zz.added"] = "New string" if loc == "en" else "Neu"
        changed[loc].pop(k_drop)
    new_de = P.build_content(changed, "de", usage=({}, {}))
    d = P.diff_against(snap, new_de)
    assert d["added"] == ["interface:zz.added"] and d["removed"] == [f"interface:{k_drop}"]
    assert d["source_changed"] == [f"interface:{k_src}"] and d["text_changed"] == [f"interface:{k_text}"]
    assert d["needs_rereview"] == 3 and d["unchanged"] == len(P.content_items(new_de)) - 3
    md = P.render_changes_md(d, new_de)
    assert "NOT REVIEWED" in md and "zz.added" in md and k_text in md and f"`{SHA}`" in md
    # another language is unaffected by the German edit apart from the shared English edits
    new_fr = P.build_content(changed, "fr", usage=({}, {}))
    assert P.diff_against(snap, new_fr)["text_changed"] == []
    # the digest changes whenever the content does
    assert P.content_digest(new_de) != P.content_digest(contents["de"])


def test_a_layout_change_does_not_change_the_content_digest(built):
    _, _, _, contents = built
    c = copy.deepcopy(contents["it"])
    c["interface"][0]["note"] = "A different context note"
    c["interface"][0]["files"] = ["x.tsx"]
    assert P.content_digest(c) == P.content_digest(contents["it"])


def test_manifest_digests_cover_every_file(built):
    _, packs, manifest, contents = built
    for lang in P.LANGUAGES:
        m = manifest["languages"][lang]
        assert set(m["files"]) == set(P.FILES) and m["content_digest"] == P.content_digest(contents[lang])
        assert m["interface_keys"] == len(contents[lang]["interface"])
    assert manifest["english_source_digest"] == manifest["languages"]["en"]["content_digest"]


def test_digest_embedded_in_readme_and_form_match_the_manifest(built):
    _, packs, manifest, _ = built
    for lang in P.LANGUAGES:
        d = manifest["languages"][lang]["content_digest"]
        assert d in packs[lang]["README.md"] and d in packs[lang]["SIGNOFF_FORM.md"]


# ------------------------------------------------------------------------------------------------------------------------------------------------ command line
def _run(*args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("AI_BUDGET")}
    return subprocess.run([sys.executable, str(SCRIPT), *args], cwd=str(ROOT), capture_output=True, text=True, check=False, env=env)


def test_cli_check_freeze_diff_and_validate(built, tmp_path):
    _, _, _, contents = built
    r = _run("--check")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "review packs current" in r.stdout and "Sign-offs recorded: 0" in r.stdout
    r = _run("--freeze", "--release-sha", SHA, "--out", str(tmp_path / "freeze"))
    assert r.returncode == 0, r.stdout + r.stderr
    snap = tmp_path / "freeze" / "FREEZE_SNAPSHOT.json"
    assert json.loads(snap.read_text(encoding="utf-8"))["release_sha"] == SHA
    r = _run("--diff", "--baseline", str(snap), "--language", "de", "--out", str(tmp_path / "diff"))
    assert r.returncode == 0 and "0 item(s) need re-review" in r.stdout
    assert (tmp_path / "diff" / "CHANGES_SINCE_REVIEW_de.md").exists()
    assert _run("--freeze", "--release-sha", "zzz", "--out", str(tmp_path / "bad")).returncode != 0
    blank = tmp_path / "blank.json"
    blank.write_text(json.dumps(P.form_template("de", P.content_digest(contents["de"]))), encoding="utf-8")
    r = _run("--validate-form", str(blank), "--gate", "LG-11")
    assert r.returncode == 1 and "FORM INCOMPLETE" in r.stdout
    digest = P.content_digest(contents["de"])
    done = tmp_path / "done.json"
    done.write_text(json.dumps(_complete_form("de", "LG-11", digest, approval_date="2026-10-01")), encoding="utf-8")
    r = _run("--validate-form", str(done), "--gate", "LG-11")
    assert r.returncode == 0 and "Nothing was recorded" in r.stdout and '"approver": "Test Reviewer One"' in r.stdout


def test_nothing_in_the_package_writes_the_readiness_record():
    source = (ROOT / "src" / "language_quality" / "review_pack.py").read_text(encoding="utf-8") + SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"language_readiness\.json[^\n]*(write|open\()|(write|open\()[^\n]*language_readiness", source), "the package must never write the readiness record"
    assert "READINESS_PATH" not in source


# ------------------------------------------------------------------------------------------------------------------------------------------------ the owner checklist
CHECKLIST = ROOT / "docs" / "production" / "language_review" / "OWNER_READINESS_CHECKLIST.md"
DOCS = (CHECKLIST, ROOT / "docs" / "production" / "language_review" / "README.md", ROOT / "docs" / "production" / "execution" / "evidence" / "06G_HUMAN_EVAL_PROTOCOL.md",
        ROOT / "docs" / "production" / "execution" / "evidence" / "06G_PILOT_REVALIDATION_CHECKLIST.md")


def test_checklist_maps_every_field_language_activation_requires():
    text = CHECKLIST.read_text(encoding="utf-8")
    for field in ("approver", "evidence", "approved_on", "release_sha", "approved_until", "production_qualified", "offered_to_real_users"):
        assert f"`{field}`" in text or f".{field}`" in text, field
    for gate in ("LG-10", "LG-11", "LG-04", "LG-05"):
        assert gate in text
    for lang in P.LANGUAGES:
        assert lang in text
    for od in ("OD-LANG-03", "OD-LANG-04", "OD-BUDGET", "OD-GATE-THRESHOLDS"):
        assert od in text
    for form_field, _, _ in P.FIELD_MAP:
        assert f"`forms.LG-11.{form_field}`" in text or f"`forms.<gate>.{form_field}`" in text or form_field in text, form_field


def test_documents_state_that_nothing_is_signed_and_claim_nothing():
    for path in DOCS:
        text = path.read_text(encoding="utf-8")
        assert re.search(r"NOT RUN|NOTHING IS SUPPLIED|MATERIALS ONLY|OPEN", text), path.name
        assert not re.search(r"\b(approved|signed|qualified) (by|on)\s+[A-Z][a-z]+ [A-Z]", text), path.name


def test_paths_named_in_the_documents_exist():
    pattern = re.compile(r"`((?:docs|src|scripts|tests|evaluations|frontend)/[A-Za-z0-9_./-]+\.(?:md|json|py|mjs|ts|tsx))`")
    missing = []
    for path in DOCS:
        for m in pattern.finditer(path.read_text(encoding="utf-8")):
            if "<" in m.group(1) or not (ROOT / m.group(1)).exists():
                missing.append((path.name, m.group(1)))
    assert missing == []


def test_the_documents_pass_the_repository_language_claim_scanner():
    spec = importlib.util.spec_from_file_location("eval_marketing_product_trust", ROOT / "scripts" / "eval_marketing_product_trust.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    offenders = {str(p): mod.language_qualification_claims(p.read_text(encoding="utf-8")) for p in list(DOCS) + list(P.PACK_DIR.rglob("*.md"))}
    assert {k: v for k, v in offenders.items() if v} == {}
