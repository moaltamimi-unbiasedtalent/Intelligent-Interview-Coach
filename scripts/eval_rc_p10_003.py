#!/usr/bin/env python
"""RC-P10-003 release-candidate ARTIFACT guard (deterministic, offline, 0 paid/live calls).

RC-P10-003 is an evidence artifact pinned to one merged-main SHA (not a Git tag, version bump or deployment). It was created by a separate owner-approved action AFTER
P10B-W11 was COMPLETE AND INTEGRATED; W11 itself did not create it. This guard validates the artifact against the repository (mostly static), keeps RC-P10-002 immutable and
re-derives the headline facts from live code so the manifest cannot drift from the tree.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

# TEST ISOLATION (hard requirement): before any application import (temp DATABASE_URL, no .env, non-temp engines fail fast).
import tests.conftest  # noqa: E402,F401

CANDIDATE = "54aad500ec937b4828984c32c64b77746534633d"
RUNTIME = "d27993d7f2757cf7605355e3f76c71dac6f85c10"
W11_HEAD = "654ca47ab603fe96d093e10faaa778f5f5ab2e33"
ACCEPTED_IDS = ["R-33", "R-38", "R-46", "R-49", "R-50", "R-51", "R-93", "R-94", "R-95", "R-96", "R-97"]
RC002_SHA1 = {  # RC-P10-002 is immutable: its two evidence files must stay byte-identical
    "artifacts/capstone/p10/RC-P10-002/manifest.json": "eade0cdd1c99160f564b494ee8e58b3f024c8679",
    "artifacts/capstone/p10/RC-P10-002/gate_results.md": "158a80acb34dd2b0e2210bf4f3d7eae29c140f82",
}


APP_ROOTS = {"src", "app", "scripts"}


def isolation_violation(source: str) -> str | None:
    """None when `source` is safe; else why not. Rule: if the script imports application code ANYWHERE (module level or inside a function), it must import
    `tests.conftest` at MODULE level before its first module-level import of application code (src/app/scripts or any other tests.* module)."""
    tree = ast.parse(source)
    imports: list[tuple[int, str, bool]] = []  # (lineno, module, module_level)
    top = {id(n) for n in tree.body}
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.level == 0 and n.module:
            imports.append((n.lineno, n.module, id(n) in top))
        elif isinstance(n, ast.Import):
            imports.extend((n.lineno, a.name, id(n) in top) for a in n.names)

    def is_app(mod: str) -> bool:
        return mod.split(".")[0] in APP_ROOTS or (mod.startswith("tests.") and mod != "tests.conftest")

    if not any(is_app(m) for _l, m, _t in imports):
        return None
    conftest = [ln for ln, m, t in imports if m == "tests.conftest" and t]
    if not conftest:
        return "imports application code but never imports tests.conftest at module level"
    early = [ln for ln, m, t in imports if t and is_app(m) and ln < conftest[0]]
    return f"application import at line {early[0]} precedes tests.conftest (line {conftest[0]})" if early else None


def read(rel: str) -> str:
    p = ROOT / rel
    return p.read_text(encoding="utf-8") if p.exists() else ""


def run() -> dict[str, tuple[bool, str]]:
    out: dict[str, tuple[bool, str]] = {}

    def check(name: str, ok: bool, detail: str = "") -> None:
        out[name] = (bool(ok), detail)

    rc = ROOT / "artifacts/capstone/p10/RC-P10-003"
    check("artifact_directory_exists", rc.is_dir())
    check("manifest_exists", (rc / "manifest.json").is_file())
    check("gate_results_exists", (rc / "gate_results.md").is_file())
    try:
        m = json.loads(read("artifacts/capstone/p10/RC-P10-003/manifest.json"))
        valid = isinstance(m, dict)
    except ValueError:
        m, valid = {}, False
    check("manifest_is_valid_json", valid)
    gate = read("artifacts/capstone/p10/RC-P10-003/gate_results.md")
    narrative = read("docs/capstone/p10/RC_P10_003_RELEASE_CANDIDATE.md")
    matrix = read("docs/capstone/p10/P10B_RELEASE_ACCEPTANCE_MATRIX.md")
    w11 = read("docs/capstone/p10/P10B_W11_INTEGRATED_REQUALIFICATION.md")

    check("release_candidate_is_rc_p10_003", m.get("release_candidate") == "RC-P10-003")
    check("candidate_sha_is_the_merged_main_sha", m.get("release_candidate_sha") == CANDIDATE and CANDIDATE in gate and CANDIDATE in narrative)
    check("qualified_runtime_merge_sha_recorded", m.get("qualified_runtime_merge_sha") == RUNTIME and RUNTIME in gate)
    check("w11_feature_head_recorded", m.get("w11_feature_head") == W11_HEAD)
    check("w11_feature_pr_132_recorded", m.get("w11_feature_pr") == "#132")
    check("w11_docs_pr_133_recorded", m.get("w11_docs_pr") == "#133")
    check("w11_complete_and_integrated", m.get("w11_status") == "COMPLETE AND INTEGRATED" and "# W11 COMPLETE AND INTEGRATED" in w11)

    # ---- release matrix (recomputed from the matrix document, not copied)
    rows = [[c.strip() for c in ln.strip().strip("|").split("|")] for ln in matrix.splitlines() if re.match(r"^\| R-\d+ ", ln)]
    by_id = {r[0]: r for r in rows}
    results = [r[5] for r in rows]
    tot, p, a, b = len(rows), results.count("PASS"), results.count("ACCEPTED"), results.count("BLOCKER")
    rm = m.get("release_matrix", {})
    check("matrix_total_99", tot == 99 and rm.get("total") == 99, str(tot))
    check("matrix_pass_88", p == 88 and rm.get("PASS") == 88, str(p))
    check("matrix_accepted_11", a == 11 and rm.get("ACCEPTED") == 11, str(a))
    check("matrix_blocker_0", b == 0 and rm.get("BLOCKER") == 0, str(b))
    listed = [x.get("matrix_id") for x in m.get("accepted_limitations", [])]
    check("all_11_accepted_ids_represented", sorted(listed) == sorted(ACCEPTED_IDS) and all(by_id.get(i, [0] * 6)[5] == "ACCEPTED" for i in ACCEPTED_IDS)
          and all(i in gate and i in narrative for i in ACCEPTED_IDS)
          and all(x.get("status") == "ACCEPTED" and x.get("rationale") and x.get("title") for x in m.get("accepted_limitations", [])))
    check("r_52_pass", by_id.get("R-52", [0] * 6)[5] == "PASS" and m.get("resolved_findings", {}).get("R-52", {}).get("status") == "PASS")
    check("r_98_pass", by_id.get("R-98", [0] * 6)[5] == "PASS" and m.get("resolved_findings", {}).get("R-98", {}).get("status") == "PASS")
    check("r_99_pass", by_id.get("R-99", [0] * 6)[5] == "PASS" and m.get("resolved_findings", {}).get("R-99", {}).get("status") == "PASS")
    check("no_r_100_for_the_rc", "R-100" not in by_id)

    # ---- facts re-derived from the live tree
    from src.agent.registry import career_tool_registry
    from src.agent.specialists.registry import SpecialistName
    from src.application import admin_permissions as perm
    from src.locales import DOCUMENT_LANGUAGE_CODES, SUPPORTED_LOCALE_CODES
    from src.persistence import KNOWLEDGE_LANGUAGES

    vi = m.get("version_identity", {})
    mig = sorted(p_.name for p_ in (ROOT / "migrations/versions").glob("0*.py"))
    check("alembic_head_0025_single", mig[-1].startswith("0025_security_audit_incidents") and len({x[:4] for x in mig}) == len(mig) and vi.get("alembic_head") == "0025_security_audit_incidents")
    check("admin_permissions_43", len(perm.PERMISSIONS) == 43 and vi.get("admin_permissions") == 43)
    check("platform_admin_28", len(perm.ROLE_PRESETS["platform_admin"]) == 28 and str(vi.get("platform_admin_permissions", "")).startswith("28"))
    check("eight_interface_locales", len(SUPPORTED_LOCALE_CODES) == 8 and vi.get("interface_locales") == 8)
    check("seven_kb_document_languages", len(DOCUMENT_LANGUAGE_CODES) == 7 and len(KNOWLEDGE_LANGUAGES) == 7 and vi.get("speech_document_kb_languages") == 7)
    tools = career_tool_registry(MagicMock()).names()
    check("eleven_tools", len(tools) == 11 and vi.get("tools", {}).get("total") == 11 and vi.get("tools") == {"total": 11, "career": 6, "specialists": 3, "human_action": 2})
    names = sorted(s.value for s in SpecialistName)
    check("exactly_three_specialists", names == sorted(vi.get("specialists", [])) and len(names) == 3, ", ".join(names))
    check("no_evaluation_specialist", "evaluation" not in " ".join(names) and "no Evaluation Specialist" in str(vi.get("evaluation_architecture")))

    # ---- boundaries
    check("paid_live_calls_zero", m.get("paid_live_calls") == 0 and "0 paid/live" in narrative)
    check("public_launch_not_authorized", m.get("public_launch") == "NOT AUTHORIZED" and "NOT AUTHORIZED" in gate)
    check("pilot_2_remains_paused", "PAUSED" in str(m.get("human_pilot")) and "PAUSED" in narrative)
    check("p10c_not_started", m.get("p10c") == "NOT STARTED" and "NOT STARTED" in narrative)
    check("rc_p10_002_present_and_byte_identical", all((ROOT / f).is_file() and hashlib.sha1((ROOT / f).read_bytes()).hexdigest() == h for f, h in RC002_SHA1.items()))
    check("rc_p10_002_not_modified_in_the_working_diff", not _diff_touches("artifacts/capstone/p10/RC-P10-002"))
    fs = m.get("freeze_semantics", {})
    check("freeze_semantics_runtime_change_requires_new_rc", "RC-P10-004" in str(fs.get("new_candidate_required_for")) and fs.get("rc_candidate_sha") == CANDIDATE and fs.get("gate_rerun_for_favourable_result") is False)
    check("w10_13_contamination_disclosure_referenced", "disclosed contamination with stable post-incident qualification baseline" in json.dumps(m) and "disclosed contamination with stable post-incident qualification baseline" in narrative)
    check("artifact_rc_not_git_tag_identity", fs.get("git_tag_identity") is False and "not a Git tag" in narrative and "not a Git tag" in str(m.get("creation")) and not _has_tag("RC-P10-003"))
    check("w11_did_not_create_the_rc_and_this_is_separate", "separate owner-approved" in str(m.get("creation")) and "W11 did NOT create" in narrative and "W11 did NOT create" in str(m.get("creation")))
    check("activation_rule_recorded", "present on main" in str(m.get("activation_rule")) and "present on main" in narrative)
    check("no_secrets_or_private_paths_in_artifact", not re.search(r"(sk-[A-Za-z0-9]{10,}|api[_-]?key\s*[:=]\s*\S{8,}|/Users/)", json.dumps(m) + gate + narrative))

    # ---- evaluator test-isolation guard (RC qualification contamination: an unisolated legacy evaluator wrote the dev research cache)
    good = "import sys\nsys.path.insert(0, '.')\nimport tests.conftest\nfrom src.x import y\n"
    bad_late = "from src.x import y\nimport tests.conftest\n"
    bad_none = "def f():\n    from src.x import y\n"
    check("isolation_detector_self_test", isolation_violation(good) is None and isolation_violation(bad_late) and isolation_violation(bad_none) and isolation_violation("import json\n") is None,
          "the detector accepts isolated scripts and flags late/missing bootstrap")
    import yaml
    wf = yaml.safe_load(read(".github/workflows/ci.yml"))
    ci_steps = "\n".join(st.get("run", "") for job in wf["jobs"].values() for st in job["steps"])
    scripts = sorted({ROOT / r for r in re.findall(r"scripts/eval_[a-z_0-9]+\.py", ci_steps)})   # every CI evaluator (manual/live-opt-in evaluators are out of scope)
    offenders = [f"{p_.name}: {why}" for p_ in scripts if (why := isolation_violation(p_.read_text(encoding="utf-8")))]
    check("every_ci_evaluator_importing_app_code_bootstraps_isolation_first", not offenders and len(scripts) >= 40, f"{len(scripts)} CI evaluators scanned; " + ("; ".join(offenders) if offenders else "0 offenders"))
    check("legacy_release_evaluator_bootstraps_isolation_before_src", isolation_violation(read("scripts/eval_release_candidate.py")) is None and "import tests.conftest" in read("scripts/eval_release_candidate.py"))
    notes = json.dumps(m.get("qualification_environment_incidents", [])) + gate + narrative
    check("rc_contamination_incident_disclosed", "be293349a0419d930134b8c6.json" in notes and "25264b17b36f7a365ff8dfaca9eec97e997ee710" in notes and "a3ad0eea16f2fadd337bba0ce2fd5ea6a88b1dc8" in notes
          and "unisolated legacy evaluator" in notes)
    return out


def _git(*args: str) -> str | None:
    import subprocess
    try:
        r = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20)
    except Exception:  # noqa: BLE001 - git unavailable: skip the VCS-only assertions
        return None
    return r.stdout if r.returncode == 0 else None


def _diff_touches(path: str) -> bool:
    d = _git("status", "--porcelain", "--", path)
    return bool(d and d.strip())


def _has_tag(tag: str) -> bool:
    t = _git("tag", "--list", tag)
    return bool(t and t.strip())


if __name__ == "__main__":
    res = run()
    w = max(len(k) for k in res)
    for k, (ok, d) in res.items():
        print(f"  {k:<{w}}  {'PASS' if ok else 'FAIL'}  {d}")
    bad = [k for k, (ok, _d) in res.items() if not ok]
    print(f"\nChecks: {len(res)}   Paid LLM calls: 0   Live calls: 0")
    print("RESULT:", "PASS" if not bad else "FAIL: " + ", ".join(bad))
    sys.exit(1 if bad else 0)
